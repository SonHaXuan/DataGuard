#!/usr/bin/env python3
"""
01_reconstruct_confusion.py

Recover the exact confusion matrix (TP, FP, FN, TN) behind every published
Precision/Recall/F1/Accuracy figure in the originally submitted manuscript.

Why this is needed
------------------
Reviewer 1, Major Issue 3 ("Lack of error analysis") notes that the paper reports
only aggregate metrics and gives no insight into *how* the models fail. The
per-app prediction files from the 2024 runs are no longer available in the
project tree (data-guard-experiment/output/**/output.json are 0 bytes), but the
confusion matrix is fully determined by the four published metrics plus the known
test-set size, so the error counts can be recovered exactly and without any
assumption.

Derivation
----------
With N the test-set size and the "defect" class (Incorrect / Incomplete) as the
positive class:

    P = TP / (TP + FP)          =>  FP = TP (1 - P) / P
    R = TP / (TP + FN)          =>  FN = TP (1 - R) / R
    A = (TP + TN) / N           =>  TN = N*A - TP
    TP + FP + FN + TN = N

Substituting the first three into the fourth:

    TP [ (1-P)/P + (1-R)/R ] = N (1 - A)

    TP = N (1 - A) / [ (1-P)/P + (1-R)/R ]

The recovered counts must be near-integers; the residual from the nearest
integer is reported as an internal-consistency check on the published table.

Outputs
-------
    results/confusion_reconstructed.csv    one row per (case, category)
    results/confusion_reconstructed.json   same, machine readable
"""

from __future__ import annotations

import csv
import json
import pathlib

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

N_TEST = 150  # 150-app held-out test set, identical across all eight cases

# Published metrics, transcribed verbatim from the submitted manuscript:
#   Table "Results for Case 01 and Case 02"      (sn-article.tex, tab:case01_02)
#   Table "Results for Case 03, 04 and 05"       (sn-article.tex, tab:case03_04_05)
#   Table "Results for Case 06, 07 and 08"       (sn-article.tex, tab:case06_07_08)
# (P, R, F1, A)
PUBLISHED = {
    "Case 01": {
        "label": "Zero-shot, GPT-3.5",
        "train": "none",
        "labeller": "n/a",
        "n_train": 0,
        "Incorrect": (0.942, 0.825, 0.879, 0.793),
        "Incomplete": (0.828, 0.595, 0.692, 0.573),
    },
    "Case 02": {
        "label": "Fine-tuned, manual labels",
        "train": "150 apps",
        "labeller": "human experts",
        "n_train": 150,
        "Incorrect": (0.951, 0.993, 0.971, 0.947),
        "Incomplete": (0.844, 0.983, 0.908, 0.840),
    },
    "Case 03": {
        "label": "Fine-tuned, GPT-4 labels",
        "train": "150 apps",
        "labeller": "GPT-4",
        "n_train": 150,
        "Incorrect": (0.981, 0.759, 0.856, 0.767),
        "Incomplete": (0.849, 0.975, 0.908, 0.840),
    },
    "Case 04": {
        "label": "Fine-tuned, GPT-4o labels",
        "train": "150 apps",
        "labeller": "GPT-4o",
        "n_train": 150,
        "Incorrect": (0.919, 1.000, 0.958, 0.920),
        "Incomplete": (0.807, 1.000, 0.883, 0.807),
    },
    "Case 05": {
        "label": "Fine-tuned, Gemini 1.5 labels",
        "train": "150 apps",
        "labeller": "Gemini 1.5",
        "n_train": 150,
        "Incorrect": (0.938, 1.000, 0.980, 0.940),
        "Incomplete": (0.834, 1.000, 0.910, 0.840),
    },
    "Case 06": {
        "label": "Fine-tuned, GPT-4 labels",
        "train": "450 apps",
        "labeller": "GPT-4",
        "n_train": 450,
        "Incorrect": (0.971, 0.730, 0.833, 0.733),
        "Incomplete": (0.877, 0.942, 0.908, 0.847),
    },
    "Case 07": {
        "label": "Fine-tuned, GPT-4o labels",
        "train": "450 apps",
        "labeller": "GPT-4o",
        "n_train": 450,
        "Incorrect": (0.932, 1.000, 0.965, 0.933),
        "Incomplete": (0.857, 0.992, 0.920, 0.860),
    },
    "Case 08": {
        "label": "Fine-tuned, Gemini 1.5 labels",
        "train": "450 apps",
        "labeller": "Gemini 1.5",
        "n_train": 450,
        "Incorrect": (0.945, 1.000, 0.972, 0.947),
        "Incomplete": (0.851, 0.992, 0.916, 0.853),
    },
}


