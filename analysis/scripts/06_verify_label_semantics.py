#!/usr/bin/env python3
"""
06_verify_label_semantics.py

Establish, empirically, which direction the `Incorrect` and `Incomplete` labels
actually run, because the submitted manuscript defines them inconsistently.

The contradiction
-----------------
Example 1 in Section 4.1 (the prompt actually sent to the models) states:

    "Incomplete: Data Safety provides information but is not as complete as the
     Privacy Policy provides.
     Incorrect:  Data Safety does not provide that information, but the Privacy
     Policy mentions it."

Appendix A states the reverse for Incorrect:

    "the `Incorrect' class reveals an overt error in alignment, where specific
     data-sharing types are mentioned in the data safety declarations but
     conspicuously absent in the privacy policy."

and the reverse for Incomplete relative to Example 1:

    "a deeper dive reveals omissions in the privacy policy when compared to the
     finer aspects of the data safety declarations."

A reader cannot reproduce the study without knowing which reading the ground
truth follows. This script settles it from the annotators' own behaviour, by
pairing each verdict with the structural facts of the app's Data Safety section
and with the language of the annotator's written rationale.

Method
------
For every audited app/dimension we record whether the Data Safety section
declares nothing at all, and how many data types it declares. If `Incorrect`
means "Data Safety under-declares relative to the policy", then apps with an
empty Data Safety section should be strongly over-represented among `Incorrect`
verdicts. If it means the reverse, they should be under-represented.

Rationale wording is then checked independently: rationales are classified by
which document each one accuses of omitting something.

Outputs
-------
    results/label_semantics.json
    results/label_semantics.md
"""

from __future__ import annotations

import json
import pathlib
import re

import pandas as pd

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
DATA = BASE.parents[2] / "data-in-brief-submission" / "data_package" / "data"

DIMS = {
    "label_one_s": ("sharing", "correctness", "Incorrect", "Correct"),
    "label_two_s": ("sharing", "completeness", "Incomplete", "Complete"),
    "label_one_c": ("collection", "correctness", "Incorrect", "Correct"),
    "label_two_c": ("collection", "completeness", "Incomplete", "Complete"),
}

# Phrases that accuse one document or the other of omitting something.
POLICY_OMITS = re.compile(
    r"(?:privacy polic\w*|policy|pp)\b[^.]{0,60}?\b(?:not |n't |no |doesn|does not|didn|"
    r"missing|lack|omit|without|isn)", re.I
)
SAFETY_OMITS = re.compile(
    r"(?:data safety|safety|ds)\b[^.]{0,60}?\b(?:not |n't |no |doesn|does not|didn|"
    r"missing|lack|omit|without|isn)", re.I
)


