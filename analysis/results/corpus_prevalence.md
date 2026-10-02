# DataGuard corpus: defect prevalence and difficulty predictors

Annotation corpus: 2400 apps balanced across 12 Google Play categories. Human-audited subset: 1214 apps, 1506 judgment rows, 7 annotators.

## 1. Defect prevalence per audit dimension

| Audit axis | Judgment | apps judged | defect | clean | contested | defect rate |
|---|---|---|---|---|---|---|
| Sharing | Correctness | 1083 | 384 | 596 | 103 | 0.355 |
| Sharing | Completeness | 1009 | 368 | 551 | 90 | 0.365 |
| Collection | Correctness | 1176 | 426 | 634 | 116 | 0.362 |
| Collection | Completeness | 1093 | 464 | 540 | 89 | 0.425 |

At app level, 869 of 1214 audited apps (71.6%) carry at least one disclosure defect on at least one dimension.

## 2. Prevalence by Google Play category

| Category | audited apps | any-defect rate |
|---|---|---|
| Art & Design | 200 | 0.675 |
| Beauty | 140 | 0.850 |
| Books & Reference | 145 | 0.648 |
| Business | 100 | 0.850 |
| Communication | 100 | 0.850 |
| Lifestyle | 101 | 0.832 |
| Photography | 27 | 0.630 |
| Shopping | 101 | 0.366 |
| Social | 100 | 0.550 |
| Tools | 200 | 0.790 |

## 3. Prevalence by download tier

| Download tier | audited apps | any-defect rate |
|---|---|---|
| Low (<50K) | 157 | 0.643 |
| Mid (50K-1M) | 625 | 0.730 |
| High (1M-50M) | 402 | 0.734 |
| Top (50M+) | 30 | 0.567 |

## 4. Class prior: DataGuard corpus versus the original 150-app test set

| Category | prevalence in original test set | comparable DataGuard rate |
|---|---|---|
| Incorrect | 0.913 | 0.362 |
| Incomplete | 0.807 | 0.425 |

The original test set is markedly more defect-heavy than the broader audited corpus. Accuracy figures obtained on it are therefore inflated relative to what the same model would score on a representative sample, which is the central reason the revised manuscript reports prevalence-aware metrics alongside accuracy.

## 5. Structural difficulty predictors

Among the 289 apps reviewed by more than one annotator, 222 (76.8%) produced at least one conflicting verdict.

| Predictor | contested apps | agreed apps | difference |
|---|---|---|---|
| Data Safety declares nothing | 0.347 | 0.254 | +0.093 |
| Declared data types (mean) | 5 | 7 | -2 |
| Privacy-policy length in chars (mean) | 1328 | 1156 | +172 |
| Data Safety length in chars (mean) | 1100 | 1708 | -609 |

Apps whose Data Safety section declares nothing at all, and apps with longer privacy policies, are over-represented among the contested cases. Both patterns have a clear mechanism: an empty declaration forces the annotator to decide whether a policy statement falls under one of Google's disclosure exemptions, and a longer policy offers more opportunities to find or miss a matching statement.