def reconstruct(p: float, r: float, a: float, n: int = N_TEST) -> dict:
    """Recover TP/FP/FN/TN from precision, recall, accuracy and test-set size."""
    # Perfect recall means FN = 0, which makes the (1-R)/R term vanish; handle
    # it directly to avoid a division by zero.
    denom = (1.0 - p) / p + ((1.0 - r) / r if r < 1.0 else 0.0)
    tp_raw = n * (1.0 - a) / denom if denom > 0 else float("nan")

    fp_raw = tp_raw * (1.0 - p) / p
    fn_raw = tp_raw * (1.0 - r) / r if r < 1.0 else 0.0
    tn_raw = n * a - tp_raw

    tp, fp, fn, tn = (round(x) for x in (tp_raw, fp_raw, fn_raw, tn_raw))
    residual = max(
        abs(tp_raw - tp), abs(fp_raw - fp), abs(fn_raw - fn), abs(tn_raw - tn)
    )

    support_pos = tp + fn          # true number of defective apps in the test set
    support_neg = fp + tn          # true number of clean apps
    predicted_pos = tp + fp

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "total": tp + fp + fn + tn,
        "errors": fp + fn,
        "support_positive": support_pos,
        "support_negative": support_neg,
        "predicted_positive": predicted_pos,
        # Predicted-positive rate vs. true-positive rate: >1 means the model
        # over-flags defects, <1 means it under-flags them.
        "flag_ratio": round(predicted_pos / support_pos, 3) if support_pos else None,
        # Specificity = TN / (TN + FP): ability to leave compliant apps alone.
        "specificity": round(tn / support_neg, 3) if support_neg else None,
        "balanced_accuracy": (
            round(0.5 * (tp / support_pos + tn / support_neg), 3)
            if support_pos and support_neg
            else None
        ),
        "reconstruction_residual": round(residual, 3),
    }


def main() -> None:
    rows = []
    for case, meta in PUBLISHED.items():
        for category in ("Incorrect", "Incomplete"):
            p, r, f1, a = meta[category]
            rec = reconstruct(p, r, a)
            rows.append(
                {
                    "case": case,
                    "configuration": meta["label"],
                    "training_set": meta["train"],
                    "label_source": meta["labeller"],
                    "n_train": meta["n_train"],
                    "category": category,
                    "P": p,
                    "R": r,
                    "F1": f1,
                    "A": a,
                    **rec,
                }
            )

    # csv.DictWriter, not manual joining: configuration labels contain commas.
    header = list(rows[0].keys())
    out_csv = RESULTS / "confusion_reconstructed.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=header, restval="")
        wr.writeheader()
        for row in rows:
            wr.writerow({k: ("" if v is None else v) for k, v in row.items()})

    (RESULTS / "confusion_reconstructed.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )

    # ---- console report -------------------------------------------------
    worst = max(r["reconstruction_residual"] for r in rows)
    print(f"Test-set size N = {N_TEST}; worst reconstruction residual = {worst:.3f}")
    print(
        "(residuals well below 0.5 confirm the published metrics are mutually "
        "consistent with integer error counts)\n"
    )

    fmt = "{:<9}{:<11}{:>5}{:>5}{:>5}{:>5}{:>8}{:>8}{:>7}{:>7}"
    print(
        fmt.format(
            "Case", "Category", "TP", "FP", "FN", "TN", "errors", "flagR", "spec", "balA"
        )
    )
    print("-" * 75)
    for row in rows:
        print(
            fmt.format(
                row["case"],
                row["category"],
                row["TP"],
                row["FP"],
                row["FN"],
                row["TN"],
                row["errors"],
                row["flag_ratio"],
                row["specificity"],
                row["balanced_accuracy"],
            )
        )

    print("\nClass support implied by the published metrics (should be stable "
          "across cases, since every case shares one test set):")
    for category in ("Incorrect", "Incomplete"):
        sup = sorted({r["support_positive"] for r in rows if r["category"] == category})
        print(f"  {category:<11} positives per case: {sup}")

    print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
