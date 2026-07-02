# Scoring-weight calibration report

- N (verified assays used): **0**
- Decision: **KEEP V4 (no verified data)**  

## Per-criterion correlation with real outcome (sorted by |Pearson r|)

| Criterion | Pearson r | Spearman r | V4 weight | V5 weight |
|---|---|---|---|---|
| tm_accuracy | +0.000 | +0.000 | 0.200 | — |
| mfe_stemloop | +0.000 | +0.000 | 0.140 | — |
| tm_binding_accuracy | +0.000 | +0.000 | 0.100 | — |
| hairpin_penalty | +0.000 | +0.000 | 0.080 | — |
| dimer_penalty | +0.000 | +0.000 | 0.080 | — |
| end_stability | +0.000 | +0.000 | 0.080 | — |
| bound_fraction_binding | +0.000 | +0.000 | 0.050 | — |
| bound_fraction_full | +0.000 | +0.000 | 0.030 | — |
| gc_content | +0.000 | +0.000 | 0.080 | — |
| family_discrimination | +0.000 | +0.000 | 0.050 | — |
| tm_pair_match | +0.000 | +0.000 | 0.010 | — |
| gc_clamp | +0.000 | +0.000 | 0.040 | — |
| primer_size | +0.000 | +0.000 | 0.020 | — |
| amplicon_size | +0.000 | +0.000 | 0.020 | — |
| gc_skew | +0.000 | +0.000 | 0.020 | — |

## Cross-validation
- LOOCV RMSE (V4 prior): n/a
- LOOCV RMSE (calibrated): n/a
- chosen lambda: n/a

## Notes
- No verified assays. Populate benchmark_assays.json with per-assay efficiency transcribed from cited papers (verified=true).

*Interpretation only; not ground truth. Data from PubMed-cited sources.*