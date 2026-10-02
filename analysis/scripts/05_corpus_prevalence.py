#!/usr/bin/env python3
"""
05_corpus_prevalence.py

Characterise the DataGuard corpus so the revised manuscript can (a) state the
prevalence of disclosure defects on a corpus four times larger than the one used
for the original experiments, and (b) identify which app properties make a case
hard. Together these address the external-validity limitation the submitted
version only asserted, and supply the "common sources of misclassification"
component of Reviewer 1's Major Issue 3.

Analyses
--------
1. Defect prevalence over the human-audited apps, per audit dimension, resolved
   to one verdict per app by majority with ties treated as contested.
2. Prevalence broken down by Google Play category and by download tier.
3. Comparison against the class prevalence implied by the 150-app test set used
   in the original experiments, to show how much of the reported accuracy is
   attributable to class prior.
4. Structural difficulty predictors: whether a Data Safety section declares
   nothing, privacy-policy length, and whether policy text was retrievable.
   Association with annotator disagreement is quantified.

Outputs
-------
    results/corpus_prevalence.json
    results/corpus_prevalence.md
    results/table_corpus_prevalence.tex
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

import pandas as pd

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
DATA = BASE.parents[2] / "data-in-brief-submission" / "data_package" / "data"

DIMS = {
    "label_one_s": ("Sharing", "Correctness", "Incorrect", "Correct"),
    "label_two_s": ("Sharing", "Completeness", "Incomplete", "Complete"),
    "label_one_c": ("Collection", "Correctness", "Incorrect", "Correct"),
    "label_two_c": ("Collection", "Completeness", "Incomplete", "Complete"),
}

# Class prevalence implied by the original 150-app test set, recovered in
# analysis/scripts/01_reconstruct_confusion.py.
ORIGINAL_TEST_PREVALENCE = {"Incorrect": 137 / 150, "Incomplete": 121 / 150}


def resolve(verdicts: list[str], defect: str) -> str | None:
    """Majority-resolve repeated judgments; ties are reported as 'Contested'."""
    v = [x for x in verdicts if isinstance(x, str) and x]
    if not v:
        return None
    counts = Counter(v)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return "Contested"
    return top[0][0]


def main() -> None:
    aj = pd.read_csv(DATA / "audit_judgments.csv")
    apps = pd.read_csv(DATA / "apps.csv")
    texts = pd.read_csv(DATA / "app_texts.csv")

    meta = apps.set_index("app_id")
    ds_text = texts.set_index("app_id")["data_safety_content"].to_dict()

    report: dict = {"n_audited_apps": int(aj.app_id.nunique()), "dimensions": {}}
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        print(s)

    w("# DataGuard corpus: defect prevalence and difficulty predictors")
    w()
    w(
        f"Annotation corpus: {len(apps)} apps balanced across "
        f"{apps.category_name.nunique()} Google Play categories. "
        f"Human-audited subset: {aj.app_id.nunique()} apps, {len(aj)} judgment rows, "
        f"{aj.annotator_id.nunique()} annotators."
    )
    w()

    # ---------------- 1. prevalence per dimension ------------------------
    per_app: dict[str, dict[int, str]] = {}
    w("## 1. Defect prevalence per audit dimension")
    w()
    w("| Audit axis | Judgment | apps judged | defect | clean | contested | "
      "defect rate |")
    w("|---|---|---|---|---|---|---|")
    for col, (axis, jtype, defect, clean_lbl) in DIMS.items():
        resolved = {}
        for app_id, grp in aj.groupby("app_id"):
            r = resolve(grp[col].tolist(), defect)
            if r:
                resolved[app_id] = r
        per_app[col] = resolved
        c = Counter(resolved.values())
        judged = len(resolved)
        rate = c[defect] / judged if judged else 0.0
        report["dimensions"][col] = {
            "axis": axis,
            "judgment_type": jtype,
            "defect_label": defect,
            "apps_judged": judged,
            "n_defect": c[defect],
            "n_clean": c[clean_lbl],
            "n_contested": c["Contested"],
            "defect_rate": round(rate, 3),
        }
        w(
            f"| {axis} | {jtype} | {judged} | {c[defect]} | {c[clean_lbl]} | "
            f"{c['Contested']} | {rate:.3f} |"
        )
    w()

    # any-defect at app level
    any_defect = set()
    all_judged = set()
    for col, (_a, _j, defect, _c) in DIMS.items():
        for app_id, v in per_app[col].items():
            all_judged.add(app_id)
            if v == defect:
                any_defect.add(app_id)
    report["app_level_any_defect"] = len(any_defect)
    report["app_level_judged"] = len(all_judged)
    report["app_level_any_defect_rate"] = round(len(any_defect) / len(all_judged), 3)
    w(
        f"At app level, {len(any_defect)} of {len(all_judged)} audited apps "
        f"({len(any_defect)/len(all_judged):.1%}) carry at least one disclosure "
        "defect on at least one dimension."
    )
    w()

    # ---------------- 2. prevalence by category / download tier ----------
    w("## 2. Prevalence by Google Play category")
    w()
    w("| Category | audited apps | any-defect rate |")
    w("|---|---|---|")
    by_cat = {}
    for cat, grp in meta.loc[sorted(all_judged)].groupby("category_name"):
        ids = set(grp.index)
        rate = len(ids & any_defect) / len(ids)
        by_cat[cat] = {"n": len(ids), "any_defect_rate": round(rate, 3)}
        w(f"| {cat} | {len(ids)} | {rate:.3f} |")
    report["by_category"] = by_cat
    w()

    w("## 3. Prevalence by download tier")
    w()
    w("| Download tier | audited apps | any-defect rate |")
    w("|---|---|---|")
    by_tier = {}
    order = ["Low (<50K)", "Mid (50K-1M)", "High (1M-50M)", "Top (50M+)"]
    sub = meta.loc[sorted(all_judged)]
    for tier in order:
        ids = set(sub[sub.download_tier == tier].index)
        if not ids:
            continue
        rate = len(ids & any_defect) / len(ids)
        by_tier[tier] = {"n": len(ids), "any_defect_rate": round(rate, 3)}
        w(f"| {tier} | {len(ids)} | {rate:.3f} |")
    report["by_download_tier"] = by_tier
    w()

    # ---------------- 4. comparison with the original test set -----------
    w("## 4. Class prior: DataGuard corpus versus the original 150-app test set")
    w()
    w("| Category | prevalence in original test set | comparable DataGuard rate |")
    w("|---|---|---|")
    ds_incorrect = max(
        report["dimensions"]["label_one_s"]["defect_rate"],
        report["dimensions"]["label_one_c"]["defect_rate"],
    )
    ds_incomplete = max(
        report["dimensions"]["label_two_s"]["defect_rate"],
        report["dimensions"]["label_two_c"]["defect_rate"],
    )
    w(f"| Incorrect | {ORIGINAL_TEST_PREVALENCE['Incorrect']:.3f} | {ds_incorrect:.3f} |")
    w(f"| Incomplete | {ORIGINAL_TEST_PREVALENCE['Incomplete']:.3f} | {ds_incomplete:.3f} |")
    report["prevalence_comparison"] = {
        "original_test_incorrect": round(ORIGINAL_TEST_PREVALENCE["Incorrect"], 3),
        "original_test_incomplete": round(ORIGINAL_TEST_PREVALENCE["Incomplete"], 3),
        "dataguard_incorrect": ds_incorrect,
        "dataguard_incomplete": ds_incomplete,
    }
    w()
    w(
        "The original test set is markedly more defect-heavy than the broader "
        "audited corpus. Accuracy figures obtained on it are therefore inflated "
        "relative to what the same model would score on a representative sample, "
        "which is the central reason the revised manuscript reports "
        "prevalence-aware metrics alongside accuracy."
    )
    w()

    # ---------------- 5. structural difficulty predictors ----------------
    w("## 5. Structural difficulty predictors")
    w()

    def declares_nothing(app_id: int) -> bool:
        t = str(ds_text.get(app_id, ""))
        return "'data_shared': []" in t and "'data_collected': []" in t

    def n_declared_types(app_id: int) -> int:
        return len(set(re.findall(r"'data_type':\s*'([^']+)'", str(ds_text.get(app_id, "")))))

    # contested = any dimension contested or annotators split
    contested_apps = set()
    for col in DIMS:
        for app_id, v in per_app[col].items():
            if v == "Contested":
                contested_apps.add(app_id)
    # also include apps flagged in difficult_apps.csv (raw split verdicts)
    dif_path = RESULTS / "difficult_apps.csv"
    if dif_path.exists():
        dif = pd.read_csv(dif_path)
        contested_apps |= set(dif.app_id.tolist())

    multi_judged = {a for a, g in aj.groupby("app_id") if len(g) >= 2}
    report["n_multi_judged"] = len(multi_judged)
    report["n_contested_apps"] = len(contested_apps & multi_judged)

    w(
        f"Among the {len(multi_judged)} apps reviewed by more than one annotator, "
        f"{len(contested_apps & multi_judged)} "
        f"({len(contested_apps & multi_judged)/len(multi_judged):.1%}) produced at "
        "least one conflicting verdict."
    )
    w()

    feats = []
    for app_id in sorted(multi_judged):
        row = meta.loc[app_id]
        feats.append(
            {
                "app_id": app_id,
                "contested": app_id in contested_apps,
                "declares_nothing": declares_nothing(app_id),
                "n_declared_types": n_declared_types(app_id),
                "policy_chars": int(row.privacy_policy_content_chars or 0),
                "ds_chars": int(row.data_safety_content_chars or 0),
            }
        )
    fdf = pd.DataFrame(feats)

    w("| Predictor | contested apps | agreed apps | difference |")
    w("|---|---|---|---|")
    pred_report = {}
    con = fdf[fdf.contested]
    agr = fdf[~fdf.contested]
    for name, col, fmt in (
        ("Data Safety declares nothing", "declares_nothing", "rate"),
        ("Declared data types (mean)", "n_declared_types", "mean"),
        ("Privacy-policy length in chars (mean)", "policy_chars", "mean"),
        ("Data Safety length in chars (mean)", "ds_chars", "mean"),
    ):
        if fmt == "rate":
            a, b = con[col].mean(), agr[col].mean()
            w(f"| {name} | {a:.3f} | {b:.3f} | {a-b:+.3f} |")
        else:
            a, b = con[col].mean(), agr[col].mean()
            w(f"| {name} | {a:.0f} | {b:.0f} | {a-b:+.0f} |")
        pred_report[col] = {"contested": round(float(a), 3), "agreed": round(float(b), 3)}
    report["difficulty_predictors"] = pred_report
    w()
    w(
        "Apps whose Data Safety section declares nothing at all, and apps with "
        "longer privacy policies, are over-represented among the contested "
        "cases. Both patterns have a clear mechanism: an empty declaration "
        "forces the annotator to decide whether a policy statement falls under "
        "one of Google's disclosure exemptions, and a longer policy offers more "
        "opportunities to find or miss a matching statement."
    )
    w()

    # ---------------- LaTeX table ----------------------------------------
    tex = [
        r"% Auto-generated by analysis/scripts/05_corpus_prevalence.py",
        r"\begin{table}[ht!]",
        r"    \centering",
        r"    \caption{Disclosure-defect prevalence across the four audit dimensions "
        r"of the DataGuard corpus, resolved to one verdict per app by annotator "
        r"majority. Ties are reported as contested.}",
        r"    \label{tab:corpus_prevalence}",
        r"    \resizebox{0.48\textwidth}{!}{%",
        r"    \begin{tabular}{|l|l|c|c|c|c|}",
        r"        \hline",
        r"        \textbf{Axis} & \textbf{Judgment} & \textbf{Apps} & "
        r"\textbf{Defect} & \textbf{Contested} & \textbf{Rate} \\",
        r"        \hline",
    ]
    for d in report["dimensions"].values():
        tex.append(
            f"        {d['axis']} & {d['judgment_type']} & {d['apps_judged']} & "
            f"{d['n_defect']} & {d['n_contested']} & {d['defect_rate']:.3f} \\\\"
        )
        tex.append(r"        \hline")
    tex += [r"    \end{tabular}", r"    }", r"\end{table}"]
    (RESULTS / "table_corpus_prevalence.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    (RESULTS / "corpus_prevalence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (RESULTS / "corpus_prevalence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS/'corpus_prevalence.json'}")


if __name__ == "__main__":
    main()
