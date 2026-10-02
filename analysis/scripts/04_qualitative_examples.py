#!/usr/bin/env python3
"""
04_qualitative_examples.py

Extract concrete, real-world discrepancy cases from the DataGuard corpus for the
qualitative analysis Reviewer 1 asks for (Major Issue 6), and assemble the
difficult-case illustrations for the error analysis (Major Issue 3).

Each selected case carries the full evidential chain:
    app identity -> Google Play Data Safety declaration -> the privacy-policy
    excerpt the annotator pasted as evidence -> the annotator's rationale ->
    the recorded verdict.

Selection policy
----------------
Consensus cases: every annotator who judged that app/dimension agreed, the
evidence excerpt is substantive, and the rationale is informative. These are
used as unambiguous illustrations of each defect type.

Contested cases: independent annotators recorded conflicting verdicts on the
same app/dimension. These are used to show what makes a case genuinely hard,
and to give the reader a sense of the band inside which model disagreement with
the reference labels is not necessarily model error.

Outputs
-------
    results/qualitative_examples.json
    results/qualitative_examples.md
    results/examples_consensus.tex
    results/examples_contested.tex
"""

from __future__ import annotations

import json
import pathlib
import re

import pandas as pd

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
DATA = BASE.parents[2] / "data-in-brief-submission" / "data_package" / "data"

MIN_EVIDENCE_CHARS = 90
MIN_RATIONALE_CHARS = 35

AXIS_LABEL = {"sharing": "Data sharing", "collection": "Data collection"}


def clean(text: str, limit: int | None = None) -> str:
    """Normalise whitespace and the mojibake question marks in the scrape."""
    t = re.sub(r"\s+", " ", str(text)).strip()
    if limit and len(t) > limit:
        t = t[: limit - 1].rsplit(" ", 1)[0] + "…"
    return t


def tex_escape(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(c, c) for c in text)


def summarise_data_safety(raw: str) -> dict:
    """Pull the declared categories out of the stored Data Safety blob."""
    text = str(raw)
    out = {"shared": [], "collected": [], "security": []}
    for key, field in (
        ("data_shared", "shared"),
        ("data_collected", "collected"),
        ("security_practices", "security"),
    ):
        m = re.search(rf"'{key}':\s*\[(.*?)\](?=,\s*'|\s*\}}$)", text, re.S)
        if not m:
            continue
        out[field] = sorted(set(re.findall(r"'category':\s*'([^']+)'", m.group(1))))
    out["data_types"] = sorted(set(re.findall(r"'data_type':\s*'([^']+)'", text)))
    out["declares_nothing_shared"] = "'data_shared': []" in text
    out["declares_nothing_collected"] = "'data_collected': []" in text
    return out


