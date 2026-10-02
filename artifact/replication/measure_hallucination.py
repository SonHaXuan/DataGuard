#!/usr/bin/env python3
"""
measure_hallucination.py

Quantify the failure modes that the submitted manuscript attributed to
"hallucination" without evidence, using the controlled probes built by
make_probes.py plus repeated sampling of the unperturbed set.

Four measurable quantities replace the unsupported narrative:

  format violation rate
      Share of calls whose output did not conform to the requested JSON schema,
      broken down by deviation type. An instruction-following failure, directly
      observable.

  unsupported assertion rate            (null probe)
      Share of calls that answered incorrect = 1 when the privacy policy shown
      to the model was a placeholder containing no data-practice statement. The
      reference answer is 0 by construction, so a 1 asserts the presence of
      content that is absent from the input. This is the narrowest defensible
      operationalisation of hallucination for a binary task.

  grounding failure rate                (inject probe)
      Share of calls that answered incorrect = 0 after an explicit disclosure of
      an undeclared data type was appended to the policy. The reference answer is
      1 by construction, so a 0 means the verdict did not depend on the evidence.

  instability rate                      (shuffle probe, and repeats)
      Share of apps whose label changed under a meaning-preserving reordering of
      the policy sentences, and share whose label changed across identical
      repeated calls. Neither can be reasoning; both bound how much of any
      reported metric difference is noise.

Usage
-----
    python3 measure_hallucination.py \
        --base runs/openai_gpt-5_20260926T120000Z.jsonl \
        --null runs/openai_gpt-5_null_*.jsonl \
        --inject runs/openai_gpt-5_inject_*.jsonl \
        --shuffle runs/openai_gpt-5_shuffle_*.jsonl \
        --out results/hallucination_gpt-5.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter, defaultdict


def load(paths: list[pathlib.Path]) -> list[dict]:
    recs = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(json.loads(line))
    return recs


def format_stats(recs: list[dict]) -> dict:
    usable = [r for r in recs if not r.get("api_error")]
    n = len(usable)
    if n == 0:
        return {"n_calls": 0}
    bad = [r for r in usable if not r.get("parse_ok")]
    # parse_ok records can still carry a deviation note (extra keys, prose, ...)
    deviating = [r for r in usable if r.get("failure_mode")]
    return {
        "n_calls": n,
        "n_api_errors": sum(1 for r in recs if r.get("api_error")),
        "n_unparseable": len(bad),
        "unparseable_rate": round(len(bad) / n, 4),
        "n_any_format_deviation": len(deviating),
        "format_deviation_rate": round(len(deviating) / n, 4),
        "deviation_breakdown": dict(Counter(r["failure_mode"] for r in deviating)),
        "n_extra_prose": sum(1 for r in usable if r.get("extra_prose")),
    }


def probe_stats(recs: list[dict], target: str, reference: int) -> dict:
    """Share of predictions that contradict a reference fixed by construction."""
    usable = [
        r for r in recs
        if not r.get("api_error") and r.get(target) is not None
    ]
    n = len(usable)
    if n == 0:
        return {"n": 0}
    violations = [r for r in usable if int(r[target]) != reference]
    by_cat = defaultdict(lambda: [0, 0])
    for r in usable:
        c = r.get("category", "?")
        by_cat[c][1] += 1
        if int(r[target]) != reference:
            by_cat[c][0] += 1
    return {
        "n": n,
        "reference_answer": reference,
        "n_violations": len(violations),
        "violation_rate": round(len(violations) / n, 4),
        "by_category": {
            c: {"violations": v[0], "n": v[1], "rate": round(v[0] / v[1], 3)}
            for c, v in sorted(by_cat.items())
        },
        "example_app_packages": [r.get("app_package") for r in violations[:10]],
    }


def flip_stats(base: list[dict], other: list[dict], targets=("incorrect", "incomplete")) -> dict:
    """Label change rate between two runs over the same apps."""
    def index(recs):
        out = {}
        for r in recs:
            if r.get("api_error") or not r.get("parse_ok"):
                continue
            out[(r["app_id"], r.get("repeat", 0))] = r
        return out

    a, b = index(base), index(other)
    # compare on app_id, using repeat 0 of each
    keys = {k[0] for k in a} & {k[0] for k in b}
    out = {"n_compared_apps": len(keys)}
    for t in targets:
        flips = 0
        n = 0
        for app in keys:
            ra, rb = a.get((app, 0)), b.get((app, 0))
            if ra is None or rb is None:
                continue
            if ra.get(t) is None or rb.get(t) is None:
                continue
            n += 1
            if int(ra[t]) != int(rb[t]):
                flips += 1
        out[t] = {
            "n": n,
            "n_flips": flips,
            "flip_rate": round(flips / n, 4) if n else None,
        }
    return out


def self_consistency(recs: list[dict], targets=("incorrect", "incomplete")) -> dict:
    """Agreement across repeated identical calls to the same app."""
    by_app = defaultdict(list)
    for r in recs:
        if r.get("api_error") or not r.get("parse_ok"):
            continue
        by_app[r["app_id"]].append(r)
    multi = {k: v for k, v in by_app.items() if len(v) >= 2}
    out = {"n_apps_with_repeats": len(multi)}
    if not multi:
        return out
    for t in targets:
        unstable = 0
        counted = 0
        for _app, rs in multi.items():
            vals = [r.get(t) for r in rs if r.get(t) is not None]
            if len(vals) < 2:
                continue
            counted += 1
            if len(set(vals)) > 1:
                unstable += 1
        out[t] = {
            "n_apps": counted,
            "n_unstable": unstable,
            "instability_rate": round(unstable / counted, 4) if counted else None,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="*", type=pathlib.Path, default=[])
    ap.add_argument("--null", nargs="*", type=pathlib.Path, default=[])
    ap.add_argument("--inject", nargs="*", type=pathlib.Path, default=[])
    ap.add_argument("--shuffle", nargs="*", type=pathlib.Path, default=[])
    ap.add_argument("--repeats", nargs="*", type=pathlib.Path, default=[],
                    help="run produced with --repeats > 1")
    ap.add_argument("--label", default="model")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    report: dict = {"label": args.label}

    base = load(args.base) if args.base else []
    if base:
        report["format_compliance_base"] = format_stats(base)

    if args.null:
        recs = load(args.null)
        report["format_compliance_null"] = format_stats(recs)
        report["unsupported_assertion"] = probe_stats(recs, "incorrect", reference=0)

    if args.inject:
        recs = load(args.inject)
        report["format_compliance_inject"] = format_stats(recs)
        report["grounding_failure"] = probe_stats(recs, "incorrect", reference=1)

    if args.shuffle and base:
        recs = load(args.shuffle)
        report["order_instability"] = flip_stats(base, recs)

    if args.repeats:
        report["self_consistency"] = self_consistency(load(args.repeats))

    # ---------------- console ------------------------------------------
    print(f"=== Hallucination and stability probes: {args.label} ===\n")
    fc = report.get("format_compliance_base")
    if fc and fc.get("n_calls"):
        print(f"Format: {fc['n_calls']} calls | unparseable "
              f"{fc['unparseable_rate']:.3%} | any deviation "
              f"{fc['format_deviation_rate']:.3%}")
        if fc["deviation_breakdown"]:
            print(f"        breakdown: {fc['deviation_breakdown']}")
    ua = report.get("unsupported_assertion")
    if ua and ua.get("n"):
        print(f"\nNull probe (policy contains nothing; reference incorrect = 0):")
        print(f"  unsupported assertion rate = {ua['violation_rate']:.3%} "
              f"({ua['n_violations']}/{ua['n']})")
    gf = report.get("grounding_failure")
    if gf and gf.get("n"):
        print(f"\nInject probe (explicit undeclared disclosure added; reference "
              f"incorrect = 1):")
        print(f"  grounding failure rate = {gf['violation_rate']:.3%} "
              f"({gf['n_violations']}/{gf['n']})")
    oi = report.get("order_instability")
    if oi:
        print(f"\nSentence-order probe over {oi['n_compared_apps']} apps:")
        for t in ("incorrect", "incomplete"):
            if t in oi and oi[t]["flip_rate"] is not None:
                print(f"  {t}: flip rate {oi[t]['flip_rate']:.3%} "
                      f"({oi[t]['n_flips']}/{oi[t]['n']})")
    sc = report.get("self_consistency")
    if sc and sc.get("n_apps_with_repeats"):
        print(f"\nRepeated identical calls over {sc['n_apps_with_repeats']} apps:")
        for t in ("incorrect", "incomplete"):
            if t in sc and sc[t]["instability_rate"] is not None:
                print(f"  {t}: instability {sc[t]['instability_rate']:.3%} "
                      f"({sc[t]['n_unstable']}/{sc[t]['n_apps']})")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
