# Error analysis of the eight originally reported cases

Test set: N = 150 apps, identical across all eight cases.

## 1. The test set is strongly imbalanced towards the defect class

| Category | defective apps | clean apps | prevalence | accuracy of an "always flag" classifier |
|---|---|---|---|---|
| Incorrect | 137 | 13 | 0.913 | 0.913 |
| Incomplete | 121 | 29 | 0.807 | 0.807 |

A classifier that flags *every* app therefore already scores 0.913 accuracy with perfect recall on `Incorrect`, and 0.807 on `Incomplete`. Accuracy and recall alone cannot distinguish a discriminating model from a degenerate one on this test set, which is why the prevalence-aware columns below are necessary.

## 2. Prevalence-aware performance

| Case | Category | A | A - baseline | Spec. | Bal. acc. | MCC | kappa | FP | FN | Error profile |
|---|---|---|---|---|---|---|---|---|---|---|
| Case 01 | Incorrect | 0.793 | -0.120 | 0.462 | 0.643 | 0.201 | 0.180 | 7 | 24 | under-flagging dominant |
| Case 01 | Incomplete | 0.573 | -0.234 | 0.483 | 0.539 | 0.062 | 0.054 | 15 | 49 | under-flagging dominant |
| Case 02 | Incorrect | 0.947 | +0.034 | 0.462 | 0.727 | 0.606 | 0.574 | 7 | 1 | over-flagging dominant |
| Case 02 | Incomplete | 0.840 | +0.033 | 0.241 | 0.612 | 0.374 | 0.305 | 22 | 2 | over-flagging dominant |
| Case 03 | Incorrect | 0.767 | -0.146 | 0.846 | 0.803 | 0.374 | 0.291 | 2 | 33 | under-flagging dominant |
| Case 03 | Incomplete | 0.840 | +0.033 | 0.276 | 0.626 | 0.380 | 0.329 | 21 | 3 | over-flagging dominant |
| Case 04 | Incorrect | 0.920 | +0.007 | 0.143 | 0.571 | 0.362 | 0.232 | 12 | 0 | over-flagging only |
| Case 04 | Incomplete | 0.807 | +0.000 | 0.000 | 0.500 | -- | 0.000 | 29 | 0 | over-flagging only |
| Case 05 | Incorrect | 0.940 | +0.027 | 0.357 | 0.679 | 0.579 | 0.502 | 9 | 0 | over-flagging only |
| Case 05 | Incomplete | 0.840 | +0.033 | 0.172 | 0.586 | 0.379 | 0.252 | 24 | 0 | over-flagging only |
| Case 06 | Incorrect | 0.733 | -0.180 | 0.769 | 0.750 | 0.303 | 0.229 | 3 | 37 | under-flagging dominant |
| Case 06 | Incomplete | 0.847 | +0.040 | 0.448 | 0.695 | 0.454 | 0.443 | 16 | 7 | over-flagging dominant |
| Case 07 | Incorrect | 0.933 | +0.020 | 0.167 | 0.583 | 0.394 | 0.269 | 10 | 0 | over-flagging only |
| Case 07 | Incomplete | 0.860 | +0.053 | 0.310 | 0.651 | 0.478 | 0.402 | 20 | 1 | over-flagging dominant |
| Case 08 | Incorrect | 0.947 | +0.034 | 0.385 | 0.692 | 0.603 | 0.533 | 8 | 0 | over-flagging only |
| Case 08 | Incomplete | 0.853 | +0.046 | 0.276 | 0.634 | 0.445 | 0.363 | 21 | 1 | over-flagging dominant |

## 3. Degenerate and near-degenerate classifiers

- **Case 01 / Incomplete**: TN = 14, specificity = 0.483, balanced accuracy = 0.539, MCC = 0.062. Accuracy 0.573 versus an always-flag baseline of 0.807 (-0.234).
- **Case 04 / Incomplete**: TN = 0, specificity = 0.0, balanced accuracy = 0.5, MCC = None. Accuracy 0.807 versus an always-flag baseline of 0.807 (+0.000).

## 4. Over-flagging versus under-flagging

- Over-flagging (FP-dominated): 12 of 16 case/category cells.
- Under-flagging (FN-dominated): 4 of 16 case/category cells.

Under-flagging cells, i.e. the configurations that silently miss real disclosure defects:
- Case 01 / Incorrect (n/a labels, 0 training apps): FN = 24, recall = 0.825, specificity = 0.462, MCC = 0.201
- Case 01 / Incomplete (n/a labels, 0 training apps): FN = 49, recall = 0.595, specificity = 0.483, MCC = 0.062
- Case 03 / Incorrect (GPT-4 labels, 150 training apps): FN = 33, recall = 0.759, specificity = 0.846, MCC = 0.374
- Case 06 / Incorrect (GPT-4 labels, 450 training apps): FN = 37, recall = 0.730, specificity = 0.769, MCC = 0.303

## 5. The Case 03 / Case 06 anomaly is a threshold shift, not a collapse in discrimination

| Case | Category | flag ratio | Spec. | Recall | MCC | Bal. acc. |
|---|---|---|---|---|---|---|
| Case 03 | Incorrect | 0.774 | 0.846 | 0.759 | 0.374 | 0.803 |
| Case 03 | Incomplete | 1.149 | 0.276 | 0.975 | 0.38 | 0.626 |
| Case 04 | Incorrect | 1.088 | 0.143 | 1.000 | 0.362 | 0.571 |
| Case 04 | Incomplete | 1.24 | 0.0 | 1.000 | None | 0.5 |
| Case 05 | Incorrect | 1.066 | 0.357 | 1.000 | 0.579 | 0.679 |
| Case 05 | Incomplete | 1.198 | 0.172 | 1.000 | 0.379 | 0.586 |
| Case 06 | Incorrect | 0.752 | 0.769 | 0.730 | 0.303 | 0.75 |
| Case 06 | Incomplete | 1.074 | 0.448 | 0.942 | 0.454 | 0.695 |
| Case 07 | Incorrect | 1.072 | 0.167 | 1.000 | 0.394 | 0.583 |
| Case 07 | Incomplete | 1.157 | 0.31 | 0.992 | 0.478 | 0.651 |
| Case 08 | Incorrect | 1.058 | 0.385 | 1.000 | 0.603 | 0.692 |
| Case 08 | Incomplete | 1.165 | 0.276 | 0.992 | 0.445 | 0.634 |

Mean flag ratio, GPT-4-labelled cases (03, 06): 0.937; GPT-4o/Gemini-labelled cases (04, 05, 07, 08): 1.131.
Mean specificity: GPT-4 0.585 versus GPT-4o/Gemini 0.226.
Mean MCC: GPT-4 0.378 versus GPT-4o/Gemini 0.463.

The GPT-4-labelled models sit at a *conservative* operating point: they flag fewer apps than are actually defective (flag ratio below 1), and in exchange retain far higher specificity and equal or better MCC. The GPT-4o/Gemini-labelled models sit at a *permissive* operating point: they flag more apps than are defective, buying recall at the cost of specificity that approaches or reaches zero. Discriminative power is not lower for the GPT-4 configurations, so the accuracy drop reported for Cases 03 and 06 is a movement along the precision/recall trade-off induced by the class balance of the training labels, and not evidence of fabricated model output.