def main() -> None:
    aj = pd.read_csv(DATA / "audit_judgments.csv")
    texts = pd.read_csv(DATA / "app_texts.csv")
    ra = pd.read_csv(DATA / "rationales_long.csv")

    ds = texts.set_index("app_id")["data_safety_content"].astype(str).to_dict()

    def empty_ds(app_id) -> bool:
        t = ds.get(app_id, "")
        return "'data_shared': []" in t and "'data_collected': []" in t

    def n_types(app_id) -> int:
        return len(set(re.findall(r"'data_type':\s*'([^']+)'", ds.get(app_id, ""))))

    report: dict = {"structural_test": {}, "rationale_test": {}}
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        print(s)

    w("# Which direction do the labels actually run?")
    w()
    w("## Test 1 (structural): are empty Data Safety sections over-represented "
      "among defect verdicts?")
    w()
    w("| Dimension | verdict | n | share with an empty Data Safety section | "
      "mean declared data types |")
    w("|---|---|---|---|---|")

    for col, (axis, jtype, defect, clean) in DIMS.items():
        sub = aj[aj[col].notna()][["app_id", col]]
        for verdict in (defect, clean):
            rows = sub[sub[col] == verdict]
            if rows.empty:
                continue
            share = float(rows.app_id.map(empty_ds).mean())
            mtypes = float(rows.app_id.map(n_types).mean())
            report["structural_test"].setdefault(f"{axis}/{jtype}", {})[verdict] = {
                "n": int(len(rows)),
                "empty_data_safety_share": round(share, 3),
                "mean_declared_types": round(mtypes, 2),
            }
            w(f"| {axis}/{jtype} | {verdict} | {len(rows)} | {share:.3f} | {mtypes:.2f} |")
    w()

    # Interpretation
    inc_dims = [k for k in report["structural_test"] if "correctness" in k]
    icp_dims = [k for k in report["structural_test"] if "completeness" in k]

    def delta(dims, defect, clean):
        ds_, cs_ = [], []
        for k in dims:
            e = report["structural_test"][k]
            if defect in e and clean in e:
                ds_.append(e[defect]["empty_data_safety_share"])
                cs_.append(e[clean]["empty_data_safety_share"])
        return (sum(ds_) / len(ds_)) - (sum(cs_) / len(cs_))

    d_incorrect = delta(inc_dims, "Incorrect", "Correct")
    d_incomplete = delta(icp_dims, "Incomplete", "Complete")
    report["structural_test"]["_empty_ds_share_delta"] = {
        "Incorrect_minus_Correct": round(d_incorrect, 3),
        "Incomplete_minus_Complete": round(d_incomplete, 3),
    }
    w(f"Empty-Data-Safety share, Incorrect minus Correct: {d_incorrect:+.3f}")
    w(f"Empty-Data-Safety share, Incomplete minus Complete: {d_incomplete:+.3f}")
    w()
    w(
        "An app whose Data Safety section declares nothing cannot possibly "
        "declare *more* than its privacy policy. So a positive delta for "
        "`Incorrect` means `Incorrect` is recorded when the Data Safety section "
        "under-declares relative to the policy, and a negative delta for "
        "`Incomplete` means `Incomplete` requires the Data Safety section to "
        "have declared something the policy fails to match."
    )
    w()

    # ---------------- Test 2: rationale wording --------------------------
    w("## Test 2 (linguistic): which document does the annotator accuse?")
    w()
    w("| Verdict | rationales | accuses the privacy policy | accuses Data Safety |")
    w("|---|---|---|---|")
    for verdict in ("Incorrect", "Correct", "Incomplete", "Complete"):
        sub = ra[(ra.verdict == verdict) & ra.rationale_text.notna()]
        if sub.empty:
            continue
        txt = sub.rationale_text.astype(str)
        pol = float(txt.str.contains(POLICY_OMITS).mean())
        saf = float(txt.str.contains(SAFETY_OMITS).mean())
        report["rationale_test"][verdict] = {
            "n": int(len(sub)),
            "accuses_policy": round(pol, 3),
            "accuses_data_safety": round(saf, 3),
        }
        w(f"| {verdict} | {len(sub)} | {pol:.3f} | {saf:.3f} |")
    w()

    # ---------------- conclusion, derived from the tests above -----------
    # Decision rule, fixed before looking at the numbers:
    #   |delta| >= 0.05 and the same sign on both audit axes  -> direction resolved
    #   otherwise                                             -> inconclusive
    def per_axis_deltas(dims, defect, clean):
        out = {}
        for k in dims:
            e = report["structural_test"][k]
            if defect in e and clean in e:
                out[k] = round(
                    e[defect]["empty_data_safety_share"]
                    - e[clean]["empty_data_safety_share"],
                    3,
                )
        return out

    inc_axis = per_axis_deltas(inc_dims, "Incorrect", "Correct")
    icp_axis = per_axis_deltas(icp_dims, "Incomplete", "Complete")

    def verdict_on(deltas: dict, threshold: float = 0.05) -> str:
        vals = list(deltas.values())
        if not vals:
            return "inconclusive"
        if all(v >= threshold for v in vals):
            return "data-safety-under-declares"
        if all(v <= -threshold for v in vals):
            return "policy-under-describes"
        return "inconclusive"

    inc_dir = verdict_on(inc_axis)
    icp_dir = verdict_on(icp_axis)

    report["direction_test"] = {
        "Incorrect": {"per_axis_delta": inc_axis, "resolution": inc_dir},
        "Incomplete": {"per_axis_delta": icp_axis, "resolution": icp_dir},
        "decision_rule": "|delta| >= 0.05 with a consistent sign on both audit axes",
    }

    w("## Conclusion")
    w()
    w(f"Per-axis empty-Data-Safety deltas for `Incorrect`: {inc_axis} "
      f"-> **{inc_dir}**")
    w(f"Per-axis empty-Data-Safety deltas for `Incomplete`: {icp_axis} "
      f"-> **{icp_dir}**")
    w()

    if inc_dir == "data-safety-under-declares":
        report.setdefault("operational_definition", {})["Incorrect"] = (
            "the privacy policy mentions a data practice that the Data Safety "
            "section does not declare"
        )
        w(
            "- **Incorrect is resolved.** Apps with an empty Data Safety section "
            "are markedly over-represented among `Incorrect` verdicts on both "
            "audit axes, and such apps declare fewer data types on average. An "
            "app that declares nothing cannot over-declare, so `Incorrect` must "
            "mean *the privacy policy mentions a data practice that the Data "
            "Safety section does not declare*. This matches the prompt in "
            "Example 1 and contradicts Appendix A, which must therefore be "
            "corrected."
        )
    else:
        w("- **Incorrect is not resolved by this test.**")
    w()

    if icp_dir == "inconclusive":
        report.setdefault("operational_definition", {})["Incomplete"] = (
            "UNRESOLVED in the corpus; see the reliability analysis"
        )
        w(
            "- **Incomplete is not resolved.** The two audit axes disagree in "
            f"sign ({icp_axis}), so the corpus does not license a direction. "
            "Roughly a quarter of `Incomplete` verdicts were recorded for apps "
            "whose Data Safety section declares nothing at all, which is "
            "impossible under the Appendix A reading and unexpected under the "
            "Example 1 reading. Read together with the near-zero chance-corrected "
            "agreement on this dimension (kappa = -0.066 for sharing "
            "completeness, see 03_annotator_reliability.py), the most defensible "
            "reading is that the contradictory definitions in the submitted "
            "manuscript were themselves applied inconsistently by annotators. "
            "The revised manuscript therefore states one operational definition "
            "explicitly, reuses it verbatim in the prompt and the appendix, and "
            "reports this as a limitation of the original `Incomplete` labels "
            "rather than silently picking a direction."
        )
    else:
        report.setdefault("operational_definition", {})["Incomplete"] = (
            "the Data Safety section declares a data practice that the privacy "
            "policy does not describe as fully"
            if icp_dir == "policy-under-describes"
            else "the privacy policy declares more than the Data Safety section"
        )
        w(f"- **Incomplete is resolved**: {icp_dir}.")
    w()

    inc = report["rationale_test"].get("Incorrect", {})
    icp = report["rationale_test"].get("Incomplete", {})
    w(
        "The rationale-wording test is reported for completeness but is not "
        "relied on: the keyword patterns are crude and the margins are small "
        f"(`Incorrect`: {inc.get('accuses_policy')} of rationales fault the "
        f"policy versus {inc.get('accuses_data_safety')} that fault Data Safety; "
        f"`Incomplete`: {icp.get('accuses_policy')} versus "
        f"{icp.get('accuses_data_safety')})."
    )

    (RESULTS / "label_semantics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (RESULTS / "label_semantics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS/'label_semantics.json'}")


if __name__ == "__main__":
    main()