def main() -> None:
    aj = pd.read_csv(DATA / "audit_judgments.csv")
    apps = pd.read_csv(DATA / "apps.csv")
    texts = pd.read_csv(DATA / "app_texts.csv")
    ev = pd.read_csv(DATA / "evidence_excerpts_long.csv")
    ra = pd.read_csv(DATA / "rationales_long.csv")

    ds_by_app = texts.set_index("app_id")["data_safety_content"].to_dict()
    pp_by_app = texts.set_index("app_id")["privacy_policy_content"].to_dict()
    app_meta = apps.set_index("app_id")[
        ["app_package", "app_name", "category_name", "download_tier",
         "privacy_policy_host"]
    ].to_dict("index")

    # Join evidence with its matching rationale on the same judgment cell.
    ra_key = ra.set_index(["label_id", "audit_axis", "judgment_type"])[
        "rationale_text"
    ].to_dict()
    ev = ev[ev.evidence_text.notna()].copy()
    ev["rationale_text"] = [
        ra_key.get((r.label_id, r.audit_axis, r.judgment_type))
        for r in ev.itertuples()
    ]

    # Consensus map: for each (app, axis, judgment_type) do all annotators agree?
    dim_col = {
        ("sharing", "correctness"): "label_one_s",
        ("sharing", "completeness"): "label_two_s",
        ("collection", "correctness"): "label_one_c",
        ("collection", "completeness"): "label_two_c",
    }
    consensus: dict[tuple, dict] = {}
    for (axis, jtype), col in dim_col.items():
        for app_id, grp in aj.groupby("app_id"):
            verdicts = grp[col].dropna().tolist()
            if verdicts:
                consensus[(app_id, axis, jtype)] = {
                    "n": len(verdicts),
                    "unanimous": len(set(verdicts)) == 1,
                    "verdicts": verdicts,
                }

    # ---------------- candidate scoring ----------------------------------
    cands = []
    for r in ev.itertuples():
        if not isinstance(r.rationale_text, str):
            continue
        if len(str(r.evidence_text)) < MIN_EVIDENCE_CHARS:
            continue
        if len(r.rationale_text) < MIN_RATIONALE_CHARS:
            continue
        if r.verdict not in ("Incorrect", "Incomplete"):
            continue
        cons = consensus.get((r.app_id, r.audit_axis, r.judgment_type), {})
        meta = app_meta.get(r.app_id, {})
        ds = ds_by_app.get(r.app_id, "")
        cands.append(
            {
                "app_id": int(r.app_id),
                "app_package": meta.get("app_package", ""),
                "app_name": meta.get("app_name", ""),
                "category": meta.get("category_name", ""),
                "download_tier": meta.get("download_tier", ""),
                "policy_host": meta.get("privacy_policy_host", ""),
                "audit_axis": r.audit_axis,
                "judgment_type": r.judgment_type,
                "verdict": r.verdict,
                "annotator_id": r.annotator_id,
                "n_judgments": cons.get("n", 1),
                "unanimous": bool(cons.get("unanimous", True)),
                "all_verdicts": cons.get("verdicts", [r.verdict]),
                "evidence_text": clean(r.evidence_text, 700),
                "rationale_text": clean(r.rationale_text, 320),
                "data_safety_summary": summarise_data_safety(ds),
                "data_safety_raw": clean(ds, 900),
                "policy_chars": len(str(pp_by_app.get(r.app_id, ""))),
                "_score": len(str(r.evidence_text)) + 2 * len(r.rationale_text),
            }
        )

    df = pd.DataFrame(cands)
    print(f"Candidate evidence-backed defect cases: {len(df)}")

    # ---- consensus illustrations: best per (axis, judgment_type) ---------
    selected: list[dict] = []
    for (axis, jtype), grp in df[df.unanimous].groupby(["audit_axis", "judgment_type"]):
        # Prefer cases confirmed by more than one annotator, then richest text,
        # and keep category diversity across the chosen set.
        grp = grp.sort_values(["n_judgments", "_score"], ascending=False)
        used_cat = {s["category"] for s in selected}
        pick = None
        for _, row in grp.iterrows():
            if row["category"] not in used_cat:
                pick = row
                break
        if pick is None and len(grp):
            pick = grp.iloc[0]
        if pick is not None:
            d = pick.to_dict()
            d["selection"] = "consensus"
            selected.append(d)

    # ---- contested illustrations ---------------------------------------
    contested = df[(~df.unanimous) & (df.n_judgments >= 2)].sort_values(
        "_score", ascending=False
    )
    for (axis, jtype), grp in contested.groupby(["audit_axis", "judgment_type"]):
        d = grp.iloc[0].to_dict()
        d["selection"] = "contested"
        selected.append(d)

    for s in selected:
        s.pop("_score", None)

    (RESULTS / "qualitative_examples.json").write_text(
        json.dumps(selected, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---------------- markdown report ------------------------------------
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)

    w("# Real discrepancy cases from the DataGuard corpus")
    w()
    w(
        f"Selected from {len(df)} human-audited defect judgments that carry both a "
        "pasted privacy-policy excerpt and a written rationale. Consensus cases "
        "are unanimous among the annotators who reviewed the app; contested "
        "cases are those where independent annotators disagreed."
    )
    w()
    w(
        "These cases document discrepancies between two *disclosure artefacts* - "
        "the Google Play Data Safety section and the linked privacy policy. They "
        "are not claims about the apps' actual runtime behaviour, and not "
        "allegations of intentional wrongdoing."
    )
    w()

    for group, title in (("consensus", "Consensus cases"), ("contested", "Contested cases")):
        w(f"## {title}")
        w()
        for i, s in enumerate([x for x in selected if x["selection"] == group], 1):
            dss = s["data_safety_summary"]
            w(f"### {group[:3].upper()}-{i}. {s['app_name']} (`{s['app_package']}`)")
            w()
            w(
                f"- Category: {s['category']} | Downloads: {s['download_tier']} | "
                f"Policy host: {s['policy_host']}"
            )
            w(
                f"- Dimension: {AXIS_LABEL[s['audit_axis']]} / "
                f"{s['judgment_type']} -> **{s['verdict']}**"
            )
            if group == "contested":
                w(f"- Independent verdicts recorded: {', '.join(s['all_verdicts'])}")
            else:
                w(f"- Annotators in agreement: {s['n_judgments']}")
            w()
            w("**Data Safety declaration**")
            w()
            shared = dss["shared"] or (["(nothing declared as shared)"]
                                       if dss["declares_nothing_shared"] else [])
            collected = dss["collected"] or (["(nothing declared as collected)"]
                                             if dss["declares_nothing_collected"] else [])
            w(f"- Declared shared: {', '.join(shared) if shared else 'n/a'}")
            w(f"- Declared collected: {', '.join(collected) if collected else 'n/a'}")
            if dss["data_types"]:
                w(f"- Declared data types: {', '.join(dss['data_types'][:12])}")
            w()
            w("**Privacy-policy excerpt cited by the annotator**")
            w()
            w(f"> {s['evidence_text']}")
            w()
            w("**Annotator rationale**")
            w()
            w(f"> {s['rationale_text']}")
            w()

    (RESULTS / "qualitative_examples.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------------- LaTeX for the manuscript ---------------------------
    # Emitted as two files so the manuscript can \input them independently:
    #   examples_consensus.tex  unanimous illustrations of each defect type
    #   examples_contested.tex  cases where independent reviewers disagreed
    for group, outname in (
        ("consensus", "examples_consensus.tex"),
        ("contested", "examples_contested.tex"),
    ):
        tex: list[str] = [
            r"% Auto-generated by analysis/scripts/04_qualitative_examples.py",
            rf"% {group.capitalize()} discrepancy cases from the DataGuard corpus.",
            r"% Requires \usepackage[most]{tcolorbox} (already in the preamble).",
        ]
        for i, s in enumerate([x for x in selected if x["selection"] == group], 1):
            dss = s["data_safety_summary"]
            shared = ", ".join(dss["shared"]) or (
                "nothing declared as shared" if dss["declares_nothing_shared"] else "n/a"
            )
            collected = ", ".join(dss["collected"]) or (
                "nothing declared as collected"
                if dss["declares_nothing_collected"]
                else "n/a"
            )
            tag = "Case" if group == "consensus" else "Contested case"
            if group == "contested":
                verdict_line = (
                    rf"\textit{{Independent verdicts recorded:}} "
                    rf"{tex_escape(', '.join(s['all_verdicts']))}\\[2pt]"
                )
            else:
                verdict_line = (
                    rf"\textit{{Reviewers in agreement:}} {s['n_judgments']}\\[2pt]"
                )
            tex += [
                r"",
                r"\begin{tcolorbox}[colback=gray!5,colframe=gray!55,boxrule=0.4pt,"
                r"left=4pt,right=4pt,top=3pt,bottom=3pt,breakable]",
                rf"\textbf{{{tag} {i}: {tex_escape(s['app_name'])}}} "
                rf"(\texttt{{{tex_escape(s['app_package'])}}}, {tex_escape(s['category'])}, "
                rf"{tex_escape(str(s['download_tier']))} downloads)\\[2pt]",
                rf"\textit{{Dimension:}} {AXIS_LABEL[s['audit_axis']]} / "
                rf"{s['judgment_type']} $\rightarrow$ \textbf{{{s['verdict']}}}\\[2pt]",
                verdict_line,
                rf"\textit{{Data Safety declares shared:}} {tex_escape(shared)}\\[1pt]",
                rf"\textit{{Data Safety declares collected:}} {tex_escape(collected)}\\[2pt]",
                rf"\textit{{Privacy-policy excerpt:}} ``{tex_escape(s['evidence_text'][:420])}''\\[2pt]",
                rf"\textit{{Annotator rationale:}} {tex_escape(s['rationale_text'])}",
                r"\end{tcolorbox}",
            ]
        (RESULTS / outname).write_text("\n".join(tex) + "\n", encoding="utf-8")
        print(f"Wrote {RESULTS/outname}")

    print(f"Selected {len(selected)} illustrative cases "
          f"({sum(1 for s in selected if s['selection']=='consensus')} consensus, "
          f"{sum(1 for s in selected if s['selection']=='contested')} contested)")
    print(f"Wrote {RESULTS/'qualitative_examples.md'}")



if __name__ == "__main__":
    main()
