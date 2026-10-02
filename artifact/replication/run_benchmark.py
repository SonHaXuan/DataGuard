#!/usr/bin/env python3
"""
run_benchmark.py

Run the Data Safety vs privacy-policy discrepancy task against a language model
and record everything needed to score it and to audit its failure modes.

The script deliberately uses only the Python standard library, so the
replication package has no dependency footprint beyond Python itself.

Supported providers
-------------------
    openai     any OpenAI-compatible /v1/chat/completions endpoint
    anthropic  /v1/messages
    gemini     generativelanguage.googleapis.com generateContent
    ollama     local http://localhost:11434/api/chat

What is recorded per call
-------------------------
Raw response text, the parsed labels, whether parsing succeeded, the failure
mode when it did not, latency, token usage when the provider reports it, the
resolved model identifier the provider echoes back, and the repeat index. The
raw text is kept because the hallucination analysis (Major Issue 4) is computed
from it, not from the parsed labels.

Usage
-----
    export OPENAI_API_KEY=sk-...
    python3 run_benchmark.py --provider openai --model gpt-5 \
        --dataset data/eval_set_natural.csv --out runs/

    # self-consistency probe: same prompt three times at non-zero temperature
    python3 run_benchmark.py --provider openai --model gpt-5 \
        --dataset data/eval_set_natural.csv --repeats 3 --temperature 0.7 \
        --out runs/
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent

# The task prompt. Kept verbatim from the structure described in the manuscript
# (Task Description / Terms Explanation / Rules for Formatting / Content
# Injection) so the comparison with the 2024 runs is like-for-like.
SYSTEM_PROMPT = (
    "You are an expert in labeling the content comparison of the Data Safety "
    "declaration and the Privacy Policy for an Android application."
)

USER_TEMPLATE = """Compare and analyse the information between the Data Safety declaration and the Privacy Policy of an Android app, and decide two things: whether the disclosure is incorrect, and whether it is incomplete.

Definitions:
- incorrect = 1 when the Data Safety declaration does not disclose a data practice that the Privacy Policy does mention.
- incomplete = 1 when the Data Safety declaration discloses a data practice, but the Privacy Policy does not describe it as fully as the Data Safety declaration does.
- Use 0 when the condition does not hold.

Answer with JSON only, no explanation, exactly in this form:
{{"incorrect": 0 or 1, "incomplete": 0 or 1}}

Data Safety:
{data_safety}

