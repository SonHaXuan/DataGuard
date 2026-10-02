#!/usr/bin/env python3
"""
03_annotator_reliability.py

Measure how reliably *human* experts perform the very task the models are asked
to perform, using the DataGuard audit corpus.

Why this matters for the review
-------------------------------
Reviewer 1 asks for an error analysis including "difficult cases" (Major 3) and
for the hallucination interpretations to be either evidenced or moderated
(Major 4). Both need a reference point for how hard the task intrinsically is.

The DataGuard audit corpus contains repeated independent judgments: 289 of the
1,214 audited apps were reviewed by more than one annotator, before any
adjudication. Those repeats let us estimate the human agreement ceiling on each
of the four audit dimensions. A model cannot be meaningfully credited or blamed
for behaviour that falls inside the band where trained humans also disagree.

Statistics reported
-------------------
Raw pairwise agreement, Cohen's kappa, and PABAK (prevalence-adjusted
bias-adjusted kappa, = 2*p_o - 1). PABAK is included because Cohen's kappa is
depressed when one class dominates; reporting both prevents over- or
under-stating reliability. Per-annotator positive rates are reported to show
whether disagreement is driven by systematic annotator leniency/strictness
rather than by random noise.

Outputs
-------
    results/annotator_reliability.json
    results/annotator_reliability.md
    results/table_annotator_reliability.tex
    results/difficult_apps.csv              apps where trained humans disagreed
"""

from __future__ import annotations

import itertools
import json
import pathlib

import pandas as pd

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# The DataGuard Data-in-Brief package is the canonical source for the audit data.
DATA = (
    BASE.parents[2]  # .../DATAGUARD
    / "data-in-brief-submission"
    / "data_package"
    / "data"
)

