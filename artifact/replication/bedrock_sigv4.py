#!/usr/bin/env python3
"""
bedrock_sigv4.py

Minimal AWS SigV4 request signing and an Amazon Bedrock Converse client, using
only the Python standard library.

Why hand-rolled rather than boto3
---------------------------------
The replication harness deliberately has no third-party dependencies, so that a
reviewer can run it with nothing but a Python interpreter. SigV4 is a fully
specified, deterministic algorithm, so implementing it costs ~80 lines and keeps
that property. If boto3 is available and preferred, the same requests can be
issued through it without changing anything else in the harness.

Why the Converse API rather than InvokeModel
--------------------------------------------
Converse presents one request and response shape across every Bedrock model
family (Anthropic, Amazon Nova, Meta Llama, Mistral, DeepSeek, Cohere).
InvokeModel requires a different body schema per vendor. Since the point of this
experiment is to compare models on identical inputs, a uniform surface removes a
whole class of confound.

Credentials are read from the environment in the usual order:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, optional AWS_SESSION_TOKEN
    AWS_REGION (or AWS_DEFAULT_REGION)
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ALGORITHM = "AWS4-HMAC-SHA256"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _hmac(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def sign_request(
    method: str,
    url: str,
    body: bytes,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
    session_token: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return the headers needed to authenticate one SigV4 request."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    # Each path segment is encoded, but the separators are not.
    canonical_uri = urllib.parse.quote(parsed.path or "/", safe="/-_.~")
    canonical_query = parsed.query or ""

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = _sha256_hex(body)

    headers = {
        "content-type": "application/json",
        "host": host,
        "x-amz-date": amz_date,
    }
    if session_token:
        headers["x-amz-security-token"] = session_token
    if extra_headers:
        headers.update({k.lower(): v for k, v in extra_headers.items()})

    signed_header_names = ";".join(sorted(headers))
    canonical_headers = "".join(
        f"{k}:{headers[k].strip()}\n" for k in sorted(headers)
    )
    canonical_request = "\n".join([
        method, canonical_uri, canonical_query,
        canonical_headers, signed_header_names, payload_hash,
    ])

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        ALGORITHM, amz_date, credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])

    signature = hmac.new(
        _signing_key(secret_key, date_stamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    out = {k: v for k, v in headers.items()}
    out["Authorization"] = (
        f"{ALGORITHM} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_header_names}, Signature={signature}"
    )
    return out


def load_dotenv(path: str | None = None) -> None:
    """
    Populate os.environ from a .env file sitting beside this module.

    Real environment variables win, so an exported credential is never silently
    overridden by a stale file. Values may be quoted or bare; blank values are
    ignored so an unused AWS_SESSION_TOKEN line does no harm.
    """
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(p):
        return
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # tolerate `export KEY=value` as well as `KEY=value`
            if key.startswith("export "):
                key = key[len("export "):].strip()
            val = val.strip().strip('"').strip("'")
            if val and not os.environ.get(key):
                os.environ[key] = val


def region_name() -> str:
    """The Bedrock region, from the environment or .env."""
    load_dotenv()
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or ""
    if not region:
        raise RuntimeError(
            "missing AWS_REGION. Set it in "
            + os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        )
    return region


def bearer_token() -> str | None:
    """
    An Amazon Bedrock API key, if one is configured.

    Bedrock API keys are bearer tokens rather than SigV4 credentials: they go in
    an `Authorization: Bearer` header, and they are scoped to the Bedrock and
    Bedrock Runtime actions only. See
    https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-use.html
    """
    load_dotenv()
    return os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or None


def credentials() -> tuple[str, str, str | None, str]:
    """Read SigV4 credentials and region from the environment or .env, or raise."""
    load_dotenv()
    ak = os.environ.get("AWS_ACCESS_KEY_ID", "")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    st = os.environ.get("AWS_SESSION_TOKEN") or None
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or ""
    missing = [n for n, v in
               (("AWS_ACCESS_KEY_ID", ak), ("AWS_SECRET_ACCESS_KEY", sk),
                ("AWS_REGION", region)) if not v]
    if missing:
        raise RuntimeError(
            "missing credentials: " + ", ".join(missing)
            + f"\nFill them into {os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')}"
              " or export them. If you have a Bedrock API key instead, set"
              " AWS_BEARER_TOKEN_BEDROCK."
        )
    return ak, sk, st, region


def _request(method: str, url: str, region: str, service: str,
             body: bytes = b"", timeout: int = 180) -> dict:
    """
    Issue one authenticated request, preferring a Bedrock API key when present
    and falling back to SigV4 signing otherwise. Both reach the same endpoints.
    """
    token = bearer_token()
    if token:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    else:
        ak, sk, st, _ = credentials()
        headers = sign_request(method, url, body, region, service, ak, sk, st)

    req = urllib.request.Request(
        url, data=body if body else None, headers=headers, method=method
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_models(region: str | None = None) -> list[dict]:
    """List the foundation models visible to these credentials."""
    region = region or region_name()
    url = f"https://bedrock.{region}.amazonaws.com/foundation-models"
    data = _request("GET", url, region, "bedrock")
    return data.get("modelSummaries", [])


def list_inference_profiles(region: str | None = None) -> list[dict]:
    """List cross-region inference profiles, which newer models require."""
    region = region or region_name()
    url = f"https://bedrock.{region}.amazonaws.com/inference-profiles"
    try:
        data = _request("GET", url, region, "bedrock")
    except urllib.error.HTTPError:
        return []
    return data.get("inferenceProfileSummaries", [])


# Current-generation Claude models reject `temperature` with a 400. Rather than
# hard-code a model list that will go stale, the first rejection is remembered
# and the call retried without it. Affected models then sample at their own
# default, which is noted where self-consistency is reported.
_NO_TEMPERATURE: set[str] = set()


def rejects_temperature(model_id: str) -> bool:
    """True if this model has been observed to reject an explicit temperature."""
    return model_id in _NO_TEMPERATURE


def converse(model_id: str, system: str, user: str, temperature: float,
             max_tokens: int, region: str | None = None,
             json_mode: bool = False) -> dict:
    """
    One Converse call. Returns {"text", "usage", "resolved_model"} so the shape
    matches the other provider adapters in run_benchmark.py.

    Newer models are served only through cross-region inference profiles, whose
    IDs carry a geography prefix (`us.`, `eu.`, `apac.`). Pass the profile ID.
    """
    region = region or region_name()
    url = (f"https://bedrock-runtime.{region}.amazonaws.com/model/"
           f"{urllib.parse.quote(model_id, safe='')}/converse")

    def build(with_temperature: bool) -> bytes:
        cfg: dict = {"maxTokens": max_tokens}
        if with_temperature:
            cfg["temperature"] = temperature
        payload: dict = {
            "messages": [{"role": "user", "content": [{"text": user}]}],
            "inferenceConfig": cfg,
        }
        if system:
            payload["system"] = [{"text": system}]
        return json.dumps(payload).encode("utf-8")

    send_temp = model_id not in _NO_TEMPERATURE
    try:
        data = _request("POST", url, region, "bedrock", build(send_temp))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code == 400 and "temperature" in detail.lower() and send_temp:
            _NO_TEMPERATURE.add(model_id)
            data = _request("POST", url, region, "bedrock", build(False))
        else:
            # Re-raise with the body attached; the caller records it verbatim.
            raise urllib.error.HTTPError(
                e.url, e.code, f"{e.reason}: {detail[:400]}", e.headers, None
            ) from None

    blocks = (data.get("output", {}).get("message", {}) or {}).get("content", []) or []
    text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))

    usage = data.get("usage", {}) or {}
    return {
        "text": text.strip(),
        "usage": {
            "input_tokens": usage.get("inputTokens"),
            "output_tokens": usage.get("outputTokens"),
            "total_tokens": usage.get("totalTokens"),
        },
        "resolved_model": model_id,
        "stop_reason": data.get("stopReason"),
    }


if __name__ == "__main__":
    # Quick connectivity and access check.
    import sys

    try:
        region = region_name()
        mode = "Bedrock API key (bearer)" if bearer_token() else None
        if mode is None:
            credentials()          # raises with guidance if SigV4 is incomplete
            mode = "SigV4 access key"
    except RuntimeError as e:
        sys.exit(f"{e}\n\nSet them, for example:\n"
                 "  export AWS_ACCESS_KEY_ID=...\n"
                 "  export AWS_SECRET_ACCESS_KEY=...\n"
                 "  export AWS_REGION=us-east-1")

    print(f"Region: {region}   |   Auth: {mode}\n")
    models = list_models()
    print(f"{len(models)} foundation models visible.\n")

    interesting = ("anthropic", "amazon.nova", "meta.llama", "mistral", "deepseek", "cohere")
    rows = [m for m in models
            if any(m.get("modelId", "").startswith(p) for p in interesting)
            and "TEXT" in (m.get("outputModalities") or [])]
    for m in sorted(rows, key=lambda r: r.get("modelId", "")):
        streaming = "stream" if m.get("responseStreamingSupported") else "     "
        print(f"  {m.get('modelId',''):<60} {streaming}  {m.get('modelName','')}")

    profiles = list_inference_profiles()
    if profiles:
        print(f"\n{len(profiles)} inference profiles (use these IDs for newer models):")
        for p in sorted(profiles, key=lambda r: r.get("inferenceProfileId", ""))[:40]:
            print(f"  {p.get('inferenceProfileId',''):<60} {p.get('inferenceProfileName','')}")
