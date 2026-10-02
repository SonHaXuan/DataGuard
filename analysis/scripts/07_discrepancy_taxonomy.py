#!/usr/bin/env python3
"""
07_discrepancy_taxonomy.py

Derive a taxonomy of recurring discrepancy patterns from the 4,866 annotator
rationales, so that the qualitative section reports categories grounded in what
reviewers actually wrote rather than categories invented for the paper.

Method
------
Each pattern is defined by a keyword signature over the rationale text. The
signatures were written by reading a sample of rationales, then applied to the
whole set. A rationale can match more than one pattern; the counts are therefore
reported as coverage, not as a partition, and the share of rationales matching no
pattern is reported so the reader can judge how much the taxonomy leaves out.

This is deliberately a transparent lexical scheme rather than a topic model: the
rationales average 79 characters, which is far too short for reliable
unsupervised topic discovery, and a reader can check a lexical rule by eye.

Outputs
-------
    results/discrepancy_taxonomy.json
    results/discrepancy_taxonomy.md
    results/table_discrepancy_taxonomy.tex
"""

from __future__ import annotations

import json
import pathlib
import re

import pandas as pd

BASE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
DATA = BASE.parents[2] / "data-in-brief-submission" / "data_package" / "data"

# Ordered so the more specific patterns are described first in the write-up.
PATTERNS = {
    "Third-party or SDK disclosure": {
        "regex": r"third[\s-]?part|sdk|advertis|ads?\b|analytic|facebook|google|firebase|admob",
        "gloss": "The discrepancy concerns data reaching third parties, advertising "
                 "networks or embedded SDKs.",
    },
    "Exemption ambiguity": {
        "regex": r"exception|exempt|not collect(?:ed)? by us|on (?:your|the) device|"
                 r"retained on|anonym|aggregat|de-?identif",
        "gloss": "The policy claims the data is anonymised, kept on device, or "
                 "otherwise falls under a Google disclosure exemption, so whether "
                 "a declaration was required is a matter of interpretation.",
    },
    "Missing data type": {
        "regex": r"not mention|no mention|does ?n[o']t mention|missing|not list|not includ|"
                 r"not refer|not state|not specif|not declar",
        "gloss": "A specific data type or practice named in one artefact is absent "
                 "from the other.",
    },
    "Empty or absent declaration": {
        "regex": r"(?:do|does|did)(?:es)? ?n[o']t provide|no info|nothing|empty|blank|"
                 r"not provided|no data safety|without any",
        "gloss": "One artefact supplies no relevant content at all.",
    },
    "Purpose mismatch": {
        "regex": r"purpose|reason|why|marketing|personali[sz]|target",
        "gloss": "Both artefacts mention the data, but disagree on what it is used for.",
    },
    "Location data": {
        "regex": r"\blocation\b|\bgps\b|geo",
        "gloss": "The discrepancy specifically concerns location data.",
    },
    "Identifiers and device data": {
        "regex": r"\bid\b|identifier|device|ip address|advertising id|cookie",
        "gloss": "The discrepancy concerns persistent identifiers or device data.",
    },
    "Account or contact data": {
        "regex": r"email|name|phone|address|account|contact|personal info",
        "gloss": "The discrepancy concerns directly identifying account or contact data.",
    },
    "Partial or less complete coverage": {
        "regex": r"not (?:as )?(?:complete|full|detail)|less|fewer|part(?:ial|ly)|some of|"
                 r"most of|not enough|not all|insufficient|general",
        "gloss": "The content is present in both artefacts but at different levels "
                 "of specificity.",
    },
    "Security or retention practices": {
        "regex": r"encrypt|secur|delet|retention|retain|storage|stored",
        "gloss": "The discrepancy concerns security practices, retention or deletion.",
    },
}


