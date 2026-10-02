# DataGuard

[![DOI](https://zenodo.org/badge/1401598451.svg)](https://doi.org/10.5281/zenodo.23102209)

Data, annotations and replication code for our work on the gap between what
Android apps **declare** in Google Play Data Safety and what their **privacy
policies** actually say.

Two artifacts live here:

- the **corpus**: 2,400 apps across 12 Google Play categories, their Data Safety
  declarations, condensed policy text, and 1,506 human audit judgments with
  evidence excerpts and written rationales;
- the **replication package**: the prompts, probe sets, benchmark harness and
  analysis scripts that regenerate every table in the paper.

## Contents

| Path | What it holds |
|---|---|
| `analysis/scripts/` | Seven scripts that regenerate the paper's tables: confusion-matrix recovery, prevalence-aware re-analysis, annotator reliability, qualitative cases, corpus prevalence, label-semantics test, discrepancy taxonomy |
| `analysis/results/` | The CSV outputs those scripts produce |
| `artifact/replication/` | Dependency-free benchmark harness, probe generator, scorer, hallucination measurement, and the recorded model runs |
| `artifact/replication/data/` | Evaluation sets and probe sets |
| `artifact/replication/runs/` | Raw model outputs, one directory per model and condition |
| `ARTIFACT.md` | What can and cannot be reproduced, and the commands to do it |

Start with [`ARTIFACT.md`](ARTIFACT.md). It states plainly which results are
fully reproducible, which are reproducible only up to provider non-determinism,
and which artifacts from the original 2024 runs did not survive.

## Citing this

Cite the version you used. Release v1.0.0 is archived at Zenodo under the
version DOI [10.5281/zenodo.23102210](https://doi.org/10.5281/zenodo.23102210);
the badge above carries the concept DOI, which always resolves to the newest
release.

## The corpus

The corpus is deposited separately at Mendeley Data, under CC BY 4.0:

> Ha, Son; Pham, Nghiem; Nguyen, Triet; Vo, Khanh; Phan, Trung; Pham, Duy;
> Nguyen, Tung (2026), "DataGuard", Mendeley Data, V1,
> doi: [10.17632/2vh8pmc27y.1](https://doi.org/10.17632/2vh8pmc27y.1)

## Running it

The harness has **no third-party dependencies** — it uses only the Python
standard library, so it runs without a virtualenv:

```bash
python3 artifact/replication/run_benchmark.py --help
```

The analysis scripts need `pandas` and `scikit-learn`, and Python 3.9 or later.

Calling a hosted model needs an API key for that provider, supplied through the
environment or a `.env` file beside the harness. **No credentials are committed
to this repository**, and `.gitignore` is set up to keep it that way. The
open-weight configuration runs locally through Ollama and needs no account,
which is why it is included: a reader can re-run it identically.

Inference against a hosted model is not bit-reproducible even at temperature 0.
We report decoding parameters, repeat counts and measured self-consistency
rather than claiming determinism we cannot deliver.

## Licences

| Material | Licence |
|---|---|
| Code (`analysis/scripts/`, `artifact/replication/*.py`) | MIT — [`LICENSE-CODE.md`](LICENSE-CODE.md) |
| Data, prompts, probe sets, run outputs | CC BY 4.0 — [`LICENSE-DATA.md`](LICENSE-DATA.md) |

The package quotes short excerpts of developer-authored privacy policies and
Data Safety declarations for research analysis. Copyright in those excerpts
stays with their authors; our licence covers our selection, annotation and
arrangement.

## A note on how to read the labels

The audit judgments record whether one disclosure artifact is supported by
another. They are research annotations — **not** legal determinations of
compliance, not measurements of runtime behaviour, and not allegations of
wrongdoing by any developer. Independent trained annotators agreed on these
judgments only 52–61% of the time (Cohen's κ between −0.07 and 0.16), and the
repeated judgments are released precisely so that this uncertainty can be
modelled rather than assumed away. Please preserve that framing in any reuse
that names individual applications.
