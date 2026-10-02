#!/usr/bin/env python3
"""
build_eval_set.py

Construct the DataGuard validation set used to re-test the paper's task on
current-generation models.

Design
------
The original experiments used a 150-app test set whose class prior turned out to
be extreme (91.3% Incorrect, 80.7% Incomplete), which inflates accuracy and
makes a degenerate always-flag classifier look strong. The validation set built
here is drawn from the human-audited portion of the DataGuard corpus and is
deliberately constructed so that this confound cannot recur silently:

* only apps whose annotators agreed are used, so the reference label is not
  itself contested;
* both the Data Safety content and the privacy-policy text must be present;
* the set is stratified by Google Play category;
* the realised class prior is reported explicitly in the manifest, and a
  prevalence-balanced variant is emitted alongside the natural-prior variant.

Label mapping
-------------
DataGuard records four audit dimensions (sharing/collection x
correctness/completeness). The manuscript's two target classes are formed as:

    Incorrect  = Incorrect on sharing-correctness  OR collection-correctness
    Incomplete = Incomplete on sharing-completeness OR collection-completeness

An app contributes a target label only when every annotator who judged the
relevant dimensions agreed, so ambiguous apps are excluded rather than resolved
by majority.

Outputs
-------
    eval_set_natural.csv      stratified sample, natural class prior
    eval_set_balanced.csv     prevalence-balanced sample
    eval_set_manifest.json    composition, priors, provenance, checksums
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from collections import Counter

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_DATA = (
    HERE.parents[3] / "data-in-brief-submission" / "data_package" / "data"
)

CORRECTNESS = ["label_one_s", "label_one_c"]
COMPLETENESS = ["label_two_s", "label_two_c"]


def unanimous_label(values: list, defect: str, clean: str) -> int | None:
    """Return 1 (defect), 0 (clean), or None when absent or contested."""
    vals = [v for v in values if isinstance(v, str) and v in (defect, clean)]
    if not vals:
        return None
    if defect in vals and clean in vals:
        return None  # contested within this dimension
    return 1 if vals[0] == defect else 0


def derive_targets(grp: pd.DataFrame) -> tuple[int | None, int | None]:
    """Collapse the four audit dimensions into the manuscript's two classes."""
    # correctness axis
    per_dim = [
        unanimous_label(grp[c].tolist(), "Incorrect", "Correct") for c in CORRECTNESS
    ]
    incorrect = None if all(v is None for v in per_dim) or None in per_dim else (
        1 if any(v == 1 for v in per_dim) else 0
    )
    # completeness axis
    per_dim = [
        unanimous_label(grp[c].tolist(), "Incomplete", "Complete") for c in COMPLETENESS
    ]
    incomplete = None if all(v is None for v in per_dim) or None in per_dim else (
        1 if any(v == 1 for v in per_dim) else 0
    )
    return incorrect, incomplete


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=pathlib.Path, default=DEFAULT_DATA)
    ap.add_argument("--out", type=pathlib.Path, default=HERE / "data")
    ap.add_argument("--n", type=int, default=300, help="target size, natural-prior set")
    ap.add_argument("--n-balanced", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    aj = pd.read_csv(args.data / "audit_judgments.csv")
    apps = pd.read_csv(args.data / "apps.csv")
    texts = pd.read_csv(args.data / "app_texts.csv")

    rows = []
    for app_id, grp in aj.groupby("app_id"):
        inc, incm = derive_targets(grp)
        if inc is None and incm is None:
            continue
        rows.append(
            {
                "app_id": app_id,
                "y_incorrect": inc,
                "y_incomplete": incm,
                "n_annotators": grp.annotator_id.nunique(),
            }
        )
    lab = pd.DataFrame(rows)
    print(f"Apps with at least one unanimous target label: {len(lab)}")

    df = (
        lab.merge(
            apps[["app_id", "app_package", "app_name", "category_name", "download_tier"]],
            on="app_id",
        )
        # app_texts.csv repeats app_package; drop it so the merge keeps one copy
        .merge(
            texts[["app_id", "data_safety_content", "privacy_policy_content"]],
            on="app_id",
            how="left",
        )
    )
    # both texts must be usable
    before = len(df)
    df = df[
        df.data_safety_content.notna()
        & df.privacy_policy_content.notna()
        & (df.data_safety_content.astype(str).str.len() > 20)
        & (df.privacy_policy_content.astype(str).str.len() > 50)
    ].copy()
    print(f"After requiring both documents: {len(df)} (dropped {before-len(df)})")

    # keep only apps with BOTH targets defined, so one sample serves both tasks
    complete = df[df.y_incorrect.notna() & df.y_incomplete.notna()].copy()
    complete["y_incorrect"] = complete.y_incorrect.astype(int)
    complete["y_incomplete"] = complete.y_incomplete.astype(int)
    print(f"Apps with both targets defined: {len(complete)}")

    rng_seed = args.seed

    # ---- natural-prior stratified sample --------------------------------
    n = min(args.n, len(complete))
    per_cat = max(1, n // complete.category_name.nunique())
    parts = []
    for _cat, grp in complete.groupby("category_name"):
        parts.append(grp.sample(min(per_cat, len(grp)), random_state=rng_seed))
    natural = pd.concat(parts)
    if len(natural) < n:  # top up
        rest = complete.drop(natural.index)
        natural = pd.concat(
            [natural, rest.sample(min(n - len(natural), len(rest)), random_state=rng_seed)]
        )
    natural = natural.sample(frac=1.0, random_state=rng_seed).reset_index(drop=True)

    # ---- prevalence-balanced sample -------------------------------------
    half = args.n_balanced // 2
    bal_parts = []
    for target in ("y_incorrect",):
        pos = complete[complete[target] == 1]
        neg = complete[complete[target] == 0]
        bal_parts.append(pos.sample(min(half, len(pos)), random_state=rng_seed))
        bal_parts.append(neg.sample(min(half, len(neg)), random_state=rng_seed))
    balanced = (
        pd.concat(bal_parts)
        .drop_duplicates(subset="app_id")
        .sample(frac=1.0, random_state=rng_seed)
        .reset_index(drop=True)
    )

    cols = [
        "app_id", "app_package", "app_name", "category_name", "download_tier",
        "data_safety_content", "privacy_policy_content", "y_incorrect", "y_incomplete",
        "n_annotators",
    ]
    natural[cols].to_csv(args.out / "eval_set_natural.csv", index=False)
    balanced[cols].to_csv(args.out / "eval_set_balanced.csv", index=False)

    def prior(frame: pd.DataFrame) -> dict:
        return {
            "n": int(len(frame)),
            "incorrect_rate": round(float(frame.y_incorrect.mean()), 4),
            "incomplete_rate": round(float(frame.y_incomplete.mean()), 4),
            "by_category": {
                k: int(v) for k, v in Counter(frame.category_name).items()
            },
        }

    def sha(path: pathlib.Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "generator": "artifact/replication/build_eval_set.py",
        "seed": args.seed,
        "source_corpus": str(args.data),
        "label_derivation": {
            "incorrect": "Incorrect on sharing-correctness OR collection-correctness; "
                         "app excluded if annotators split on either dimension",
            "incomplete": "Incomplete on sharing-completeness OR collection-completeness; "
                          "app excluded if annotators split on either dimension",
        },
        "pool_apps_with_both_targets": int(len(complete)),
        "eval_set_natural": prior(natural),
        "eval_set_balanced": prior(balanced),
        "original_paper_test_prior": {
            "n": 150, "incorrect_rate": 0.913, "incomplete_rate": 0.807,
            "note": "recovered in analysis/scripts/01_reconstruct_confusion.py",
        },
        "checksums_sha256": {
            "eval_set_natural.csv": sha(args.out / "eval_set_natural.csv"),
            "eval_set_balanced.csv": sha(args.out / "eval_set_balanced.csv"),
        },
    }
    (args.out / "eval_set_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("\nNatural-prior set :", manifest["eval_set_natural"]["n"],
          "apps | Incorrect rate", manifest["eval_set_natural"]["incorrect_rate"],
          "| Incomplete rate", manifest["eval_set_natural"]["incomplete_rate"])
    print("Balanced set      :", manifest["eval_set_balanced"]["n"],
          "apps | Incorrect rate", manifest["eval_set_balanced"]["incorrect_rate"],
          "| Incomplete rate", manifest["eval_set_balanced"]["incomplete_rate"])
    print(f"\nWrote {args.out/'eval_set_natural.csv'}")
    print(f"Wrote {args.out/'eval_set_balanced.csv'}")
    print(f"Wrote {args.out/'eval_set_manifest.json'}")


if __name__ == "__main__":
    main()
