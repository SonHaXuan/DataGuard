#!/usr/bin/env python3
"""
make_probes.py

Build controlled probe variants of the evaluation set so that hallucination can
be measured against a *determinate* reference instead of being inferred from
metric wobble. This is what Reviewer 1 asks for in Major Issue 4: either
evidence for the hallucination claims, or their removal.

The probes
----------
null      The privacy policy is replaced by a document that demonstrably
          contains no data-practice statement. Under the operational definition
          of `Incorrect` (the policy mentions a practice the Data Safety section
          omits) the reference answer is necessarily incorrect = 0, because the
          policy mentions nothing at all. A model that answers 1 is asserting
          the presence of policy content that is not there. This is an
          unsupported assertion, and it is countable.

inject    A single explicit sentence is appended to the real privacy policy,
          disclosing a data type that the app's Data Safety section does not
          declare. The reference answer is necessarily incorrect = 1. A model
          that answers 0 is failing to ground its judgement in the supplied
          text. Combined with `null`, this separates a model that is insensitive
          to the evidence from one that over-asserts.

shuffle   The sentences of the real privacy policy are reordered. The task is
          about whether content is present, not about the order it appears in,
          so the reference label is unchanged. Any label flip relative to the
          unperturbed run is instability rather than reasoning.

Self-consistency is measured separately, by running the unperturbed set with
--repeats > 1; no probe file is needed for that.

Outputs
-------
    data/probe_null.csv
    data/probe_inject.csv
    data/probe_shuffle.csv
    data/probe_manifest.json
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent

# A document that is unmistakably free of data-practice statements.
NULL_POLICY = (
    "Notice. This page is a placeholder. The document that normally appears "
    "here is not available at this address. No statement about data handling, "
    "data collection, data sharing, tracking, storage, retention, disclosure or "
    "user rights is made on this page. Please check back later."
)

# Google Play Data Safety data types, used to pick something the app does not
# declare so the injected sentence is guaranteed to be unmatched.
PLAY_DATA_TYPES = [
    ("precise location", "Location"),
    ("voice or sound recordings", "Audio"),
    ("health and fitness information", "Health and fitness"),
    ("SMS and text messages", "Messages"),
    ("contacts list", "Contacts"),
    ("calendar events", "Calendar"),
    ("browsing history", "Web browsing"),
    ("purchase history", "Financial info"),
    ("photos and videos", "Photos and videos"),
    ("installed application list", "App activity"),
]

INJECT_TEMPLATE = (
    " We also disclose your {phrase} to third-party advertising and analytics "
    "partners for the purpose of audience measurement and targeted advertising."
)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text).strip())
    return [p for p in parts if p.strip()]


def pick_absent_type(data_safety: str) -> tuple[str, str] | None:
    """Choose a data type the Data Safety section does not mention."""
    ds = str(data_safety).lower()
    for phrase, play_name in PLAY_DATA_TYPES:
        needles = [play_name.lower()] + play_name.lower().split()
        if not any(n in ds for n in needles if len(n) > 3):
            return phrase, play_name
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=pathlib.Path,
                    default=HERE / "data" / "eval_set_natural.csv")
    ap.add_argument("--out", type=pathlib.Path, default=HERE / "data")
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    with args.dataset.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    fields = list(rows[0].keys()) + ["probe", "probe_detail"]

    null_rows, inject_rows, shuffle_rows = [], [], []
    n_skipped_inject = 0

    for r in rows:
        # ---- null ------------------------------------------------------
        nr = dict(r)
        nr["privacy_policy_content"] = NULL_POLICY
        # Reference: the policy mentions nothing, so nothing can be missing
        # from Data Safety relative to it.
        nr["y_incorrect"] = 0
        # Completeness is left undefined for this probe: whether a Data Safety
        # claim counts as unmatched by an absent document is a definitional
        # question, not an empirical one, so we do not score it.
        nr["y_incomplete"] = ""
        nr["probe"] = "null"
        nr["probe_detail"] = "privacy policy replaced by a contentless placeholder"
        null_rows.append(nr)

        # ---- inject ----------------------------------------------------
        picked = pick_absent_type(r["data_safety_content"])
        if picked:
            phrase, play_name = picked
            ir = dict(r)
            ir["privacy_policy_content"] = (
                str(r["privacy_policy_content"]).rstrip()
                + INJECT_TEMPLATE.format(phrase=phrase)
            )
            ir["y_incorrect"] = 1  # policy now states a practice Data Safety omits
            ir["y_incomplete"] = ""
            ir["probe"] = "inject"
            ir["probe_detail"] = f"appended an explicit disclosure of {play_name}"
            inject_rows.append(ir)
        else:
            n_skipped_inject += 1

        # ---- shuffle ---------------------------------------------------
        sents = split_sentences(r["privacy_policy_content"])
        if len(sents) >= 3:
            order = list(range(len(sents)))
            rng.shuffle(order)
            sr = dict(r)
            sr["privacy_policy_content"] = " ".join(sents[i] for i in order)
            sr["probe"] = "shuffle"
            sr["probe_detail"] = f"reordered {len(sents)} policy sentences"
            shuffle_rows.append(sr)

    def write(path: pathlib.Path, data: list[dict]) -> None:
        with path.open("w", encoding="utf-8", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=fields)
            wr.writeheader()
            wr.writerows(data)

    write(args.out / "probe_null.csv", null_rows)
    write(args.out / "probe_inject.csv", inject_rows)
    write(args.out / "probe_shuffle.csv", shuffle_rows)

    manifest = {
        "generator": "artifact/replication/make_probes.py",
        "seed": args.seed,
        "source": str(args.dataset),
        "null": {
            "n": len(null_rows),
            "reference": "y_incorrect = 0 by construction",
            "interpretation": "a prediction of 1 asserts policy content that is absent",
            "placeholder_text": NULL_POLICY,
        },
        "inject": {
            "n": len(inject_rows),
            "skipped": n_skipped_inject,
            "reference": "y_incorrect = 1 by construction",
            "interpretation": "a prediction of 0 ignores an explicit statement in the input",
            "sentence_template": INJECT_TEMPLATE.strip(),
        },
        "shuffle": {
            "n": len(shuffle_rows),
            "reference": "labels unchanged from the unperturbed set",
            "interpretation": "a label flip is instability, not reasoning",
        },
    }
    (args.out / "probe_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"null   : {len(null_rows)} rows")
    print(f"inject : {len(inject_rows)} rows ({n_skipped_inject} apps skipped, "
          "no unused data type available)")
    print(f"shuffle: {len(shuffle_rows)} rows")
    print(f"\nWrote probe files and manifest to {args.out}")


if __name__ == "__main__":
    main()
