# Which direction do the labels actually run?

## Test 1 (structural): are empty Data Safety sections over-represented among defect verdicts?

| Dimension | verdict | n | share with an empty Data Safety section | mean declared data types |
|---|---|---|---|---|
| sharing/correctness | Incorrect | 547 | 0.331 | 3.86 |
| sharing/correctness | Correct | 779 | 0.241 | 4.39 |
| sharing/completeness | Incomplete | 476 | 0.212 | 4.73 |
| sharing/completeness | Complete | 719 | 0.289 | 4.27 |
| collection/correctness | Incorrect | 595 | 0.390 | 3.41 |
| collection/correctness | Correct | 851 | 0.188 | 5.04 |
| collection/completeness | Incomplete | 591 | 0.281 | 3.48 |
| collection/completeness | Complete | 734 | 0.232 | 5.42 |

Empty-Data-Safety share, Incorrect minus Correct: +0.146
Empty-Data-Safety share, Incomplete minus Complete: -0.014

An app whose Data Safety section declares nothing cannot possibly declare *more* than its privacy policy. So a positive delta for `Incorrect` means `Incorrect` is recorded when the Data Safety section under-declares relative to the policy, and a negative delta for `Incomplete` means `Incomplete` requires the Data Safety section to have declared something the policy fails to match.

## Test 2 (linguistic): which document does the annotator accuse?

| Verdict | rationales | accuses the privacy policy | accuses Data Safety |
|---|---|---|---|
| Incorrect | 1089 | 0.245 | 0.173 |
| Correct | 1461 | 0.018 | 0.181 |
| Incomplete | 931 | 0.289 | 0.339 |
| Complete | 1342 | 0.073 | 0.157 |

## Conclusion

Per-axis empty-Data-Safety deltas for `Incorrect`: {'sharing/correctness': 0.09, 'collection/correctness': 0.202} -> **data-safety-under-declares**
Per-axis empty-Data-Safety deltas for `Incomplete`: {'sharing/completeness': -0.077, 'collection/completeness': 0.049} -> **inconclusive**

- **Incorrect is resolved.** Apps with an empty Data Safety section are markedly over-represented among `Incorrect` verdicts on both audit axes, and such apps declare fewer data types on average. An app that declares nothing cannot over-declare, so `Incorrect` must mean *the privacy policy mentions a data practice that the Data Safety section does not declare*. This matches the prompt in Example 1 and contradicts Appendix A, which must therefore be corrected.

- **Incomplete is not resolved.** The two audit axes disagree in sign ({'sharing/completeness': -0.077, 'collection/completeness': 0.049}), so the corpus does not license a direction. Roughly a quarter of `Incomplete` verdicts were recorded for apps whose Data Safety section declares nothing at all, which is impossible under the Appendix A reading and unexpected under the Example 1 reading. Read together with the near-zero chance-corrected agreement on this dimension (kappa = -0.066 for sharing completeness, see 03_annotator_reliability.py), the most defensible reading is that the contradictory definitions in the submitted manuscript were themselves applied inconsistently by annotators. The revised manuscript therefore states one operational definition explicitly, reuses it verbatim in the prompt and the appendix, and reports this as a limitation of the original `Incomplete` labels rather than silently picking a direction.

The rationale-wording test is reported for completeness but is not relied on: the keyword patterns are crude and the margins are small (`Incorrect`: 0.245 of rationales fault the policy versus 0.173 that fault Data Safety; `Incomplete`: 0.289 versus 0.339).
