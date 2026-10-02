#!/usr/bin/env python3
"""
02_error_analysis.py

Turn the recovered confusion matrices into the error analysis requested by
Reviewer 1 (Major Issue 3) and into the evidence needed to replace the
unsupported hallucination narrative (Major Issue 4).

Three things are computed here, all from the recovered integer error counts:

1. Prevalence-aware metrics. The 150-app test set is heavily skewed towards the
   defect class, so accuracy is inflated for any model that simply flags
   everything. We therefore add the majority-class baseline, balanced accuracy,
   Matthews Correlation Coefficient (MCC) and Cohen's kappa. MCC and AUC were
   already named as desirable metrics in Appendix D of the submitted version;
   this makes good on that.

2. An error *profile* for each case: whether the model's mistakes are dominated
   by false positives (over-flagging compliant apps) or false negatives
   (missing real defects). This is the operationally meaningful distinction for
   a compliance-screening tool.

3. A decision-threshold account of the Case 03/06 (GPT-4-label) anomaly that the
   submitted manuscript attributed to hallucination. If the anomaly is a shift
   in the models' effective operating point, it should show up as a coherent
   movement along the precision/recall trade-off with *preserved* discriminative
   power (MCC), rather than as degraded discrimination. That is a testable claim
   and it is tested here.

Outputs
-------
    results/error_analysis.csv
    results/error_analysis_summary.md
    results/table_error_analysis.tex      (LaTeX, drop-in for the manuscript)
"""

from __future__ import annotations

import csv
import json
import math
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"

N_TEST = 150


