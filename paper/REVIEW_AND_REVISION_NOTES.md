# Review And Revision Notes

## Main Review Findings

1. The original novelty claim around "robust multi-chiller scheduling with storage" was too broad because closely related robust scheduling papers already exist.
2. The paper previously treated weather only as a nominal efficiency modifier, which made the robustness story weaker than the literature positioning implied.
3. Out-of-sample evaluation originally perturbed load and tariff, but not realized weather-dependent power or available cooling, so the stress test understated ambient risk.
4. The paper narrative was stronger than the real delta supported by the code; it needed a narrower, more defensible contribution statement.

## Revisions Implemented

1. Repositioned the contribution as an `ambient-aware full-plant robust benchmark`, not a generic robust chiller scheduler.
2. Added a weather-aware robust extension to the Pyomo MILP:
   - wet-bulb-sensitive inverse-COP slopes
   - wet-bulb-dependent chiller capacity derating
   - conservative robust coefficients that keep the formulation MILP-compatible
3. Expanded out-of-sample evaluation so realized wet-bulb affects:
   - actual chiller power
   - auxiliary power
   - available cooling supply
4. Added a dedicated benchmark method:
   - `robust_full_with_storage`
5. Added a dedicated ablation pair:
   - `no_weather_robustness`
   - `with_weather_robustness`
6. Rewrote the paper text so the claims align with the actual methodological delta and latest benchmark numbers.

## Current Positioning

The strongest defensible claim is:

> A reproducible Pyomo-MILP benchmark for day-ahead scheduling of heterogeneous multi-chiller plants that jointly models storage, auxiliaries, and ambient-aware robustness under load, price, and wet-bulb uncertainty.

## Recommended Submission Framing

- Prefer `Energy and Buildings`, `Journal of Building Engineering`, or `Applied Thermal Engineering`.
- Present the work as a reproducible optimization benchmark and methodological scaffold.
- Do not present it as a deployed supervisory controller or field-validated MPC replacement.
