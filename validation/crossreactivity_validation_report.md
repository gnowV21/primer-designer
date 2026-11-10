# Cross-reactivity matrix — comparison with published data

Matrix: `outputs\crossreactivity_long.parquet` (tool 3.5.0, miRBase 22.1). Cross-reactive = R ≥ 1 %.

## chen2005

File: `validation\crossreactivity_chen2005.csv` — 0/25 rows filled.
**Not independent:** ΔCq_RT constants (rG·dT 3.7 %, 0.1 %, ≤ 0.3 %) come from Chen 2005.

_no measured values yet — fill measured_value in the CSV_

## mestdagh2014

File: `validation\crossreactivity_mestdagh2014.csv` — 0/0 rows filled.

_no measured values yet — fill measured_value in the CSV_

## Sanity check — near-identical vs random pairs

- 322 ordered pairs of equal-length miRNAs differing at 1–2 positions: mean R 0.1414, median 0.0089, 21.1 % above 10 %.
- 20000 random pairs: mean R 0.000011, 0.000 % above 10 %.
- passes (close mean > 10 × random mean): **True**