DIMENSIONS = {
    "label_one_s": ("Sharing", "Correctness", "Incorrect"),
    "label_two_s": ("Sharing", "Completeness", "Incomplete"),
    "label_one_c": ("Collection", "Correctness", "Incorrect"),
    "label_two_c": ("Collection", "Completeness", "Incomplete"),
}


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters over a set of (rater_a, rater_b) verdicts."""
    n = len(pairs)
    if n == 0:
        return None
    cats = sorted({v for p in pairs for v in p})
    po = sum(a == b for a, b in pairs) / n
    pe = 0.0
    for c in cats:
        pa = sum(a == c for a, _ in pairs) / n
        pb = sum(b == c for _, b in pairs) / n
        pe += pa * pb
    return None if pe == 1 else (po - pe) / (1 - pe)


def main() -> None:
    aj = pd.read_csv(DATA / "audit_judgments.csv")
    annotators = pd.read_csv(DATA / "annotators_anonymized.csv")

    report: dict = {
        "source": str(DATA / "audit_judgments.csv"),
        "n_judgment_rows": int(len(aj)),
        "n_unique_apps": int(aj.app_id.nunique()),
        "n_annotators": int(aj.annotator_id.nunique()),
        "judgments_per_app": {
            str(k): int(v)
            for k, v in aj.groupby("app_id").size().value_counts().sort_index().items()
        },
        "dimensions": {},
        "per_annotator": {},
    }

    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        print(s)

    w("# Human reliability on the disclosure-audit task (DataGuard corpus)")
    w()
    w(
        f"Audit rows: {len(aj)}; unique apps: {aj.app_id.nunique()}; "
        f"annotators: {aj.annotator_id.nunique()}."
    )
    multi = (aj.groupby("app_id").size() >= 2).sum()
    w(f"Apps carrying two or more independent judgments: {multi}.")
    w()
    w(
        "These are first-pass independent judgments recorded before any "
        "adjudication, so they measure the raw difficulty of the task rather "
        "than the quality of the final adjudicated labels."
    )
    w()

    # ---------------- per-dimension agreement ----------------------------
    w("## Pairwise agreement between independent annotators")
    w()
    w("| Audit axis | Judgment | pairs | raw agreement | Cohen's kappa | PABAK | "
      "defect rate |")
    w("|---|---|---|---|---|---|---|")

    difficult_rows = []
    for col, (axis, jtype, defect) in DIMENSIONS.items():
        pairs: list[tuple[str, str]] = []
        for app_id, grp in aj.groupby("app_id"):
            verdicts = grp[col].dropna().tolist()
            if len(verdicts) >= 2:
                for a, b in itertools.combinations(verdicts, 2):
                    pairs.append((a, b))
                if len(set(verdicts)) > 1:
                    difficult_rows.append(
                        {
                            "app_id": app_id,
                            "audit_axis": axis,
                            "judgment_type": jtype,
                            "n_judgments": len(verdicts),
                            "verdicts": " | ".join(verdicts),
                            "annotators": " | ".join(
                                grp.loc[grp[col].notna(), "annotator_id"].tolist()
                            ),
                        }
                    )
        if not pairs:
            continue
        po = sum(a == b for a, b in pairs) / len(pairs)
        k = cohen_kappa(pairs)
        pabak = 2 * po - 1
        defect_rate = sum(
            v == defect for p in pairs for v in p
        ) / (2 * len(pairs))

        report["dimensions"][col] = {
            "axis": axis,
            "judgment_type": jtype,
            "defect_label": defect,
            "n_pairs": len(pairs),
            "raw_agreement": round(po, 3),
            "cohen_kappa": None if k is None else round(k, 3),
            "pabak": round(pabak, 3),
            "defect_rate": round(defect_rate, 3),
        }
        w(
            f"| {axis} | {jtype} | {len(pairs)} | {po:.3f} | "
            f"{'--' if k is None else f'{k:.3f}'} | {pabak:+.3f} | "
            f"{defect_rate:.3f} |"
        )

    w()
    agreements = [d["raw_agreement"] for d in report["dimensions"].values()]
    kappas = [
        d["cohen_kappa"]
        for d in report["dimensions"].values()
        if d["cohen_kappa"] is not None
    ]
    report["summary"] = {
        "raw_agreement_min": min(agreements),
        "raw_agreement_max": max(agreements),
        "kappa_min": min(kappas),
        "kappa_max": max(kappas),
    }
    w(
        f"Raw agreement spans {min(agreements):.3f}-{max(agreements):.3f} and "
        f"Cohen's kappa spans {min(kappas):.3f}-{max(kappas):.3f} across the four "
        "dimensions. On a binary decision with near-balanced marginals, chance "
        "agreement is about 0.50, so trained annotators working independently "
        "agree only slightly above chance."
    )
    w()

    # ---------------- per-annotator behaviour ----------------------------
    w("## Per-annotator defect rates")
    w()
    w("Systematic differences in how often each annotator records a defect "
      "indicate that disagreement is partly a calibration effect rather than "
      "random noise.")
    w()
    w("| Annotator | role | rows | Sharing/Incorrect | Sharing/Incomplete | "
      "Collection/Incorrect | Collection/Incomplete |")
    w("|---|---|---|---|---|---|---|")
    roles = annotators.set_index("annotator_id")["role"].to_dict()
    for aid, grp in aj.groupby("annotator_id"):
        rates = {}
        for col, (_axis, _jt, defect) in DIMENSIONS.items():
            v = grp[col].dropna()
            rates[col] = None if len(v) == 0 else round((v == defect).mean(), 3)
        report["per_annotator"][aid] = {
            "role": roles.get(aid, ""),
            "n_rows": int(len(grp)),
            "defect_rates": rates,
        }
        cells = " | ".join(
            "--" if rates[c] is None else f"{rates[c]:.3f}" for c in DIMENSIONS
        )
        w(f"| {aid} | {roles.get(aid,'')} | {len(grp)} | {cells} |")
    w()

    spread = {}
    for col in DIMENSIONS:
        vals = [
            v["defect_rates"][col]
            for v in report["per_annotator"].values()
            if v["defect_rates"][col] is not None
        ]
        if vals:
            spread[col] = round(max(vals) - min(vals), 3)
    report["per_annotator_defect_rate_spread"] = spread
    w(
        "Across-annotator spread in defect rate: "
        + ", ".join(
            f"{DIMENSIONS[c][0]}/{DIMENSIONS[c][1]} {s:.3f}" for c, s in spread.items()
        )
        + "."
    )
    w()

    # ---------------- difficult apps -------------------------------------
    dif = pd.DataFrame(difficult_rows)
    dif.to_csv(RESULTS / "difficult_apps.csv", index=False)
    report["n_conflicting_app_dimension_pairs"] = int(len(dif))
    report["n_apps_with_any_conflict"] = int(dif.app_id.nunique()) if len(dif) else 0

    w("## Difficult cases")
    w()
    w(
        f"{len(dif)} app/dimension cells received conflicting verdicts from "
        f"independent annotators, spanning {dif.app_id.nunique()} distinct apps. "
        "These are written to `difficult_apps.csv` and form the natural "
        "difficult-case pool for qualitative error analysis."
    )
    w()
    if len(dif):
        w("Conflicts by dimension:")
        for (axis, jt), n in dif.groupby(["audit_axis", "judgment_type"]).size().items():
            w(f"- {axis} / {jt}: {n}")
    w()

    # ---------------- LaTeX table ----------------------------------------
    tex = [
        r"% Auto-generated by analysis/scripts/03_annotator_reliability.py",
        r"\begin{table}[ht!]",
        r"    \centering",
        r"    \caption{Agreement between independent human annotators on the four "
        r"disclosure-audit dimensions in the DataGuard corpus, computed over apps "
        r"that received more than one first-pass judgment. PABAK is the "
        r"prevalence-adjusted bias-adjusted kappa.}",
        r"    \label{tab:annotator_reliability}",
        r"    \resizebox{0.48\textwidth}{!}{%",
        r"    \begin{tabular}{|l|l|c|c|c|c|}",
        r"        \hline",
        r"        \textbf{Axis} & \textbf{Judgment} & \textbf{Pairs} & "
        r"\textbf{Agree.} & $\boldsymbol{\kappa}$ & \textbf{PABAK} \\",
        r"        \hline",
    ]
    for d in report["dimensions"].values():
        kappa_cell = (
            "--" if d["cohen_kappa"] is None else format(d["cohen_kappa"], ".3f")
        )
        tex.append(
            f"        {d['axis']} & {d['judgment_type']} & {d['n_pairs']} & "
            f"{d['raw_agreement']:.3f} & {kappa_cell} & {d['pabak']:+.3f} \\\\"
        )
        tex.append(r"        \hline")
    tex += [r"    \end{tabular}", r"    }", r"\end{table}"]
    (RESULTS / "table_annotator_reliability.tex").write_text(
        "\n".join(tex) + "\n", encoding="utf-8"
    )

    (RESULTS / "annotator_reliability.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (RESULTS / "annotator_reliability.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"\nWrote {RESULTS/'annotator_reliability.json'}")
    print(f"Wrote {RESULTS/'annotator_reliability.md'}")
    print(f"Wrote {RESULTS/'difficult_apps.csv'}")


if __name__ == "__main__":
    main()
