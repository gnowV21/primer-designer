# Tm Model Accuracy Report — SPEC_phase5 PART C

- **default mode**: single reference column per oligo (34 data points)
- Tool model: SantaLucia 1998 NN (primer3-py, `salt_corrections_method='santalucia'`)
- Salt correction pipeline (confirmed from primer3 C source, oligotm.c):
  - Na⁺ series: SantaLucia entropy correction directly on K_mM (Na⁺ only).
    → **Owczarzy 2004 Na⁺ data: fully independent** validation of monovalent salt correction.
  - Mg²⁺ series: step 1 = von Ahsen 2001 divalent→monovalent `120√(Mg−dNTP)`; step 2 = SantaLucia entropy on combined K_mM.
    → **Owczarzy 2008 Mg²⁺ data: fully independent** from both steps (von Ahsen 2001 ≠ Owczarzy formula; SantaLucia 1998 ≠ Owczarzy 2008).
  - **No circularity** for either series — safe to report both as independent validation.
- Predictions at **each data point's measured conditions** (per-oligo salt/Ct from benchmark).
- Ct convention: `primer_conc_nm` = Ct (total strand); passed directly to primer3.calc_tm which divides by 4 internally.
- RT primers excluded: DNA:RNA hybrid Tm uses DNA:DNA NN params (approx. only); only forward/reverse (DNA:DNA) are validated here.
- Experimental noise floor: σ(Tm) ≈ 0.3 °C (Owczarzy 2008); errors within 1–2 °C are excellent.

## Summary by dataset

| Series | N | MAE (°C) | Bias (°C) | Source |
|---|---|---|---|---|
| **All** | 34 | 2.69 | -2.65 | — |
| Mg²⁺ series (Owczarzy 2008) | 18 | 3.12 | -3.06 | DOI 10.1021/bi702363u |
| Na⁺ series (Owczarzy 2004)  | 16 | 2.19 | -2.19 | DOI 10.1021/bi034621r |

## Summary by oligo length

| Length | N | MAE (°C) | Bias (°C) |
|---|---|---|---|
| ≤12 nt | 10 | 3.75 | -3.75 |
| 13–20 nt | 14 | 2.32 | -2.32 |
| 21+ nt | 10 | 2.13 | -2.01 |

## Summary by GC%

| GC% | N | MAE (°C) | Bias (°C) |
|---|---|---|---|
| ≤40% | 12 | 3.10 | -3.10 |
| 41–65% | 12 | 2.72 | -2.72 |
| >65% | 10 | 2.15 | -2.03 |

⚠ **Systematic bias = -2.65°C** (threshold ±1.5°C). Tool under-predicts Tm.

Possible causes: (1) SantaLucia salt correction underestimates Mg²⁺ stabilisation at low [Na⁺] (1 mM Tris buffer); (2) NN parameters slightly off for short oligos (≤12 nt); (3) benchmark conditions (1 mM monovalent, no dNTP) differ from tool defaults (50 mM Na + 1.5 mM Mg + 0.8 mM dNTP). Do NOT adjust `TM_FORWARD_TARGET` without in-lab measurements at tool conditions.

## Per-data-point results

