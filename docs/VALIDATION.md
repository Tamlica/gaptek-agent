# Validation

A gaptek run is only credible if, on a reference flow, it finds **at least the majority** of the
issues that 3–5 real non-technical people find on the same flow (SPEC §12). Until a flow has an
entry here, treat its findings as unvalidated hypotheses.

## Protocol

1. Pick one reference flow on a real app (planned: MakanMap order flow) and freeze the app version.
2. **Real sessions:** 3–5 people matching a persona (age, device, English level). Same goal text as
   `goal_for_persona`, same phone model class, no help. Record screen + think-aloud. Note every
   point of hesitation, wrong tap, question, or giving up, with the screen.
3. **Simulated sessions:** `gaptek batch --personas personas/ --task tasks/<flow>.yaml
   --runs-per-persona 5`. Keep `summary.json` and the run dirs.
4. **Match:** list unique issues from the real sessions (the ground truth). For each, mark whether
   any simulated run reported it (same screen, same cause). Also list simulated issues no real
   person hit (possible false positives).
5. **Tune** on mismatches (vocabulary lists, `max_words_read`, `min_noticed_font_px`, miss rates,
   patience), then re-run step 3. Record the change and why. Do not tune on the flow you report.

## Results

| Date | App / flow | App version | Real people (n) | Real issues | Found by gaptek | Recall | False positives | Persona / settings |
|------|-----------|-------------|-----------------|-------------|-----------------|--------|-----------------|--------------------|
| _none yet_ | | | | | | | | |

## Mismatch log

| Date | Issue | Real | Simulated | Likely cause | Change made |
|------|-------|------|-----------|--------------|-------------|
| | | | | | |