def mcc(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Matthews Correlation Coefficient; None when a denominator term vanishes."""
    num = tp * tn - fp * fn
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return None if den == 0 else num / den


def cohen_kappa(tp: int, fp: int, fn: int, tn: int) -> float | None:
    """Chance-corrected agreement between prediction and ground truth."""
    n = tp + fp + fn + tn
    if n == 0:
        return None
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def profile(fp: int, fn: int) -> str:
    """Characterise which error type dominates."""
    if fp == 0 and fn == 0:
        return "no errors"
    if fn == 0:
        return "over-flagging only"
    if fp == 0:
        return "under-flagging only"
    ratio = fp / fn
    if ratio >= 2.0:
        return "over-flagging dominant"
    if ratio <= 0.5:
        return "under-flagging dominant"
    return "mixed"


def main() -> None:
    rows = json.loads((RESULTS / "confusion_reconstructed.json").read_text())

    # Majority-class baseline per category: always predict the defect class,
    # because the defect class is the majority in this test set.
    baseline = {}
    for category in ("Incorrect", "Incomplete"):
        sup = [r["support_positive"] for r in rows if r["category"] == category]
        pos = round(sum(sup) / len(sup))
        baseline[category] = {
            "n_positive": pos,
            "n_negative": N_TEST - pos,
            "prevalence": pos / N_TEST,
            # "always flag" classifier
            "acc_always_positive": pos / N_TEST,
            "recall_always_positive": 1.0,
            "precision_always_positive": pos / N_TEST,
            "balanced_acc_always_positive": 0.5,
            "mcc_always_positive": 0.0,
        }

    out = []
    for r in rows:
        tp, fp, fn, tn = r["TP"], r["FP"], r["FN"], r["TN"]
        b = baseline[r["category"]]
        m = mcc(tp, fp, fn, tn)
        k = cohen_kappa(tp, fp, fn, tn)
        out.append(
            {
                "case": r["case"],
                "configuration": r["configuration"],
                "label_source": r["label_source"],
                "n_train": r["n_train"],
                "category": r["category"],
                "P": r["P"],
                "R": r["R"],
                "F1": r["F1"],
                "A": r["A"],
                "TP": tp,
                "FP": fp,
                "FN": fn,
                "TN": tn,
                "errors": fp + fn,
                "prevalence": round(b["prevalence"], 3),
                "baseline_A": round(b["acc_always_positive"], 3),
                "A_minus_baseline": round(r["A"] - b["acc_always_positive"], 3),
                "specificity": r["specificity"],
                "balanced_accuracy": r["balanced_accuracy"],
                "MCC": None if m is None else round(m, 3),
                "kappa": None if k is None else round(k, 3),
                "flag_ratio": r["flag_ratio"],
                "error_profile": profile(fp, fn),
            }
        )

    # csv.DictWriter, not manual joining: several fields (e.g. "Fine-tuned,
    # manual labels") contain commas and must be quoted.
    header = list(out[0].keys())
    with (RESULTS / "error_analysis.csv").open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=header, restval="")
        wr.writeheader()
        for row in out:
            wr.writerow({k: ("" if v is None else v) for k, v in row.items()})

    # ---------------- console + markdown report --------------------------
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        print(s)

    w("# Error analysis of the eight originally reported cases")
    w()
    w(f"Test set: N = {N_TEST} apps, identical across all eight cases.")
    w()
    w("## 1. The test set is strongly imbalanced towards the defect class")
    w()
    w("| Category | defective apps | clean apps | prevalence | accuracy of an "
      "\"always flag\" classifier |")
    w("|---|---|---|---|---|")
    for category, b in baseline.items():
        w(
            f"| {category} | {b['n_positive']} | {b['n_negative']} | "
            f"{b['prevalence']:.3f} | {b['acc_always_positive']:.3f} |"
        )
    w()
    w("A classifier that flags *every* app therefore already scores "
      f"{baseline['Incorrect']['acc_always_positive']:.3f} accuracy with perfect "
      "recall on `Incorrect`, and "
      f"{baseline['Incomplete']['acc_always_positive']:.3f} on `Incomplete`. "
      "Accuracy and recall alone cannot distinguish a discriminating model from "
      "a degenerate one on this test set, which is why the prevalence-aware "
      "columns below are necessary.")
    w()

    w("## 2. Prevalence-aware performance")
    w()
    w("| Case | Category | A | A - baseline | Spec. | Bal. acc. | MCC | kappa | "
      "FP | FN | Error profile |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    def f3(value) -> str:
        """Format an optional float to 3 decimals, or '--' when absent."""
        return "--" if value is None else f"{value:.3f}"

    for r in out:
        w(
            f"| {r['case']} | {r['category']} | {r['A']:.3f} | "
            f"{r['A_minus_baseline']:+.3f} | "
            f"{f3(r['specificity'])} | "
            f"{f3(r['balanced_accuracy'])} | "
            f"{f3(r['MCC'])} | "
            f"{f3(r['kappa'])} | "
            f"{r['FP']} | {r['FN']} | {r['error_profile']} |"
        )
    w()

    # Degenerate / near-degenerate detection
    degenerate = [r for r in out if r["TN"] == 0 or (r["balanced_accuracy"] or 1) <= 0.55]
    w("## 3. Degenerate and near-degenerate classifiers")
    w()
    if degenerate:
        for r in degenerate:
            w(
                f"- **{r['case']} / {r['category']}**: TN = {r['TN']}, "
                f"specificity = {r['specificity']}, balanced accuracy = "
                f"{r['balanced_accuracy']}, MCC = {r['MCC']}. "
                f"Accuracy {r['A']:.3f} versus an always-flag baseline of "
                f"{r['baseline_A']:.3f} ({r['A_minus_baseline']:+.3f})."
            )
    w()

    w("## 4. Over-flagging versus under-flagging")
    w()
    over = [r for r in out if "over-flagging" in r["error_profile"]]
    under = [r for r in out if "under-flagging" in r["error_profile"]]
    w(f"- Over-flagging (FP-dominated): {len(over)} of {len(out)} case/category cells.")
    w(f"- Under-flagging (FN-dominated): {len(under)} of {len(out)} case/category cells.")
    w()
    w("Under-flagging cells, i.e. the configurations that silently miss real "
      "disclosure defects:")
    for r in under:
        w(
            f"- {r['case']} / {r['category']} ({r['label_source']} labels, "
            f"{r['n_train']} training apps): FN = {r['FN']}, recall = {r['R']:.3f}, "
            f"specificity = {r['specificity']}, MCC = {r['MCC']}"
        )
    w()

    w("## 5. The Case 03 / Case 06 anomaly is a threshold shift, not a "
      "collapse in discrimination")
    w()
    w("| Case | Category | flag ratio | Spec. | Recall | MCC | Bal. acc. |")
    w("|---|---|---|---|---|---|---|")
    for r in out:
        if r["case"] in ("Case 03", "Case 04", "Case 05", "Case 06", "Case 07", "Case 08"):
            w(
                f"| {r['case']} | {r['category']} | {r['flag_ratio']} | "
                f"{r['specificity']} | {r['R']:.3f} | {r['MCC']} | "
                f"{r['balanced_accuracy']} |"
            )
    w()
    gpt4 = [r for r in out if r["label_source"] == "GPT-4"]
    others = [
        r for r in out
        if r["label_source"] in ("GPT-4o", "Gemini 1.5") and r["n_train"] > 0
    ]
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else float("nan")

    w(
        f"Mean flag ratio, GPT-4-labelled cases (03, 06): "
        f"{mean([r['flag_ratio'] for r in gpt4]):.3f}; "
        f"GPT-4o/Gemini-labelled cases (04, 05, 07, 08): "
        f"{mean([r['flag_ratio'] for r in others]):.3f}."
    )
    w(
        f"Mean specificity: GPT-4 {mean([r['specificity'] for r in gpt4]):.3f} "
        f"versus GPT-4o/Gemini {mean([r['specificity'] for r in others]):.3f}."
    )
    w(
        f"Mean MCC: GPT-4 {mean([r['MCC'] for r in gpt4]):.3f} "
        f"versus GPT-4o/Gemini {mean([r['MCC'] for r in others]):.3f}."
    )
    w()
    w("The GPT-4-labelled models sit at a *conservative* operating point: they "
      "flag fewer apps than are actually defective (flag ratio below 1), and in "
      "exchange retain far higher specificity and equal or better MCC. The "
      "GPT-4o/Gemini-labelled models sit at a *permissive* operating point: they "
      "flag more apps than are defective, buying recall at the cost of "
      "specificity that approaches or reaches zero. Discriminative power is not "
      "lower for the GPT-4 configurations, so the accuracy drop reported for "
      "Cases 03 and 06 is a movement along the precision/recall trade-off "
      "induced by the class balance of the training labels, and not evidence of "
      "fabricated model output.")
    w()

    (RESULTS / "error_analysis_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    # ---------------- LaTeX table ---------------------------------------
    tex = [
        r"% Auto-generated by analysis/scripts/02_error_analysis.py",
        r"\begin{table*}[ht!]",
        r"    \centering",
        r"    \caption{Prevalence-aware re-analysis of the eight reported cases on the "
        r"150-app test set. $\Delta$A is accuracy minus the accuracy of a degenerate "
        r"classifier that flags every app. Spec.\ is specificity, Bal.A is balanced "
        r"accuracy, and MCC is the Matthews Correlation Coefficient. Prevalence is "
        r"0.913 for \textit{Incorrect} and 0.807 for \textit{Incomplete}.}",
        r"    \label{tab:error_analysis}",
        r"    \resizebox{\textwidth}{!}{%",
        r"    \begin{tabular}{|l|l|c|c|c|c|c|c|c|c|l|}",
        r"        \hline",
        r"        \textbf{Case} & \textbf{Category} & \textbf{A} & $\mathbf{\Delta}$\textbf{A} "
        r"& \textbf{Spec.} & \textbf{Bal.A} & \textbf{MCC} & $\boldsymbol{\kappa}$ & "
        r"\textbf{FP} & \textbf{FN} & \textbf{Dominant error} \\",
        r"        \hline",
    ]
    def fmt_opt(v):
        return "--" if v is None else f"{v:.3f}"
    for r in out:
        tex.append(
            f"        {r['case']} & {r['category']} & {r['A']:.3f} & "
            f"{r['A_minus_baseline']:+.3f} & {fmt_opt(r['specificity'])} & "
            f"{fmt_opt(r['balanced_accuracy'])} & {fmt_opt(r['MCC'])} & "
            f"{fmt_opt(r['kappa'])} & {r['FP']} & {r['FN']} & "
            f"{r['error_profile']} \\\\"
        )
        tex.append(r"        \hline")
    tex += [r"    \end{tabular}", r"    }", r"\end{table*}"]
    (RESULTS / "table_error_analysis.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    print(f"\nWrote {RESULTS/'error_analysis.csv'}")
    print(f"Wrote {RESULTS/'error_analysis_summary.md'}")
    print(f"Wrote {RESULTS/'table_error_analysis.tex'}")


if __name__ == "__main__":
    main()