| ID | nt | GC% | Na (mM) | Mg (mM) | Tm exp | Tm pred | Error |
|---|---|---|---|---|---|---|---|
| owc08_10mer_01 | 10 | 30 | 1 | 1.5 | 30.9 | 25.6 | -5.2 |
| owc08_10mer_02 | 10 | 50 | 1 | 1.5 | 38.9 | 35.1 | -3.8 |
| owc08_10mer_03 | 10 | 70 | 1 | 1.5 | 47.7 | 43.7 | -4.0 |
| owc08_10mer_04 | 10 | 80 | 1 | 1.5 | 51.9 | 47.4 | -4.5 |
| owc08_11mer_05 | 11 | 54 | 1 | 1.5 | 44.2 | 40.6 | -3.6 |
| owc08_11mer_06 | 11 | 54 | 1 | 1.5 | 42.7 | 38.6 | -4.1 |
| owc08_15mer_07 | 15 | 33 | 1 | 1.5 | 46.1 | 43.1 | -3.0 |
| owc08_15mer_08 | 15 | 53 | 1 | 1.5 | 55.1 | 52.8 | -2.3 |
| owc08_15mer_09 | 15 | 73 | 1 | 1.5 | 64.1 | 61.6 | -2.5 |
| owc08_20mer_10 | 20 | 30 | 1 | 1.5 | 54.6 | 51.3 | -3.3 |
| owc08_20mer_11 | 20 | 50 | 1 | 1.5 | 63.7 | 62.0 | -1.7 |
| owc08_20mer_12 | 20 | 70 | 1 | 1.5 | 71.3 | 69.0 | -2.3 |
| owc08_25mer_13 | 25 | 32 | 1 | 1.5 | 59.7 | 55.0 | -4.7 |
| owc08_25mer_14 | 25 | 52 | 1 | 1.5 | 67.7 | 64.0 | -3.7 |
| owc08_25mer_15 | 25 | 72 | 1 | 1.5 | 75.3 | 74.9 | -0.4 |
| owc08_30mer_16 | 30 | 30 | 1 | 1.5 | 63.1 | 59.1 | -4.0 |
| owc08_30mer_17 | 30 | 50 | 1 | 1.5 | 71.6 | 69.1 | -2.5 |
| owc08_30mer_18 | 30 | 70 | 1 | 1.5 | 77.8 | 78.4 | +0.6 |
| owc04_na_01 | 10 | 20 | 69 | 0 | 21.3 | 17.1 | -4.2 |
| owc04_na_02 | 10 | 40 | 69 | 0 | 29.0 | 26.2 | -2.8 |
| owc04_na_03 | 10 | 60 | 69 | 0 | 39.2 | 36.7 | -2.5 |
| owc04_na_04 | 10 | 80 | 69 | 0 | 46.7 | 43.9 | -2.8 |
| owc04_na_05 | 15 | 20 | 69 | 0 | 35.3 | 33.0 | -2.3 |
| owc04_na_06 | 15 | 40 | 69 | 0 | 45.5 | 43.4 | -2.1 |
| owc04_na_07 | 15 | 60 | 69 | 0 | 52.8 | 51.4 | -1.4 |
| owc04_na_08 | 15 | 80 | 69 | 0 | 64.9 | 62.3 | -2.6 |
| owc04_na_09 | 20 | 20 | 69 | 0 | 44.4 | 41.5 | -2.9 |
| owc04_na_10 | 20 | 45 | 69 | 0 | 55.6 | 53.2 | -2.4 |
| owc04_na_11 | 20 | 55 | 69 | 0 | 59.6 | 57.2 | -2.4 |
| owc04_na_12 | 20 | 80 | 69 | 0 | 70.9 | 69.6 | -1.3 |
| owc04_na_13 | 25 | 20 | 69 | 0 | 49.1 | 46.9 | -2.2 |
| owc04_na_14 | 25 | 40 | 69 | 0 | 59.1 | 58.6 | -0.5 |
| owc04_na_15 | 25 | 56 | 69 | 0 | 68.3 | 66.1 | -2.2 |
| owc04_na_16 | 25 | 80 | 69 | 0 | 76.8 | 76.3 | -0.5 |

## Prediction method
- Base NN: SantaLucia 1998 (DOI 10.1073/pnas.95.4.1460) via primer3-py.
- Salt correction (`salt_corrections_method='santalucia'`, primer3-py default, confirmed from oligotm.c):
  - Na⁺: SantaLucia entropy correction on K_mM. Owczarzy 2004 Na⁺ = independent validation. ✓
  - Mg²⁺: von Ahsen 2001 [DOI 10.1093/clinchem/47.11.1956] converts Mg²⁺−dNTP → K_equiv = 120√(Mg−dNTP), then SantaLucia entropy on K_mM+K_equiv. Owczarzy 2008 Mg²⁺ = independent from both steps. ✓
  - No circularity for either series.
- Validation datasets are independent of the SantaLucia 1998 training set.
- Short oligos (≤12 nt): larger prediction errors expected (boundary of NN validity).
- Experimental noise floor: σ(Tm) ≈ 0.3 °C (Owczarzy 2008, UV-melting). Model errors within 1–2 °C are excellent relative to this baseline.
- ⚠ DNA:RNA hybrid: RT primer Tm uses DNA:DNA NN params. Actual RT primer Tm on miRNA target (DNA:RNA hybrid) may differ by 3–8 °C (Sugimoto 1995 DNA:RNA params not implemented). RT primers are excluded from this validation.

*For research use only. Not for clinical in-vitro diagnostic use.*