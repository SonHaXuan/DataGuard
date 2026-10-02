#!/usr/bin/env python3
"""
score.py

Score one or more benchmark runs produced by run_benchmark.py.

Reports the four metrics used in the original manuscript (precision, recall,
F1, accuracy) alongside the prevalence-aware metrics the revised manuscript
adds, because on this task accuracy alone cannot separate a discriminating
classifier from one that simply flags every app.

Unparsed responses are never silently dropped. They are reported, and the
`--unparsed` policy decides how they are scored:

    exclude  omit them from the metrics and report the coverage loss (default)
    negative treat them as a prediction of 0
    positive treat them as a prediction of 1

Usage
-----
    python3 score.py runs/*.jsonl
    python3 score.py runs/*.jsonl --unparsed negative --out results/scores.json
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
from collections import Counter, defaultdict

TARGETS = ("incorrect", "incomplete")


def mcc(tp: int, fp: int, fn: int, tn: int) -> float | None:
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return None if den == 0 else (tp * tn - fp * fn) / den


def kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    n = tp + fp + fn + tn
    if n == 0:
        return None
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def metrics(pairs: list[tuple[int, int]]) -> dict:
    """pairs: list of (y_true, y_pred) with values in {0,1}."""
    tp = sum(1 for y, p in pairs if y == 1 and p == 1)
    fp = sum(1 for y, p in pairs if y == 0 and p == 1)
    fn = sum(1 for y, p in pairs if y == 1 and p == 0)
    tn = sum(1 for y, p in pairs if y == 0 and p == 0)
    n = len(pairs)
    pos = tp + fn
    neg = fp + tn

    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / pos if pos else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else (0.0 if prec is not None and rec is not None else None)
    acc = (tp + tn) / n if n else None
    spec = tn / neg if neg else None
    bal = (0.5 * (rec + spec)) if (rec is not None and spec is not None) else None
    m = mcc(tp, fp, fn, tn)
    k = kappa(tp, fp, fn, tn)

    prevalence = pos / n if n else None
    # Accuracy of the best trivial constant classifier.
    baseline = max(prevalence, 1 - prevalence) if prevalence is not None else None

    def r3(x):
        return None if x is None else round(x, 3)

    return {
        "n": n, "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "prevalence": r3(prevalence),
        "P": r3(prec), "R": r3(rec), "F1": r3(f1), "A": r3(acc),
        "specificity": r3(spec), "balanced_accuracy": r3(bal),
        "MCC": r3(m), "kappa": r3(k),
        "majority_baseline_A": r3(baseline),
        "A_minus_baseline": r3(None if (acc is None or baseline is None) else acc - baseline),
        "predicted_positive_rate": r3((tp + fp) / n if n else None),
    }


def load(paths: list[pathlib.Path]) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = defaultdict(list)
    for p in paths:
        recs = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not recs:
            continue
        label = recs[0].get("resolved_model") or recs[0].get("model_requested") or p.stem
        runs[f"{label} [{p.name}]"] = recs
    return runs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=pathlib.Path)
    ap.add_argument("--unparsed", choices=["exclude", "negative", "positive"], default="exclude")
    ap.add_argument("--repeat", type=int, default=0, help="which repeat index to score")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    all_scores = {}
    for name, recs in load(args.runs).items():
        recs = [r for r in recs if r.get("repeat", 0) == args.repeat]
        if not recs:
            continue
        n_total = len(recs)
        n_api_err = sum(1 for r in recs if r.get("api_error"))
        n_unparsed = sum(1 for r in recs if not r.get("api_error") and not r.get("parse_ok"))

        entry = {
            "n_calls": n_total,
            "n_api_errors": n_api_err,
            "n_unparsed": n_unparsed,
            "parse_rate": round((n_total - n_api_err - n_unparsed) / n_total, 3) if n_total else None,
            "unparsed_policy": args.unparsed,
            "failure_modes": dict(
                Counter(r.get("failure_mode") for r in recs if r.get("failure_mode"))
            ),
            "targets": {},
        }

        for target in TARGETS:
            pairs = []
            for r in recs:
                if r.get("api_error"):
                    continue
                y = r.get(f"y_{target}")
                if y is None:
                    continue
                p = r.get(target)
                if p is None:
                    if args.unparsed == "exclude":
                        continue
                    p = 1 if args.unparsed == "positive" else 0
                pairs.append((int(y), int(p)))
            if pairs:
                entry["targets"][target] = metrics(pairs)

        all_scores[name] = entry

    # ---------------- console table --------------------------------------
    hdr = (f"{'Model / run':<46}{'Target':<12}{'n':>5}{'P':>7}{'R':>7}{'F1':>7}"
           f"{'A':>7}{'Spec':>7}{'BalA':>7}{'MCC':>7}{'dA':>7}{'parse':>7}")
    print(hdr)
    print("-" * len(hdr))
    for name, e in all_scores.items():
        short = name if len(name) <= 44 else name[:41] + "..."
        for target, m in e["targets"].items():
            def f(x):
                return "  --  " if x is None else f"{x:6.3f}"
            print(f"{short:<46}{target:<12}{m['n']:>5}{f(m['P'])}{f(m['R'])}{f(m['F1'])}"
                  f"{f(m['A'])}{f(m['specificity'])}{f(m['balanced_accuracy'])}"
                  f"{f(m['MCC'])}{f(m['A_minus_baseline'])}{f(e['parse_rate'])}")
            short = ""
    print()
    for name, e in all_scores.items():
        if e["failure_modes"]:
            print(f"{name}: format deviations -> {e['failure_modes']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(all_scores, indent=2), encoding="utf-8")
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