def main() -> None:
    ra = pd.read_csv(DATA / "rationales_long.csv")
    ra = ra[ra.rationale_text.notna()].copy()
    ra["text"] = ra.rationale_text.astype(str).str.lower()

    defects = ra[ra.verdict.isin(["Incorrect", "Incomplete"])].copy()
    report: dict = {
        "n_rationales_total": int(len(ra)),
        "n_rationales_defect_verdicts": int(len(defects)),
        "mean_chars": round(float(ra.rationale_text.astype(str).str.len().mean()), 1),
        "patterns": {},
    }

    matched_any = pd.Series(False, index=defects.index)
    for name, spec in PATTERNS.items():
        rx = re.compile(spec["regex"], re.I)
        hit = defects.text.str.contains(rx, regex=True)
        matched_any |= hit
        sub = defects[hit]
        report["patterns"][name] = {
            "gloss": spec["gloss"],
            "regex": spec["regex"],
            "n": int(hit.sum()),
            "share_of_defect_rationales": round(float(hit.mean()), 3),
            "by_verdict": {
                k: int(v) for k, v in sub.verdict.value_counts().items()
            },
            "by_axis": {k: int(v) for k, v in sub.audit_axis.value_counts().items()},
            "example_rationales": [
                str(t)[:180] for t in sub.rationale_text.head(3).tolist()
            ],
        }

    report["share_matching_no_pattern"] = round(float((~matched_any).mean()), 3)
    report["n_matching_no_pattern"] = int((~matched_any).sum())

    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)
        print(s)

    w("# Recurring discrepancy patterns in annotator rationales")
    w()
    w(f"Rationales analysed: {len(defects)} attached to a defect verdict, out of "
      f"{len(ra)} in total. Mean length {report['mean_chars']} characters.")
    w()
    w("Patterns are keyword signatures and are not mutually exclusive, so shares "
      "sum to more than 1. "
      f"{report['share_matching_no_pattern']:.1%} of defect rationales match no "
      "pattern.")
    w()
    w("| Pattern | n | share | Incorrect | Incomplete | sharing | collection |")
    w("|---|---|---|---|---|---|---|")
    for name, p in sorted(
        report["patterns"].items(), key=lambda kv: -kv[1]["n"]
    ):
        w(
            f"| {name} | {p['n']} | {p['share_of_defect_rationales']:.3f} | "
            f"{p['by_verdict'].get('Incorrect',0)} | "
            f"{p['by_verdict'].get('Incomplete',0)} | "
            f"{p['by_axis'].get('sharing',0)} | {p['by_axis'].get('collection',0)} |"
        )
    w()
    for name, p in sorted(report["patterns"].items(), key=lambda kv: -kv[1]["n"]):
        w(f"### {name}")
        w()
        w(p["gloss"])
        w()
        for ex in p["example_rationales"]:
            w(f"- “{ex}”")
        w()

    # ---- LaTeX ----------------------------------------------------------
    tex = [
        r"% Auto-generated by analysis/scripts/07_discrepancy_taxonomy.py",
        r"\begin{table}[ht!]",
        r"    \centering",
        r"    \caption{Recurring discrepancy patterns, derived from the "
        + str(len(defects))
        + r" annotator rationales attached to a defect verdict in the DataGuard "
        r"corpus. Patterns are keyword signatures and are not mutually exclusive. "
        + f"{report['share_matching_no_pattern']:.1%}".replace("%", r"\%")
        + r" of rationales match no pattern.}",
        r"    \label{tab:discrepancy_taxonomy}",
        r"    \resizebox{0.48\textwidth}{!}{%",
        r"    \begin{tabular}{|l|c|c|c|c|}",
        r"        \hline",
        r"        \textbf{Pattern} & \textbf{n} & \textbf{Share} & "
        r"\textbf{Incorr.} & \textbf{Incompl.} \\",
        r"        \hline",
    ]
    for name, p in sorted(report["patterns"].items(), key=lambda kv: -kv[1]["n"]):
        tex.append(
            f"        {name} & {p['n']} & {p['share_of_defect_rationales']:.3f} & "
            f"{p['by_verdict'].get('Incorrect',0)} & "
            f"{p['by_verdict'].get('Incomplete',0)} \\\\"
        )
        tex.append(r"        \hline")
    tex += [r"    \end{tabular}", r"    }", r"\end{table}"]
    (RESULTS / "table_discrepancy_taxonomy.tex").write_text(
        "\n".join(tex) + "\n", encoding="utf-8"
    )

    (RESULTS / "discrepancy_taxonomy.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RESULTS / "discrepancy_taxonomy.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"\nWrote {RESULTS/'discrepancy_taxonomy.json'}")


if __name__ == "__main__":
    main()
