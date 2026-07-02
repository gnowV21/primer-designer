# Tm Model Accuracy Report — SPEC_phase5 PART C

- Verified oligos: 0
- Tool model: SantaLucia 1998 NN + SL04 Mg²⁺/dNTP salt correction

**No verified experimental data yet.**

Populate `Experimental Tm benchmark for validating the tool's SantaLucia 1998 NN Tm prediction (SPEC_phase5 PART C). Each oligo has a published or measured Tm under defined salt conditions.` with `verified: true` entries (experimental Tm from cited papers) to enable this analysis.

## Salt correction confirmation
The tool applies the Owczarzy 2004 Mg²⁺/dNTP correction on top of the
SantaLucia 1998 nearest-neighbour model (see `backend/algorithm/thermodynamics.py`).
Parameters in use: Na⁺ equiv 50 mM, Mg²⁺ 3.0 mM, dNTP 0.8 mM, [primer] 200 nM.

*For research use only. Not for clinical in-vitro diagnostic use.*