# Tm Model Accuracy Report — SPEC_phase5 PART C

- Verified oligos: 0
- Tool model: SantaLucia 1998 NN + SL04 Mg²⁺/dNTP salt correction

**No verified experimental data yet.**

Populate `Experimental Tm benchmark to validate the tool's nearest-neighbour Tm model INDEPENDENTLY. Each oligo must have an EXPERIMENTALLY MEASURED duplex Tm (UV-melting / DSC) under stated salt conditions.` with `verified: true` entries (experimental Tm from cited papers) to enable this analysis.

## Salt correction confirmation
Base model: SantaLucia 1998 nearest-neighbour (see `backend/algorithm/thermodynamics.py`).
Note on citations: the Mg²⁺/dNTP salt correction is **Owczarzy 2008** (DOI 10.1021/bi702363u), NOT Owczarzy 2004 (DOI 10.1021/bi034621r, which is Na⁺-only). Verify which correction thermodynamics.py actually implements before citing it in the paper.
Parameters in use: Na⁺ equiv 50 mM, Mg²⁺ 1.5 mM, dNTP 0.8 mM, [primer] 200 nM (must match constants.py).

*For research use only. Not for clinical in-vitro diagnostic use.*