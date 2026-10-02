# Human reliability on the disclosure-audit task (DataGuard corpus)

Audit rows: 1506; unique apps: 1214; annotators: 7.
Apps carrying two or more independent judgments: 289.

These are first-pass independent judgments recorded before any adjudication, so they measure the raw difficulty of the task rather than the quality of the final adjudicated labels.

## Pairwise agreement between independent annotators

| Audit axis | Judgment | pairs | raw agreement | Cohen's kappa | PABAK | defect rate |
|---|---|---|---|---|---|---|
| Sharing | Correctness | 246 | 0.565 | 0.141 | +0.130 | 0.465 |
| Sharing | Completeness | 188 | 0.521 | -0.066 | +0.043 | 0.340 |
| Collection | Correctness | 273 | 0.560 | 0.107 | +0.121 | 0.418 |
| Collection | Completeness | 235 | 0.613 | 0.156 | +0.226 | 0.355 |

Raw agreement spans 0.521-0.613 and Cohen's kappa spans -0.066-0.156 across the four dimensions. On a binary decision with near-balanced marginals, chance agreement is about 0.50, so trained annotators working independently agree only slightly above chance.

## Per-annotator defect rates

Systematic differences in how often each annotator records a defect indicate that disagreement is partly a calibration effect rather than random noise.

| Annotator | role | rows | Sharing/Incorrect | Sharing/Incomplete | Collection/Incorrect | Collection/Incomplete |
|---|---|---|---|---|---|---|
| A01 | PhD | 172 | 0.361 | 0.551 | 0.466 | 0.770 |
| A02 | Student | 63 | 0.143 | 0.175 | 0.238 | 0.163 |
| A03 | Student | 45 | 0.349 | 1.000 | 0.444 | 1.000 |
| A04 | Student | 143 | 0.329 | 0.594 | 0.315 | 0.801 |
| A05 | Student | 593 | 0.388 | 0.410 | 0.324 | 0.520 |
| A06 | Student | 427 | 0.641 | 0.298 | 0.621 | 0.142 |
| A07 | Student | 63 | 0.033 | 1.000 | 0.115 | 1.000 |

Across-annotator spread in defect rate: Sharing/Correctness 0.608, Sharing/Completeness 0.825, Collection/Correctness 0.506, Collection/Completeness 0.858.

## Difficult cases

403 app/dimension cells received conflicting verdicts from independent annotators, spanning 222 distinct apps. These are written to `difficult_apps.csv` and form the natural difficult-case pool for qualitative error analysis.

Conflicts by dimension:
- Collection / Completeness: 90
- Collection / Correctness: 118
- Sharing / Completeness: 90
- Sharing / Correctness: 105