Privacy Policy:
{privacy_policy}"""


# --------------------------------------------------------------------------
# provider adapters
# --------------------------------------------------------------------------
def _post(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_openai(model: str, system: str, user: str, temperature: float,
                base_url: str, api_key: str, max_tokens: int,
                json_mode: bool = False) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_completion_tokens": max_tokens,
    }
    # Some newer models accept only the default temperature; omit when 1.0.
    if temperature != 1.0:
        payload["temperature"] = temperature
    data = _post(
        f"{base_url.rstrip('/')}/chat/completions",
        payload,
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    return {
        "text": (data["choices"][0]["message"].get("content") or "").strip(),
        "usage": data.get("usage", {}),
        "resolved_model": data.get("model", model),
    }


def call_anthropic(model: str, system: str, user: str, temperature: float,
                   base_url: str, api_key: str, max_tokens: int,
                   json_mode: bool = False) -> dict:
    payload = {
        "model": model,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = _post(
        f"{base_url.rstrip('/')}/messages",
        payload,
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return {
        "text": text.strip(),
        "usage": data.get("usage", {}),
        "resolved_model": data.get("model", model),
    }


def call_gemini(model: str, system: str, user: str, temperature: float,
                base_url: str, api_key: str, max_tokens: int,
                json_mode: bool = False) -> dict:
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    url = f"{base_url.rstrip('/')}/models/{model}:generateContent?key={api_key}"
    data = _post(url, payload, {"Content-Type": "application/json"})
    text = ""
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            text += part.get("text", "")
    return {
        "text": text.strip(),
        "usage": data.get("usageMetadata", {}),
        "resolved_model": data.get("modelVersion", model),
    }


def call_ollama(model: str, system: str, user: str, temperature: float,
                base_url: str, api_key: str, max_tokens: int,
                json_mode: bool = False) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    # Constrained decoding. Necessary for reasoning-tuned models, which
    # otherwise emit a long prose preamble and are truncated before reaching the
    # JSON. It makes the format-compliance measurement vacuous for that run, so
    # the flag is recorded per call and reported alongside the results.
    if json_mode:
        payload["format"] = "json"
    # Reasoning models (Qwen3, DeepSeek-R1, ...) emit a long chain of thought by
    # default, which the task does not want and which would blow the token
    # budget. Ollama exposes an explicit switch; older servers reject the field,
    # so fall back to a plain call if it is not understood.
    think_models = ("qwen3", "deepseek-r1", "magistral", "gpt-oss")
    wants_think_off = any(k in model.lower() for k in think_models)
    if wants_think_off:
        payload["think"] = False

    url = f"{base_url.rstrip('/')}/api/chat"
    try:
        data = _post(url, payload, {"Content-Type": "application/json"})
    except urllib.error.HTTPError:
        if not wants_think_off:
            raise
        payload.pop("think", None)
        data = _post(url, payload, {"Content-Type": "application/json"})

    msg = data.get("message", {}) or {}
    text = (msg.get("content") or "").strip()
    return {
        "text": text,
        "usage": {
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            # Recorded so a reasoning model's hidden tokens are not invisible.
            "thinking_chars": len(msg.get("thinking") or ""),
        },
        "resolved_model": data.get("model", model),
    }



def call_bedrock(model: str, system: str, user: str, temperature: float,
                 base_url: str, api_key: str, max_tokens: int,
                 json_mode: bool = False) -> dict:
    """
    Amazon Bedrock via the Converse API, signed with SigV4 from the standard
    library (see bedrock_sigv4.py). Converse is used rather than InvokeModel
    because it presents one request shape across every model family, so models
    from different vendors receive byte-identical inputs.

    Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY /
    AWS_SESSION_TOKEN and AWS_REGION, and `base_url` is reused to carry an
    explicit region override when one is given.
    """
    from bedrock_sigv4 import converse

    region = base_url if base_url and "." not in base_url else None
    return converse(model, system, user, temperature, max_tokens,
                    region=region, json_mode=json_mode)


PROVIDERS = {
    "openai": (call_openai, "https://api.openai.com/v1", "OPENAI_API_KEY"),
    "anthropic": (call_anthropic, "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    "gemini": (call_gemini, "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    "ollama": (call_ollama, "http://localhost:11434", ""),
    # Bedrock authenticates with SigV4, not a bearer token, so it declares no
    # key env var here; credentials are validated inside the adapter.
    "bedrock": (call_bedrock, "", ""),
}


# --------------------------------------------------------------------------
# response parsing
# --------------------------------------------------------------------------
def opt_int(value) -> int | None:
    """Coerce a CSV cell to int, treating blanks and absent values as unknown."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_response(text: str) -> dict:
    """
    Extract the two binary labels and classify how the response deviated from
    the requested format. The deviation taxonomy feeds the hallucination
    analysis, so it distinguishes *why* a parse failed.
    """
    out = {
        "incorrect": None,
        "incomplete": None,
        "parse_ok": False,
        "failure_mode": None,
        "extra_prose": False,
    }
    if not text:
        out["failure_mode"] = "empty_response"
        return out

    stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()

    obj = None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\}", stripped, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                obj = None
            if obj is not None and len(stripped) > len(m.group(0)) + 5:
                out["extra_prose"] = True

    if obj is None:
        # last resort: key: value scraping, e.g. {incorrect: 1, incomplete: 0}
        pairs = dict(re.findall(r"['\"]?(incorrect|incomplete)['\"]?\s*[:=]\s*['\"]?([01])", stripped, re.I))
        if len(pairs) == 2:
            out.update(
                incorrect=int(pairs["incorrect"]),
                incomplete=int(pairs["incomplete"]),
                parse_ok=True,
                failure_mode="non_json_but_recoverable",
            )
            return out
        out["failure_mode"] = "unparseable"
        return out

    if not isinstance(obj, dict):
        out["failure_mode"] = "json_not_object"
        return out

    keys = {k.lower(): v for k, v in obj.items()}
    missing = [k for k in ("incorrect", "incomplete") if k not in keys]
    if missing:
        out["failure_mode"] = f"missing_key:{','.join(missing)}"
        return out

    unexpected = set(keys) - {"incorrect", "incomplete"}
    vals = {}
    for k in ("incorrect", "incomplete"):
        v = keys[k]
        if isinstance(v, bool):
            vals[k] = int(v)
        elif isinstance(v, (int, float)) and v in (0, 1):
            vals[k] = int(v)
        elif isinstance(v, str) and v.strip() in ("0", "1"):
            vals[k] = int(v.strip())
        else:
            out["failure_mode"] = f"out_of_domain_value:{k}={v!r}"
            return out

    out.update(incorrect=vals["incorrect"], incomplete=vals["incomplete"], parse_ok=True)
    if unexpected:
        out["failure_mode"] = f"extra_keys:{','.join(sorted(map(str, unexpected)))}"
    return out


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    ap.add_argument("--model", required=True)
    ap.add_argument("--dataset", type=pathlib.Path, default=HERE / "data" / "eval_set_natural.csv")
    ap.add_argument("--out", type=pathlib.Path, default=HERE / "runs")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--repeats", type=int, default=1,
                    help="calls per app; >1 enables the self-consistency probe")
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--max-retries", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls")
    ap.add_argument("--tag", default="", help="suffix for the output filename")
    ap.add_argument("--json-mode", action="store_true",
                    help="constrain decoding to JSON; required for "
                         "reasoning-tuned models, and makes the format-"
                         "compliance measurement vacuous for this run")
    args = ap.parse_args()

    import csv

    fn, default_base, key_env = PROVIDERS[args.provider]
    base_url = args.base_url or default_base
    api_key = os.environ.get(key_env, "") if key_env else ""
    if key_env and not api_key:
        sys.exit(f"Environment variable {key_env} is not set.")

    with args.dataset.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit:
        rows = rows[: args.limit]

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = re.sub(r"[^A-Za-z0-9._-]", "_", args.model)
    tag = f"_{args.tag}" if args.tag else ""
    out_path = args.out / f"{args.provider}_{safe_model}{tag}_{stamp}.jsonl"
    meta_path = out_path.with_suffix(".meta.json")

    meta = {
        "provider": args.provider,
        "model_requested": args.model,
        "base_url": base_url,
        "dataset": str(args.dataset),
        "n_apps": len(rows),
        "repeats": args.repeats,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "json_mode": args.json_mode,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "system_prompt": SYSTEM_PROMPT,
        "user_template": USER_TEMPLATE,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    n_ok = n_fail = n_err = 0
    t_start = time.time()
    with out_path.open("w", encoding="utf-8") as sink:
        for i, row in enumerate(rows, 1):
            user = USER_TEMPLATE.format(
                data_safety=row["data_safety_content"],
                privacy_policy=row["privacy_policy_content"],
            )
            for rep in range(args.repeats):
                record = {
                    "app_id": row["app_id"],
                    "app_package": row["app_package"],
                    "category": row["category_name"],
                    "repeat": rep,
                    # Probe files deliberately leave a target blank where no
                    # determinate reference answer exists; keep that as null.
                    "y_incorrect": opt_int(row.get("y_incorrect")),
                    "y_incomplete": opt_int(row.get("y_incomplete")),
                    "provider": args.provider,
                    "model_requested": args.model,
                    "temperature": args.temperature,
                    "json_mode": args.json_mode,
                }
                if row.get("probe"):
                    record["probe"] = row["probe"]
                    record["probe_detail"] = row.get("probe_detail", "")
                delay = 2.0
                for attempt in range(args.max_retries):
                    t0 = time.time()
                    try:
                        res = fn(args.model, SYSTEM_PROMPT, user, args.temperature,
                                 base_url, api_key, args.max_tokens,
                                 args.json_mode)
                        record["latency_s"] = round(time.time() - t0, 3)
                        record["raw_response"] = res["text"]
                        record["usage"] = res["usage"]
                        record["resolved_model"] = res["resolved_model"]
                        record["api_error"] = None
                        record.update(parse_response(res["text"]))
                        break
                    except urllib.error.HTTPError as e:
                        detail = e.read().decode("utf-8", "replace")[:400]
                        record["api_error"] = f"HTTP {e.code}: {detail}"
                        if e.code in (429, 500, 502, 503, 504) and attempt < args.max_retries - 1:
                            time.sleep(delay)
                            delay *= 2
                            continue
                        break
                    except Exception as e:  # noqa: BLE001 - record and continue
                        record["api_error"] = f"{type(e).__name__}: {e}"
                        if attempt < args.max_retries - 1:
                            time.sleep(delay)
                            delay *= 2
                            continue
                        break

                if record.get("api_error"):
                    n_err += 1
                elif record.get("parse_ok"):
                    n_ok += 1
                else:
                    n_fail += 1

                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                sink.flush()
                if args.sleep:
                    time.sleep(args.sleep)

            if i % 25 == 0 or i == len(rows):
                el = time.time() - t_start
                print(f"  {i}/{len(rows)} apps | parsed {n_ok} | unparsed {n_fail} "
                      f"| errors {n_err} | {el:.0f}s", flush=True)

    meta.update(
        finished_utc=datetime.now(timezone.utc).isoformat(),
        elapsed_s=round(time.time() - t_start, 1),
        n_calls=n_ok + n_fail + n_err,
        n_parsed=n_ok,
        n_unparsed=n_fail,
        n_api_errors=n_err,
    )
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
