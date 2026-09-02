# Trade Desk Dynasty Trade Calculator — Technical Model Breakdown

**Repository:** `ajknoll23-code/LOG-Trade-Calculator`  
**Production source of truth:** `index.html`  
**Technical snapshot:** 2026-09-01  
**Verified production commit:** `15a97c4c6b312385465d564fe1d00b7acdece2b8`  
**Verification status:** `Repo Regression Checks #80` passed on the verified commit.

---

## 1. Purpose of This Document

This document is the repo-level technical reference for the League of Ordinary Gentlemen Dynasty Trade Calculator, referred to throughout the repository as **Trade Desk**.

It explains:

- the deployed **Fundamental Value** model;
- the production-history and forward-projection systems feeding player valuation;
- the frozen **IDP V1** projection and production-multiplier release;
- age, role, positional-economics, and draft-pick valuation;
- the separate **Market Value** layer;
- the separate **Team Utility** / post-trade roster-simulation layer;
- value uncertainty / sensitivity envelopes;
- historical out-of-sample backtesting;
- Sleeper, FantasyPros, KTC, identity, free-agent, and maintenance pipelines;
- automation and CI/regression controls;
- frozen-release boundaries;
- known limitations and future calibration targets.

This is a **descriptive technical document**, not a second implementation of the model.

If this document ever disagrees with production code, use the following precedence:

```text
1. index.html for deployed Fundamental Value behavior
2. canonical scripts under scripts/ for pipeline behavior
3. frozen release artifacts under model/releases/ for historical release truth
4. generated artifacts for the state of the latest successful refresh
5. this document as explanatory documentation
```

The model is deliberately designed so that **Fundamental Value, Market Value, Team Utility, and Value Uncertainty are distinct concepts**. They may be displayed together, but they do not silently overwrite or blend into one another.

---

# 2. Current Project Status

The five major calculator-improvement workstreams are implemented:

```text
1. Post-trade roster simulation / roster-slot economics     COMPLETE
2. Historical backtesting / out-of-sample infrastructure   COMPLETE
3. Positional-weight revalidation V1                       COMPLETE
4. Expected value ranges / uncertainty modeling            COMPLETE
5. Fundamental / Market / Team Utility separation          COMPLETE
```

The main item that inherently requires time is historical backtesting. The infrastructure is live and automatically captures model states and future outcomes, but reliable recalibration decisions require real future 2026 NFL weeks to accumulate.

The current production architecture should therefore be treated as:

```text
                        ┌────────────────────────────┐
                        │        SOURCE DATA         │
                        │ Sleeper / FantasyPros /    │
                        │ League KTC votes / rosters │
                        └─────────────┬──────────────┘
                                      │
                         identity + scoring + QC
                                      │
              ┌───────────────────────┴───────────────────────┐
              │                                               │
              ▼                                               ▼
   ┌───────────────────────┐                       ┌───────────────────────┐
   │   FUNDAMENTAL MODEL   │                       │   MARKET OBSERVATION  │
   │ position × age × prod │                       │ league KTC voting     │
   └───────────┬───────────┘                       └───────────┬───────────┘
               │                                               │
               │                                      quantile calibration
               │                                               │
               ▼                                               ▼
     Fundamental Value                               Market Value
               │
               ├──────────────► Value Uncertainty envelope
               │
               └──────────────► Team Utility roster simulation

All layers ───────────────► append-only historical snapshots ─► future evaluators
```

---

# 3. Canonical Repository Architecture

## 3.1 Production entry points

```text
index.html
free-agent-board.html
config.json
data/
```

### `index.html`

The canonical deployed Trade Desk calculator.

It contains the live:

- `PLAYER_DB`;
- `POSITION_WEIGHT`;
- `AGE_CURVE`;
- `ROLE_MULT`;
- `PROD_MULT_DATA`;
- `NO_REAL_PRODUCTION_HISTORY`;
- `QB_POST_PEAK_FLOOR`;
- `LB_POST_PEAK_DECAY_POWER`;
- `productionMultiplier()`;
- `ageMultiplier()`;
- `playerValue()`;
- draft-pick valuation tables;
- trade UI;
- Market Value display integration;
- Team Utility / roster simulation;
- league roster metadata used by the client.

### `free-agent-board.html`

A generated free-agent experience that consumes the same canonical valuation engine as `index.html`.

It is **not** an independent model.

### `data/`

Current league state synchronized from Sleeper, including rosters, picks, player/cache information, and the free-agent dataset.

---

## 3.2 Canonical implementation folders

```text
scripts/model/
scripts/projections/
scripts/market/
scripts/sync/
scripts/maintenance/
scripts/utilities/
scripts/validation/
scripts/artifacts/generated/
scripts/artifacts/reports/
research/
model/releases/
docs/current/
```

### Model code

```text
scripts/model/ppg_pipeline.py
scripts/model/production_history_component.py
scripts/model/idp_v1_projection.py
```

### Projection and identity pipelines

```text
scripts/projections/sleeper_projections_pipeline.py
scripts/projections/fantasypros_api_pipeline.py
scripts/projections/resolve_fantasypros_sleeper_identity.py
scripts/projections/filter_sleeper_idp_only.py
```

### Market layer

```text
scripts/market/ktc_pipeline.py
scripts/market/build_market_value.py
scripts/market/draft_slot_projection_pipeline.py
```

### Synchronization

```text
scripts/sync/sync_sleeper.py
scripts/sync/sync_trade_history.py
scripts/sync/sync_free_agent_valuation.py
```

### Validation / evidence

```text
scripts/validation/snapshot_values.py
scripts/validation/build_value_uncertainty.py
scripts/validation/capture_model_history.py
scripts/validation/capture_realized_outcomes.py
scripts/validation/evaluate_model_history.py
scripts/validation/evaluate_market_history.py
scripts/validation/repo_regression_checks.py
scripts/validation/validate_free_agent_valuation_parity.py
scripts/validation/validate_idp_v1_final_deployment.py
```

### Frozen model releases

```text
model/releases/idp-v1/
```

A frozen production release is an audit package. It must never be treated as ordinary rolling generated state.

---

# 4. Fundamental Value: Core Production Formula

The deployed player-value center is:

```text
Fundamental Value
  = round(100 × PositionWeight × AgeMultiplier × ProductionMultiplier × 55)
```

In code:

```javascript
return Math.round(100 * pw * am * rm * 55);
```

where:

```text
pw = positional economic weight
am = age multiplier
rm = production multiplier after live production/role fallback rules
55 = global point-scale constant
```

The `100 × 55` scale gives a convenient dynasty trade-value range. It does not change player ordering by itself; ordering comes from the interacting positional, age, and production components.

The canonical Python parity implementation lives in:

```text
scripts/validation/snapshot_values.py
```

That script parses the constants directly from `index.html` and reproduces the JavaScript valuation for regression testing.

A key implementation detail is JavaScript rounding parity. JavaScript `Math.round()` rounds positive `.5` ties upward, whereas Python's built-in `round()` uses bankers' rounding. The Python parity layer therefore uses:

```python
math.floor(raw_value + 0.5)
```

for positive Trade Desk values.

---

# 5. Position Weight

## 5.1 Current deployed weights

```text
QB  1.30
RB  0.89
WR  1.00
TE  0.82
DL  0.93
LB  1.12
DB  0.87
K   0.35
```

WR is effectively the 1.00 reference scale.

Position weight represents **league-specific positional economics**, not a forecast of points.

It exists because a fantasy point scored by one position does not necessarily have the same dynasty scarcity or replacement economics as a fantasy point scored by another position.

Examples of the intended distinction:

- QBs receive a premium because this is a Superflex league.
- LB carries the strongest IDP weight in the current V1 positional economics.
- TE, DL, and DB have lower weights than WR/LB because their replacement/scarcity economics differ.
- K intentionally carries a very low dynasty capital weight.

## 5.2 What position weight is not

It is not:

- a projection multiplier;
- an age adjustment;
- a role adjustment;
- a direct KTC market score;
- a Team Utility adjustment.

A player can have elite raw production but a lower final Fundamental Value than a similarly dominant player at a scarcer position because positional economics are intentionally separate from production quality.

## 5.3 Revalidation philosophy

The current weights are the result of the positional-weight revalidation workstream.

The important architectural change is not merely the exact numbers. It is the separation of:

```text
production quality
        from
position-specific dynasty economics
```

Future changes to `POSITION_WEIGHT` should be treated as explicit model releases/recalibrations and validated through historical evidence, market evidence, roster economics, and regression checks.

They must not be rewritten automatically by the refresh workflow.

---

# 6. Role Multipliers

Current role multipliers:

```text
Elite        1.40
Every-Down   1.15
Starter      1.00
Rotational   0.65
Understudy   0.57
Depth        0.35
Speculative  0.22
```

Role is primarily a **fallback / structural context layer**.

The production engine prefers player-specific production information when it exists. Role becomes more important when the player does not have trustworthy production history.

This distinction is essential.

A role label should not routinely override real player evidence.

## 6.1 Understudy

`Understudy = 0.57` exists as a distinct tier between rotational/depth/speculative treatment.

Its purpose is to represent a player who has meaningful talent or investment and is one role transition away from major value, rather than treating all non-starters as generic speculative assets.

## 6.2 Role and real production

The live engine uses:

```text
real production data first
role estimate second
```

with explicit exceptions documented below.

---

# 7. Production Multiplier

Production is the most player-specific multiplicative component in the Fundamental Value equation.

The deployed lookup table is:

```text
PROD_MULT_DATA
```

inside `index.html`.

The live lookup/fallback behavior is implemented by:

```text
productionMultiplier()
```

## 7.1 Production-source hierarchy

For a normal canonical Trade Desk player:

```text
1. Use PROD_MULT_DATA if the normalized player key exists.
2. Apply the Elite floor rule when necessary.
3. Apply the no-real-history floor rescue only when lineage allows it.
4. Otherwise return the raw production multiplier.
5. If no player-specific production exists, fall back to ROLE_MULT.
```

## 7.2 Elite production floor

If a player is explicitly tagged `Elite` and their raw production multiplier is below `0.65`, the live engine returns:

```text
0.65
```

instead.

This prevents an Elite-tagged player from collapsing beneath the model's established elite production floor.

## 7.3 No-real-production-history floor rescue

A more delicate rule exists for players at the raw production floor.

The model has a separate baked lineage set:

```text
NO_REAL_PRODUCTION_HISTORY
```

If all of the following are true:

```text
raw production <= 0.15
role estimate > raw production
player is explicitly flagged as having no real production history
```

then the role estimate can rescue the raw floor.

The lineage gate matters.

Without it, a veteran who actually produced poorly could be incorrectly rescued upward merely because a generic role tag says they should be better.

The current rule distinguishes:

```text
"we have evidence this player produced poorly"
from
"we do not have real production evidence"
```

## 7.4 Raw production range

The historical production framework uses a bounded multiplier range centered around replacement-level economics:

```text
floor   0.15
ceiling 1.55
```

Not every current production entry is reproducible from one single modern pipeline. That is intentional technical debt documented later in this file.

---

# 8. Production Lineage: Offense vs. IDP

This is one of the most important distinctions in the entire model.

## 8.1 Offense

For:

```text
QB
RB
WR
TE
K
```

the deployed production values retain the existing historical `PROD_MULT_DATA` lineage.

They were **not rewritten during IDP V1**.

The known caveat is that the current legacy reconstruction pipeline does not reproduce the full historical baked offense/overall table exactly.

Therefore:

```text
current deployed PROD_MULT_DATA = production source of truth
legacy reconstruction          = diagnostic/research lineage tool
```

Do not describe the legacy generator as if it were a fully reproducible source of the old table until the legacy `PROD_MULT_DATA` lineage workstream is explicitly closed.

## 8.2 IDP

For:

```text
LB
DL
DB
```

the production projection side was upgraded in the frozen IDP V1 release.

IDP V1 did not blindly regenerate every multiplier from scratch.

Instead, it used a controlled **model-delta transport** process so that:

- the validated new IDP projection model could affect production;
- unrelated historical production-lineage differences were not silently rewritten;
- offense remained unchanged;
- players without comparable old projections could be held;
- migration discontinuities could be guarded.

The frozen release is:

```text
model/releases/idp-v1/
```

---

# 9. True Historical PPG

Canonical implementation:

```text
scripts/model/ppg_pipeline.py
```

The history pipeline reconstructs active-game fantasy scoring from raw Sleeper weekly statistics using **this league's scoring rules**.

Its purpose is to avoid a major modeling error:

```text
season total / 17
```

conflates:

```text
quality while active
with
games missed
```

Instead, the pipeline separates them.

For each player it records:

```text
games_played
weekly_points
total_points
true_ppg
season_total_ppg
weeks_played
```

The production-history component can therefore model:

```text
performance rate
and
availability
```

separately.

---

# 10. League Scoring Used by the Historical / Sleeper Projection Pipelines

The canonical historical scoring implementation includes the league's custom rules.

## 10.1 Passing

```text
0.04 per passing yard
4.0  per passing TD
2.0  per passing 2-point conversion
-2.0 per interception

300+ passing yards: +2
400+ passing yards: +3 total threshold bonus
```

## 10.2 Rushing

```text
0.2 per rush attempt
0.1 per rushing yard
6.0 per rushing TD
2.0 per rushing 2-point conversion

100+ rushing yards: +2
200+ rushing yards: +3 total threshold bonus
```

## 10.3 Receiving

```text
0.5 per reception
0.1 per receiving yard
6.0 per receiving TD
2.0 per receiving 2-point conversion

100+ receiving yards: +2
200+ receiving yards: +3 total threshold bonus
```

## 10.4 Fumbles

```text
-2.0 lost fumble
+6.0 fumble-recovery TD
```

## 10.5 IDP

```text
1.50 solo tackle
0.75 assisted tackle
2.00 tackle for loss
3.00 sack
2.00 QB hit
6.00 interception
4.00 fumble recovery
3.00 forced fumble
3.00 safety
6.00 blocked kick
6.00 defensive TD
3.00 pass defended
```

IDP weekly bonuses include:

```text
10+ combined tackles: +2
2+ sacks:             +2
3+ passes defended:   +2
```

## 10.6 Special teams

```text
6.0 special-teams TD
3.0 special-teams forced fumble
3.0 special-teams fumble recovery
```

The Sleeper projection pipeline scores weekly forward projections through the same scoring concept.

FantasyPros season-total projections require special handling because per-game milestone thresholds cannot always be reconstructed from season aggregates.

---

# 11. Production History Component

Canonical implementation:

```text
scripts/model/production_history_component.py
```

This module deliberately separates **history math** from forward projection-source logic.

## 11.1 Empirical-Bayes PPG shrinkage

For a player with real history:

```text
shrunk_ppg
  = (n × true_ppg + k[pos] × position_mean_ppg)
    / (n + k[pos])
```

where:

```text
n                 = 2025 games played
true_ppg          = observed active-game PPG
position_mean_ppg = position cohort mean
k[pos]            = empirical shrinkage strength
```

The shrinkage constant is derived from:

```text
k[pos] = within-player variance / between-player variance
```

using real weekly scoring data.

Interpretation:

- more games -> more trust in the player's own PPG;
- fewer games -> more pull toward the position mean;
- no real 2025 history -> full shrinkage to the position mean.

## 11.2 Availability model

The preserved V1 availability formula is:

```text
projected_availability_2026
  = own_weight[pos] × own_availability_2025
  + (1 - own_weight[pos]) × position_median_availability_2025
```

and:

```text
projected_games_2026
  = projected_availability_2026 × 17
```

The current `own_weight[pos]` is:

```text
clamp(position durability R², 0, 1)
```

For a player with no own history:

```text
own_weight = 0
```

and the player relies completely on position-median availability.

## 11.3 History component

```text
history_component
  = shrunk_ppg × projected_games_2026
```

This produces a projected full-season production contribution based on historical performance rate and availability.

## 11.4 Important durability caveat

The current R²-as-own-weight interpretation is intentionally preserved from the legacy methodology.

It has **not** been declared the final optimal durability model.

Durability weighting is a separate future calibration workstream.

---

# 12. Sleeper Forward Projection Pipeline

Canonical implementation:

```text
scripts/projections/sleeper_projections_pipeline.py
```

The pipeline queries Sleeper's forward projection endpoint across the 18-week regular-season fantasy schedule:

```text
/v1/projections/nfl/regular/2026/{week}
```

It then:

1. scores each weekly projection under the league's custom rules;
2. sums projected points across the season;
3. stores weeks with data;
4. independently accumulates raw projected categories.

Outputs include:

```text
scripts/sleeper_2026_projections.json
scripts/artifacts/generated/sleeper_2026_raw_categories.json
scripts/artifacts/generated/sleeper_2026_raw_weekly.json
```

The category-level output is critical for IDP V1 because final point totals can hide *why* two projection providers disagree.

---

# 13. FantasyPros Projection Pipeline

Canonical implementation:

```text
scripts/projections/fantasypros_api_pipeline.py
```

## 13.1 Principle

Trade Desk does **not** trust a provider's precomputed fantasy-point total as the canonical projection.

Instead:

```text
provider raw categories
        ↓
Trade Desk league scoring
        ↓
normalized projected points
```

This keeps scoring consistent between:

- historical actuals;
- Sleeper projections;
- FantasyPros projections.

## 13.2 Identity

FantasyPros `fpid` is the primary FantasyPros-side identity.

Names are secondary matching metadata.

The production pipeline deliberately moved away from using normalized lowercase names as if they were globally unique IDs.

## 13.3 Defensive population

The pipeline uses the combined FantasyPros:

```text
IDP
```

endpoint rather than separately merging LB/DL/DB endpoint populations.

That avoids double-counting multi-position defensive players.

## 13.4 Known FantasyPros structural gaps

FantasyPros does not expose every category required by this league's scoring model.

The most important documented gap is:

```text
QB hits
```

which this league scores but FantasyPros does not provide in the confirmed schema.

Per-game milestone bonuses also cannot safely be reconstructed from simple season-total category aggregates unless the provider supplies valid populated milestone-count fields.

Missing categories are recorded as data-quality information rather than silently represented as known zeros.

---

# 14. FantasyPros ↔ Sleeper Identity Resolution

Canonical implementation:

```text
scripts/projections/resolve_fantasypros_sleeper_identity.py
```

Cross-provider projection blending requires trustworthy player identity.

The model therefore treats:

```text
stable provider IDs
```

as superior to:

```text
display-name matching
```

The identity crosswalk:

```text
scripts/identity_crosswalk.json
```

exists so IDP and uncertainty systems can align FantasyPros observations to Sleeper players without assuming names are globally unique.

The resolver retains:

- match method;
- confidence;
- position information;
- collision / manual-review information;
- candidate IDs where resolution is uncertain.

This is essential because real player-name collisions and dual eligibility have already caused concrete bugs in earlier versions of the project.

---

# 15. IDP V1 Projection Ensemble

Canonical reusable implementation:

```text
scripts/model/idp_v1_projection.py
```

Frozen production package:

```text
model/releases/idp-v1/
```

IDP V1 operates at the **stat-category level**, not by naively averaging final fantasy-point projections.

## 15.1 Source activity is explicit

The implementation distinguishes:

```text
source row exists
source has meaningful V1 signal
source has positive tackle signal
```

These are not the same thing.

A provider can have a real row containing zeros. It must not be treated as a meaningful forecast simply because a row exists.

## 15.2 Stage 1: total tackles

If both providers have positive tackle projections:

```text
consensus_total_tackles
  = 0.50 × FantasyPros total tackles
  + 0.50 × Sleeper total tackles
```

## 15.3 Stage 2: solo share

Let:

```text
FP solo share      = FP solo / FP total tackles
Sleeper solo share = Sleeper solo / Sleeper total tackles
```

Then:

```text
consensus_solo_share
  = 0.40 × FP solo share
  + 0.60 × Sleeper solo share
```

and:

```text
consensus solo   = consensus total × consensus solo share
consensus assist = consensus total - consensus solo
```

Tackle points are then scored:

```text
1.50 × consensus solo
+ 0.75 × consensus assists
```

## 15.4 Sleeper-only categories

Current V1 treats these as Sleeper-only:

```text
TFL
QB hits
```

because FantasyPros does not provide equivalent usable fields.

## 15.5 Shared big-play categories

When both sources are meaningfully active, the following are combined 50/50:

```text
sacks
interceptions
passes defended
forced fumbles
fumble recoveries
defensive TDs
```

If only one provider is meaningfully active, the active provider is used directly.

The model does **not** average a valid source against a zero-signal placeholder.

## 15.6 No-new-data rule

If neither provider has meaningful V1 signal:

```text
preserve caller-provided old projection
```

rather than inventing zero production.

This is one of the release's key missing-data protections.

---

# 16. IDP V1: History + Projection Combination

For comparable IDP players, the V1 candidate framework uses:

```text
combined
  = 0.45 × history_component
  + 0.55 × forward_projection
```

The frozen model-delta transport artifact records:

```text
history_weight    = 0.45
projection_weight = 0.55
replacement_rank  = 32
```

for LB, DL, and DB production economics.

The replacement-level comparison is computed separately by position.

---

# 17. IDP V1 Model-Delta Transport

This is a subtle but important release-engineering decision.

The old live production table had historical lineage that could not be perfectly reconstructed.

Therefore IDP V1 did **not** assume:

```text
new reconstructed prod_mult
```

could simply replace:

```text
old live prod_mult
```

for the whole IDP population.

Instead, the release measured the change between an old-model representation and the new V1 representation and transported that **model delta** onto the true live production multiplier.

Conceptually:

```text
old model ratio  = old combined / old replacement baseline
new model ratio  = new combined / new replacement baseline

model delta = production-scale effect(new ratio) - production-scale effect(old ratio)

candidate live prod_mult
  = old live prod_mult + model delta
```

This lets the release incorporate the validated projection-model improvement without pretending that every historical component of the old live table was perfectly reproducible.

## 17.1 Frozen release facts

The final IDP V1 production bake recorded:

```text
404 candidate IDP keys
320 actual PROD_MULT changes
84 exact holds
0 non-IDP final-value changes
```

Source cohorts included:

```text
both providers
FantasyPros only
Sleeper only
no new data
```

## 17.2 No-comparable-old-projection holds

Players without a defensible comparable old projection were held rather than given an invented change.

## 17.3 Migration floor-rescue guard

A release-specific interaction was discovered during controlled deployment.

For certain zero-history speculative LBs:

```text
old raw PROD_MULT = exactly 0.15
```

The live production engine's no-history role rescue raised the effective value to the role estimate.

A tiny V1 raw increase above `0.15` would have accidentally disabled that rescue and caused a large negative final-value change.

The production bake therefore added a migration-specific guard:

```text
if the player had no real history
and old raw multiplier was exactly 0.15
and the new candidate moved above 0.15
but still did not clear the role estimate
then preserve the old raw 0.15
```

This protected the already-deployed live behavior.

It was a migration guard, **not** a global rewrite of `productionMultiplier()`.

---

# 18. Age Model

Current curves:

```text
QB  peakStart 26   peakEnd 33   floor age 35
RB  peakStart 23   peakEnd 25   floor age 30
WR  peakStart 24   peakEnd 28   floor age 33
TE  peakStart 25   peakEnd 29   floor age 34
DL  peakStart 24   peakEnd 29   floor age 34
LB  peakStart 24   peakEnd 29   floor age 32
DB  peakStart 23   peakEnd 27   floor age 32
K   peakStart 22   peakEnd 40   floor age 45
```

The age model has three conceptual phases:

```text
pre-peak
peak window
post-peak
```

---

# 19. Pre-Peak Age Multiplier

If a player is at or before their position's `peakEnd`, the model first builds a pre-peak floor.

## 19.1 Players with player-specific production

When real/player-specific production is available:

```text
production_ratio
  = clamp((production - 0.15) / (1.55 - 0.15), 0, 1)

pre_floor
  = 0.55 + production_ratio × (0.98 - 0.55)
```

This means a young player with strong real production receives a much softer youth penalty than a young player with weak production.

## 19.2 Players without player-specific production

Fallback pre-floor:

```text
Elite role       0.725
all other roles  0.55
```

## 19.3 Ramp toward peak

For ages leading into `peakStart`:

```text
t = max(0, (age - 21) / (peakStart - 21))

pre_peak_base
  = pre_floor + t × (1 - pre_floor)
```

Once the player is in the peak window:

```text
base age multiplier = 1.0
```

---

# 20. Elite Young RB Youth Premium

There is one special pre-peak age mechanism:

```text
position = RB
role = Elite
age <= 25
raw production >= 0.65
```

When all apply:

```text
years_of_upside
  = min(4, max(0, peakEnd - age))

youth_bonus
  = 0.384 × sqrt(years_of_upside)

flat_base
  = 0.725 if age <= peakStart
    else 1.0

age multiplier
  = min(1.5, flat_base + youth_bonus)
```

This is intentionally narrow.

It exists to represent the dynasty premium attached to genuinely elite young RB production rather than applying a blanket youth boost to every young running back.

It should not be generalized to other positions without explicit validation.

---

# 21. Post-Peak Age Decline

For post-peak players:

```text
t
  = clamp(
      (age - peakEnd) / (floorAge - peakEnd),
      0,
      1
    )
```

## 21.1 QB

QB has its own calibrated terminal floor:

```text
QB_POST_PEAK_FLOOR = 0.546
```

Formula:

```text
max(
  0.546,
  1 - t × (1 - 0.546)
)
```

## 21.2 LB

LB uses a front-loaded nonlinear decline:

```text
LB_POST_PEAK_DECAY_POWER = 0.5
```

Formula:

```text
max(
  0.62,
  1 - 0.38 × t^0.5
)
```

The square-root shape causes more decline shortly after the peak window and then eases toward the terminal floor.

The exponent is explicitly a future calibration candidate.

## 21.3 Other non-kicker positions

Current generic post-peak shape:

```text
max(
  0.62,
  1 - 0.38 × t
)
```

## 21.4 Kicker

Kicker currently returns a fixed:

```text
age multiplier = 0.5
```

rather than using the same player-age curve behavior as the main offensive/IDP positions.

---

# 22. Injury Status

The repository contains injury status multipliers and injury metadata.

However:

```text
injuryMultiplier() is intentionally NOT applied
to Fundamental Value
```

today.

That decision is explicit in `playerValue()`.

The current model does not silently turn a short-term injury tag into a long-term dynasty value haircut.

Reasons include:

- current Sleeper injury status is primarily a point-in-time snapshot;
- the repository does not yet have a sufficiently mature injury-duration/time-decay history;
- the injury multipliers themselves are not treated as fully validated dynasty economics.

If injury adjustments are ever activated, that should be a separately scoped model change with historical capture and regression validation.

---

# 23. Draft-Pick Valuation

Draft picks are valued independently from player age/production.

Current base values:

| Round | Early | Mid | Late |
|---|---:|---:|---:|
| 1 | 7500 | 5854 | 5244 |
| 2 | 3906 | 3624 | 3291 |
| 3 | 2692 | 2682 | 2319 |
| 4 | 1972 | 1831 | 1689 |
| 5 | 1414 | 1250 | 1118 |
| 6 | 1014 | 853 | 740 |

Current year discounts:

```text
2027  1.00
2028  0.85
2029  0.72
other 0.60 fallback
```

Formula:

```text
Pick Value
  = round(base[round][slot] × year_discount[year])
```

## 23.1 Evidence boundary

Rounds 5 and 6 are extrapolated because equivalent KTC market data is not independently available at the same quality as earlier rounds.

The 2029 year discount is also extrapolated by extending the observed future-pick decay.

These should remain labeled as lower-confidence portions of the pick model.

## 23.2 Picks vs. Team Utility

A draft pick carries Fundamental trade value immediately.

But a future pick is not a current rostered player and cannot occupy a starting lineup slot.

Therefore current Team Utility is fundamentally a **roster-state** measure, while pick capital remains represented directly in trade package value.

---

# 24. Player Fundamental Value vs. Trade Package Value

Individual player value and package value should not be confused.

For players:

```text
Fundamental Value = position × age × production × scale
```

For draft picks:

```text
Fundamental Pick Value = round(base × year discount)
```

A trade package can therefore contain additive Fundamental Value from:

```text
players
+
draft picks
```

This is the calculator's asset-equivalence lens.

It does not by itself claim that two equal-total packages will have equal impact on a specific roster.

That is why Team Utility exists separately.

---

# 25. Team Utility / Post-Trade Roster Simulation

Team Utility answers:

> What does this trade actually do to this specific roster after lineup optimization?

It is not a replacement for Fundamental Value.

It is a roster-context layer.

## 25.1 Actual league starting lineup

The optimizer uses the real league structure:

```text
QB          x1
RB          x2
WR          x2
TE          x1
FLEX        x1   (RB/WR/TE)
SUPER_FLEX  x1   (QB/RB/WR/TE)
K           x1
DL          x2
LB          x2
DB          x2
IDP_FLEX    x2   (DL/LB/DB)
```

Total:

```text
17 starters
```

## 25.2 Optimization

Pre-trade and post-trade rosters are optimized **independently from scratch**.

The optimizer receives:

```text
[{player_key, position, Fundamental Value}, ...]
```

It does not recalculate player value itself.

Its responsibility is lineup allocation.

Conceptually:

```text
pre roster
    ↓
best legal starting lineup + bench

post roster
    ↓
best legal starting lineup + bench
```

The difference between these two optimized states drives Team Utility.

## 25.3 Team Utility formula

Current:

```text
TU_BENCH_WEIGHT = 0.15
```

Therefore:

```text
Team Utility
  = 0.85 × starter-lineup value delta
  + 0.15 × bench value delta
```

where:

```text
starter-lineup value delta
  = post starters Fundamental Value
    - pre starters Fundamental Value

bench value delta
  = post bench Fundamental Value
    - pre bench Fundamental Value
```

The implementation also reports these pieces separately.

## 25.4 Why this matters

A one-for-one trade can have:

```text
small Fundamental Value delta
```

but:

```text
large Team Utility delta
```

if it upgrades a weak starting slot.

Likewise, a side can acquire more raw asset value while creating:

- starter redundancy;
- bench-only surplus;
- a hole at a scarce starting position.

Team Utility is designed to expose that difference.

## 25.5 Bench weight is not final truth

`0.15` is intentionally documented in code as an **unvalidated starting assumption**.

It is one of the clearest future calibration points once enough real trade/outcome evidence exists.

Do not quietly tune it because one trade "looks wrong."

Any change should be evaluated across many roster states and backtested.

---

# 26. Fundamental Value, Market Value, and Team Utility Separation

The production UI now exposes three separate lenses:

```text
Fundamental Value
Market Value
Team Utility
```

These answer different questions.

| Layer | Primary question |
|---|---|
| Fundamental | What is the model's structural dynasty value for this asset? |
| Market | How is this league currently ranking the player relative to others? |
| Team Utility | What does the player/package do to this specific roster? |

No layer is allowed to silently rewrite the others.

That separation is a core architectural rule.

---

# 27. League KTC Vote Aggregation

Canonical implementation:

```text
scripts/market/ktc_pipeline.py
```

Trade Desk collects league Keep/Trade/Cut-style comparisons.

Each three-way vote becomes:

```text
keep > trade
keep > cut
trade > cut
```

or three pairwise observations.

## 27.1 Why Bradley-Terry

Raw win rate is not sufficient because:

```text
beating a weak player
```

should not be treated as identical information to:

```text
beating a top player
```

The pipeline therefore fits a Bradley-Terry latent-strength model.

For strengths `s_i` and `s_j`:

```text
P(i beats j)
  = s_i / (s_i + s_j)
```

The rating is normalized to geometric mean `1.0`.

That absolute scale is arbitrary.

Relative order/strength is the meaningful output.

## 27.2 Sparse-data regularization

The league is small and pairwise comparisons can be sparse/disconnected.

The pipeline therefore uses symmetric virtual games against an anchor node.

Current regularization:

```text
2 virtual wins
+
2 virtual losses
against a fixed strength-1 anchor
```

per real player.

This stabilizes low-sample Bradley-Terry estimation without injecting directional preference.

## 27.3 Per-voter cap

The backend pipeline enforces:

```text
MAX_VOTES_PER_VOTER_PER_DAY = 20
```

The browser UX limit is not treated as the real anti-dominance boundary.

The aggregation pipeline independently limits counted votes.

## 27.4 Sample threshold

Position comparison signal is explicitly flagged as insufficient below:

```text
30 pairwise observations
```

rather than pretending every small sample is equally trustworthy.

---

# 28. Market Value V1

Canonical implementation:

```text
scripts/market/build_market_value.py
```

Generated artifact:

```text
scripts/artifacts/generated/market_values.json
```

Human report:

```text
scripts/artifacts/reports/market_value_report.md
```

Current method version:

```text
league-market-value-v1
```

Scale semantics:

```text
league_rank_quantile_mapped_to_trade_desk_points_v1
```

## 28.1 Why Market Value is not Bradley-Terry × constant

Bradley-Terry ratings are normalized latent strengths.

A rating such as:

```text
4.2
```

has no native point-scale equivalence to:

```text
7500 Trade Desk points
```

Multiplying Bradley-Terry by an arbitrary constant would fabricate cardinal meaning the model does not have.

## 28.2 Quantile calibration

Market Value V1 therefore does:

```text
1. Resolve league-only KTC ratings to canonical PLAYER_DB players.
2. Rank the resolved players by league market rating.
3. Take Fundamental Values for the exact same covered player universe.
4. Sort that Fundamental Value distribution.
5. Map market rank onto those point-scale slots.
6. Average slots for exact market-rating ties.
```

Conceptually:

```text
league voting determines ORDER
Fundamental covered-player distribution supplies SCALE
```

This preserves an additive familiar point scale while keeping market opinion separate.

## 28.3 Important invariant

For the market-covered player set, the calibration is designed so the market layer cannot simply inflate or deflate the entire pool.

It redistributes the existing covered-player point-scale distribution according to market ordering.

## 28.4 Guest voters

Market Value V1 uses:

```text
league-only votes
```

Guest votes are excluded.

## 28.5 Current coverage snapshot

At the verified 2026-09-01 data state:

```text
Fundamental model players: 565
Raw league market ratings: 467
Resolved Market Value players: 449
Coverage: 79.47%
```

Coverage is expected to change as the data refreshes.

Do not hard-code these counts into logic.

## 28.6 Evidence retained per player

Market Value records include evidence such as:

- same-position pairwise observation count;
- whether same-position evidence is considered sufficient;
- dominant-voter share;
- dominant-voter-majority flag.

These are interpretation guardrails.

They are not converted into a fake probability/confidence percentage.

## 28.7 Trade-level completeness

The UI does not pretend an incomplete Market Value package is complete.

If any player in the package lacks a valid current Market Value, the complete trade-level Market Value comparison is withheld rather than silently substituting Fundamental Value.

---

# 29. Value Uncertainty V1

Canonical implementation:

```text
scripts/validation/build_value_uncertainty.py
```

Generated artifact:

```text
scripts/artifacts/generated/value_uncertainty.json
```

Report:

```text
scripts/artifacts/reports/value_uncertainty_report.md
```

Method:

```text
sensitivity-envelope-v1
```

Semantics:

```text
sensitivity_envelope_v1_not_probability_interval
```

This wording is deliberate.

## 29.1 What the range means

The center of the range is always:

```text
the exact deployed Fundamental Value
```

The uncertainty engine does not alter the center value.

The range represents observed model-input sensitivity from three measurable sources.

It is **not** currently a calibrated:

```text
80% confidence interval
90% confidence interval
95% confidence interval
```

Historical coverage needs future out-of-sample evidence before those claims would be defensible.

---

# 30. Uncertainty Component 1: Projection-Provider Disagreement

When both Sleeper and FantasyPros exist:

```text
provider component
  = |Sleeper - FantasyPros|
    / (Sleeper + FantasyPros)
```

This equals:

```text
half provider spread / provider mean
```

for nonnegative projections.

If only one provider exists:

```text
use position median observed provider half-spread
```

If neither exists:

```text
use position 75th percentile observed provider half-spread
```

The imputation basis is stored per player.

---

# 31. Uncertainty Component 2: Historical Sampling Noise

Using active-game 2025 fantasy points:

```text
SEM
  = sample standard deviation / sqrt(active games)
```

Then:

```text
history component
  = SEM / position median active-game PPG
```

Players with fewer than two usable historical games receive a position-cohort fallback, currently the observed position 75th percentile.

This component is intended to distinguish:

```text
stable observed performance
from
noisy small-sample performance
```

---

# 32. Uncertainty Component 3: Availability History

Current relative availability component:

```text
missed_game_share × sqrt(position durability R²)
```

The use of `sqrt(R²)` is intentional.

If missed-game history has weak demonstrated persistence, V1 does not pretend a previous absence should carry forward at full strength.

No-history players receive a position-cohort fallback.

---

# 33. Combining Uncertainty

The three relative components are combined by root-sum-square:

```text
relative_half_width
  = sqrt(
      provider_component²
    + history_component²
    + availability_component²
    )
```

with a numerical cap:

```text
maximum relative half-width = 1.0
```

The player range is then centered on Fundamental Value.

Conceptually:

```text
low  = center × (1 - relative_half_width)
high = center × (1 + relative_half_width)
```

subject to implementation rounding/guards.

## 33.1 Uncertainty tiers

Current tiers:

```text
low
moderate
high
very high
```

are population quartiles of current relative half-widths.

They are descriptive relative labels.

They are **not** statistical coverage levels.

## 33.2 Current coverage snapshot

At the verified 2026-09-01 artifact:

```text
565 players total

projection providers:
  0 providers:  70
  1 provider:  321
  2 providers: 174

history:
  439 players with 2+ games
  126 insufficient-history players
```

These counts are rolling data, not model constants.

---

# 34. Historical Evidence Capture

Canonical implementation:

```text
scripts/validation/capture_model_history.py
```

Snapshots:

```text
research/model-history/snapshots/
```

The capture system is append-only.

Each snapshot stores enough evidence to reconstruct what the calculator knew at that time, including:

- deployed Fundamental Value inputs;
- every calculated player value;
- production multipliers;
- position weights;
- age curves;
- role multipliers;
- Sleeper projections;
- Sleeper raw category projections;
- FantasyPros normalized projections;
- identity crosswalk;
- KTC state;
- Value Uncertainty;
- Market Value;
- source-file hashes;
- model-state fingerprint;
- Git commit/run metadata.

This is crucial for real out-of-sample validation.

If only the *current* model were stored, future evaluation could accidentally compare future outcomes against a model that had already been updated using later information.

---

# 35. Realized Outcome Capture

Canonical implementation:

```text
scripts/validation/capture_realized_outcomes.py
```

Output:

```text
research/model-history/outcomes/2026.json
```

The outcome system reuses the league's canonical fantasy scoring logic.

The goal is to compare:

```text
what Trade Desk predicted at time T
```

against:

```text
what happened after time T
```

without rewriting the prediction after the fact.

---

# 36. Fundamental Backtesting Protocol

Canonical evaluator:

```text
scripts/validation/evaluate_model_history.py
```

Protocol:

```text
fundamental-v1
```

The protocol is intentionally frozen in code.

A future methodology change should create a new version rather than silently changing how historical results are graded.

## 36.1 Leakage protection

The scoring period containing a prediction snapshot is never graded.

The first eligible week is the **next** scoring period.

This means a Friday snapshot cannot benefit from Thursday-night results in the week containing the snapshot.

## 36.2 Completed-week requirement

A week is eligible only when:

```text
the week exists in realized outcomes
AND
the outcome file has been refreshed after the modeled completion boundary
```

A manual mid-week refresh cannot become a "completed" target by accident.

## 36.3 Fixed horizon completeness

A fixed horizon is scored only if **every required week is complete**.

The evaluator does not grade on whichever partial subset currently exists.

## 36.4 Snapshot deduplication

Repeated snapshots with:

```text
same predictions
+
same first eligible future week
```

are deduplicated.

The latest capture wins.

This prevents manual workflow testing from overweighting one model state.

---

# 37. Fundamental Backtest Targets

The evaluator separates three questions.

## 37.1 Fundamental Value vs. future total points

```text
value_vs_total_points
```

This includes availability.

No-game weeks remain zero.

It asks whether the full dynasty model aligns with future total production.

## 37.2 Fundamental Value vs. active-game PPG

```text
value_vs_active_ppg
```

Players with no active games in the horizon are excluded.

This asks how well the full value ranking relates to performance rate when active.

## 37.3 Production multiplier vs. active-game PPG

```text
prod_mult_vs_active_ppg
```

This isolates the production signal from position and age economics.

It is particularly important for diagnosing whether the production component itself is working even when full dynasty value has different objectives.

---

# 38. Fundamental Backtest Horizons

Current horizons:

```text
next 4 completed future weeks
next 8 completed future weeks
rest of regular season through Week 18
```

The model is therefore evaluated across short and longer forward horizons.

---

# 39. Fundamental Backtest Metrics

Current metrics include:

```text
Pearson correlation
Spearman rank correlation
pairwise ordering accuracy
min-max normalized MAE
min-max normalized RMSE
tie-aware top-12 hit rate
tie-aware top-24 hit rate
tie-aware top-50 hit rate
```

Subgroup analysis includes:

```text
position
offense / IDP / kicker unit
age band
role
real-production-history lineage
```

This makes the future evidence useful for diagnosis rather than reducing model quality to one global correlation.

---

# 40. Market Backtesting

Canonical implementation:

```text
scripts/validation/evaluate_market_history.py
```

Protocol:

```text
market-v1
```

This evaluator asks a different question from the Fundamental evaluator.

Fundamental evaluator:

```text
Does the model predict future football production?
```

Market evaluator:

```text
Does the model anticipate future movement in this league's internal market?
```

Internal KTC voting is a market target here, not fundamental truth.

## 40.1 Observation rule

Only:

```text
full refresh
```

snapshots are used as market observations because the KTC source is refreshed on full maintenance passes.

At most one market state per ISO week is retained.

If several full refreshes occur in the same week:

```text
latest capture wins
```

## 40.2 Horizons

```text
+1 ISO week
+2 ISO weeks
+4 ISO weeks
```

A missing exact target week remains pending.

The evaluator does not substitute a nearby snapshot.

## 40.3 Required naive baseline

The key baseline is:

```text
today's market predicts the future market
```

This is a strong persistence benchmark.

Trade Desk should receive incremental credit only if it beats that baseline.

## 40.4 Disagreement test

The evaluator also asks whether:

```text
model percentile - current market percentile
```

predicts:

```text
future market percentile - current market percentile
```

That is the most direct test of whether a current model/market disagreement contains useful forward information.

---

# 41. Why Backtesting Does Not Auto-Recalibrate the Model

The historical evaluators produce evidence.

They do not automatically rewrite:

```text
POSITION_WEIGHT
AGE_CURVE
ROLE_MULT
PROD_MULT_DATA
TU_BENCH_WEIGHT
IDP V1 release files
```

This is intentional.

Automatic optimization against early small samples would create a serious overfitting risk.

The intended process is:

```text
collect evidence
     ↓
wait for mature samples
     ↓
analyze repeated patterns
     ↓
propose a separately scoped parameter change
     ↓
validate out of sample where possible
     ↓
release deliberately
```

---

# 42. Scheduled Data Refresh

Canonical workflow:

```text
.github/workflows/scheduled-data-refresh.yml
```

The workflow uses one sequential write job and one final push to avoid independent-workflow race conditions.

## 42.1 Full refresh

Scheduled Tuesday.

The full chain includes:

```text
Sleeper league sync
trade history
team fields
player-position map
Sleeper projections
Sleeper IDP subset
FantasyPros projections
FantasyPros↔Sleeper identity crosswalk
dual-eligibility audit
KTC vote aggregation
Market Value
realized 2026 outcomes
deterministic derived state
Value Uncertainty
historical model/source snapshot
Fundamental evaluator
Market evaluator
single commit/push
```

## 42.2 Light refresh

Scheduled Friday.

The light refresh keeps the core source/projection chain current but omits selected weekly-heavy operations such as KTC/market aggregation and realized-outcome refresh.

It still captures another historical model snapshot.

## 42.3 Why sequential

All write-producing steps run in one job.

This is an explicit protection against:

```text
two workflows independently modifying main
+
both attempting to push
+
race / lost update / stale-base behavior
```

---

# 43. Repo Regression Checks

Canonical workflow:

```text
.github/workflows/repo-regression-checks.yml
```

At the technical snapshot documented here, the workflow identifies itself as:

```text
TRADE_DESK_REPO_REGRESSION_WORKFLOW=2026-09-01-v12-separate-market-value
```

It runs focused self-tests across:

- value snapshot parsing/parity;
- Value Uncertainty;
- Market Value;
- model history capture;
- realized outcomes;
- Fundamental historical evaluator;
- Market historical evaluator;
- Sleeper synchronization;
- dual eligibility;
- team-field refresh;
- player-position generation;
- free-agent valuation sync;
- deterministic derived state;
- projection filters/pipelines;
- draft-slot projection pipeline.

It then performs strict repository-level checks.

---

# 44. Regression Safety Gates

Important gates include:

## 44.1 Deterministic derived-state parity

```text
scripts/maintenance/refresh_repo_derived_state.py --check
```

Generated state must match canonical inputs.

## 44.2 Free-agent valuation parity

```text
scripts/sync/sync_free_agent_valuation.py --check
scripts/validation/validate_free_agent_valuation_parity.py
```

## 44.3 Repository regression suite

```text
scripts/validation/repo_regression_checks.py
```

## 44.4 Frozen IDP V1 deployment validation

```text
scripts/validation/validate_idp_v1_final_deployment.py
```

## 44.5 JavaScript syntax

Both:

```text
index.html
free-agent-board.html
```

have inline JavaScript syntax checked by Node.

## 44.6 Production immutability during normalization

The validation workflow asserts that deterministic normalization does **not** modify:

```text
index.html
```

This is a key boundary:

```text
rolling data refresh
must not become
silent Fundamental model recalibration
```

---

# 45. Free-Agent Board Architecture

Canonical documentation:

```text
docs/current/FREE_AGENT_BOARD.md
```

Canonical sync:

```text
scripts/sync/sync_free_agent_valuation.py
```

Canonical validator:

```text
scripts/validation/validate_free_agent_valuation_parity.py
```

The board copies canonical valuation regions from `index.html`.

That includes:

```text
POSITION_WEIGHT
AGE_CURVE
QB_POST_PEAK_FLOOR
LB_POST_PEAK_DECAY_POWER
ROLE_MULT
PROD_MULT_DATA
NO_REAL_PRODUCTION_HISTORY
productionMultiplier()
ageMultiplier()
playerValue()
PLAYER_DB
alias resolution
normalizeName()
```

## 45.1 Free-agent production precedence

Current free-agent production-source precedence:

```text
1. canonical PROD_MULT_DATA if available
2. FA_PROD_MULT_DATA if available
3. curated PLAYER_DB role estimate if applicable
4. speculative fallback estimate
```

The board's separate:

```text
FA_PROD_MULT_DATA
```

is intentionally preserved.

## 45.2 Important limitation

Core valuation parity is closed.

But:

```text
FA_PROD_MULT_DATA lineage
```

is not automatically equivalent to the frozen rostered IDP V1 lineage.

That remains an independent modeling/data-lineage backlog item.

---

# 46. Frozen IDP V1 Release

Canonical location:

```text
model/releases/idp-v1/
```

Important artifacts include:

```text
production_history_components.json
prod_mult_pre_v1_baseline.json
idp_v1_model_delta_transport_candidate.json
idp_v1_prod_mult_patch.json
idp_v1_release_manifest.json
idp_v1_final_deployment_validation.json
idp_v1_final_deployment_validation.md
README.md
```

The release manifest protects immutable artifacts with SHA256 hashes.

## 46.1 Release rule

A future model revision should create:

```text
model/releases/<new-release-id>/
```

It should **not** overwrite IDP V1.

This keeps:

```text
what production was
```

auditable independently from:

```text
what production is today
```

---

# 47. Model State vs. Rolling Data State

This repo has two fundamentally different classes of state.

## 47.1 Deliberate model state

Examples:

```text
POSITION_WEIGHT
AGE_CURVE
ROLE_MULT
PROD_MULT_DATA
QB_POST_PEAK_FLOOR
LB_POST_PEAK_DECAY_POWER
Fundamental formula
TU_BENCH_WEIGHT
IDP release methodology
```

These require deliberate analysis, validation, and release.

## 47.2 Rolling data / evidence state

Examples:

```text
Sleeper rosters
trade history
player team fields
Sleeper projections
FantasyPros projections
identity crosswalk
KTC votes/ratings
Market Values
Value Uncertainty
free-agent data
realized outcomes
historical snapshots
backtest reports
```

These are expected to change through scheduled refreshes.

The distinction is critical.

A healthy data refresh may change hundreds of generated values without meaning the Fundamental formula was recalibrated.

---

# 48. Major Modeling Invariants

The following should be treated as architectural invariants unless a deliberate project explicitly changes them.

## Invariant A — Fundamental Value remains canonical

```text
index.html playerValue()
```

is the deployed center-value source.

## Invariant B — Market never silently edits Fundamental

Market Value is an observational league-opinion layer.

## Invariant C — Team Utility never silently edits Fundamental

Team Utility consumes Fundamental player values and roster state.

It does not replace `playerValue()`.

## Invariant D — uncertainty never edits the center

Value Uncertainty creates a range around the deployed center.

## Invariant E — frozen releases stay frozen

`model/releases/idp-v1/` is immutable release history.

## Invariant F — model evaluation does not auto-fit production

Backtest evidence informs future decisions but does not rewrite live parameters automatically.

---

# 49. Current Known Limitations and Calibration Backlog

These limitations are intentionally explicit.

They should not be "fixed" incidentally during unrelated work.

## 49.1 Legacy `PROD_MULT_DATA` lineage

**Status:** open technical-debt / reproducibility workstream.

The existing legacy reconstruction does not exactly reproduce the old baked table.

Implication:

- deployed table remains source of truth;
- legacy generator remains diagnostic;
- future production-lineage work must separate changed source snapshots from actual historical formula/manual transformation.

## 49.2 Historical IDP position lineage

**Status:** open.

The IDP V1 release isolated a cohort where legacy production position and current valuation position differ.

The frozen V1 release intentionally did not mix that migration into the projection-methodology release.

## 49.3 Durability weighting methodology

**Status:** open.

Current history math interprets position durability R² as own-history weighting.

This was preserved for release isolation, not declared final optimal methodology.

## 49.4 Free-agent off-roster production lineage

**Status:** open.

Free-agent engine parity is validated, but `FA_PROD_MULT_DATA` itself has separate lineage questions.

## 49.5 Team Utility bench weight

**Status:** open calibration target.

```text
TU_BENCH_WEIGHT = 0.15
```

is explicitly a starting assumption.

## 49.6 Market voter concentration / sparse depth

**Status:** naturally improving with future votes.

Market Value preserves:

- dominant-voter share;
- same-position pairwise sample sizes;
- data-sufficiency flags.

Small-sample league opinion should not be overinterpreted as broad consensus.

## 49.7 Incomplete Market Value coverage

At the verified snapshot:

```text
449 / 565 = 79.47%
```

The UI correctly refuses to fabricate complete market package values when required player market observations are missing.

## 49.8 Uncertainty is not a probability interval

The current range is a sensitivity envelope.

Empirical coverage calibration requires future outcome evidence.

## 49.9 Backtest maturity

Infrastructure is complete.

Evidence is not yet mature simply because the future 2026 weeks have not all happened.

This is a time constraint, not an engineering defect.

## 49.10 FantasyPros category gaps

The FantasyPros API does not currently supply every exact league category, especially QB hits.

These gaps remain explicit in normalized artifacts.

## 49.11 Draft-pick extrapolation

Rounds 5-6 and the 2029 time discount contain extrapolated assumptions.

They should be revisited when stronger market evidence exists.

## 49.12 Injury-value methodology

Injury multipliers exist but are intentionally disabled in Fundamental Value.

A future injury model should likely include historical injury-duration evidence and time decay rather than relying on point-in-time status alone.

## 49.13 LB post-peak exponent

```text
LB_POST_PEAK_DECAY_POWER = 0.5
```

has the intended qualitative front-loaded decline shape but remains a future real-market/outcome calibration candidate.

---

# 50. Recommended Future Calibration Order

Once real 2026 backtest evidence begins to mature, avoid changing many parameters simultaneously.

A defensible sequence is:

```text
1. Diagnose backtest failures by component/subgroup.
2. Separate production-rate failures from position-economics failures.
3. Resolve remaining lineage debt before using a pipeline as a training target.
4. Calibrate one parameter family at a time.
5. Preserve an immutable pre-change snapshot.
6. Run full regression and historical comparison.
7. Create a versioned release when the change is material.
```

Specific candidates include:

```text
legacy PROD_MULT lineage
free-agent production lineage
IDP historical position lineage
durability weighting
TU_BENCH_WEIGHT
LB post-peak decline
pick extrapolation
uncertainty empirical coverage
```

---

# 51. How to Interpret a Trade in the Current UI

The intended analysis sequence is:

## Step 1 — Fundamental Value

Ask:

```text
Which side receives more structural dynasty asset value?
```

This is the model's center-value comparison.

## Step 2 — Uncertainty

Ask:

```text
How sensitive are these player values to observable uncertainty in projections,
history sample size, and availability history?
```

A close trade with very wide ranges should be interpreted differently from a close trade with narrow ranges.

## Step 3 — Market Value

Ask:

```text
How does the league currently rank the players?
```

This helps expose:

```text
buy-low opportunities
sell-high opportunities
league disagreement with the model
```

without redefining Fundamental Value.

## Step 4 — Team Utility

Ask:

```text
What happens to the actual starting lineup and bench after the trade?
```

This identifies roster-specific consequences.

The four views are complementary.

They are intentionally not collapsed into one "magic" number.

---

# 52. Example Conceptual Trade Diagnosis

Suppose a trade is:

```text
Side A Fundamental: 10,000
Side B Fundamental: 10,200
```

On Fundamental Value alone:

```text
Side B +200
```

But imagine:

```text
Side A acquires a high-end QB that replaces a weak Superflex starter.
Side B acquires two good WRs that mostly sit behind existing WR depth.
```

Then Team Utility could favor Side A despite the small Fundamental deficit.

Now imagine league KTC voting strongly favors the two WRs.

Market Value could favor Side B.

Finally, if the QB's projections disagree materially between providers while the WRs have stable histories, the uncertainty lens may show more risk on Side A.

The correct conclusion is not:

```text
one layer must be wrong
```

The layers answer different questions.

---

# 53. What Should Never Happen Silently

The following are model-integrity failures if they occur without an explicitly scoped release:

```text
Scheduled refresh changes POSITION_WEIGHT.
Scheduled refresh changes AGE_CURVE.
Market voting changes Fundamental Value.
Team Utility changes PLAYER_DB values.
Uncertainty changes the center point estimate.
Free-agent sync changes the canonical valuation formula.
IDP V1 frozen files are overwritten.
Backtest evaluator rewrites live production parameters.
A missing projection provider is silently treated as a real zero signal.
A name collision is silently accepted as identity truth.
A manual CI normalization pushes a changed index.html.
```

The repository's current validation architecture exists largely to prevent these classes of failure.

---

# 54. Operational Validation Commands

## Fundamental snapshot/parity

```bash
python3 scripts/validation/snapshot_values.py --selftest
```

## Value Uncertainty

```bash
python3 scripts/validation/build_value_uncertainty.py --selftest
python3 scripts/validation/build_value_uncertainty.py --write
```

## Market Value

```bash
python3 scripts/market/build_market_value.py --selftest
python3 scripts/market/build_market_value.py --write
```

## History capture/evaluation

```bash
python3 scripts/validation/capture_model_history.py --selftest
python3 scripts/validation/capture_realized_outcomes.py --selftest
python3 scripts/validation/evaluate_model_history.py --selftest
python3 scripts/validation/evaluate_market_history.py --selftest
```

## Free-agent parity

```bash
python3 scripts/sync/sync_free_agent_valuation.py --check
python3 scripts/validation/validate_free_agent_valuation_parity.py
```

## Derived state

```bash
python3 scripts/maintenance/refresh_repo_derived_state.py --check
```

## Full repository regression

```bash
python3 scripts/validation/repo_regression_checks.py
```

## Frozen IDP release

```bash
python3 scripts/validation/validate_idp_v1_final_deployment.py
```

The GitHub Actions `Repo Regression Checks` workflow is the final safety gate after production changes.

---

# 55. Technical Snapshot Summary

As of the verified production commit:

```text
Fundamental model players: 565

Fundamental Value:
  deployed and canonical in index.html

Position weights:
  QB 1.30
  RB 0.89
  WR 1.00
  TE 0.82
  DL 0.93
  LB 1.12
  DB 0.87
  K  0.35

Role multipliers:
  Elite       1.40
  Every-Down  1.15
  Starter     1.00
  Rotational  0.65
  Understudy  0.57
  Depth       0.35
  Speculative 0.22

QB post-peak floor:
  0.546

LB post-peak decay power:
  0.5

IDP V1:
  deployed
  frozen
  validated

Market Value:
  449 resolved players
  79.47% current model coverage
  league-only votes
  separate from Fundamental

Value Uncertainty:
  all 565 model players
  sensitivity envelope
  not a calibrated probability interval

Team Utility:
  real pre/post roster optimization
  85% starter delta
  15% bench delta

Historical backtesting:
  infrastructure complete
  append-only evidence capture active
  future 2026 weeks required for mature calibration

Repo Regression Checks #80:
  PASS
```

---

# 56. Final Architecture Principle

Trade Desk is no longer best described as one trade-value formula.

It is a layered decision system:

```text
Fundamental Value
    = structural dynasty asset value

Value Uncertainty
    = sensitivity around the fundamental center

Market Value
    = current internal league opinion on a comparable point scale

Team Utility
    = roster-specific consequence after optimal lineup reconstruction

Historical Backtesting
    = evidence system used to decide whether any of the above should
      eventually be recalibrated
```

The model's strongest engineering property is the separation between those layers.

That separation should be preserved.

A future improvement should clearly state which layer it changes, why that layer needs to change, what evidence supports the change, and which other layers are guaranteed to remain untouched.

---

# 57. Primary Implementation Reference Map

| Area | Canonical reference |
|---|---|
| Fundamental UI/model | `index.html` |
| Python Fundamental parity | `scripts/validation/snapshot_values.py` |
| Historical true PPG | `scripts/model/ppg_pipeline.py` |
| Historical shrinkage/durability component | `scripts/model/production_history_component.py` |
| Sleeper projections | `scripts/projections/sleeper_projections_pipeline.py` |
| FantasyPros projections | `scripts/projections/fantasypros_api_pipeline.py` |
| FantasyPros↔Sleeper identity | `scripts/projections/resolve_fantasypros_sleeper_identity.py` |
| IDP projection model | `scripts/model/idp_v1_projection.py` |
| Frozen IDP V1 release | `model/releases/idp-v1/` |
| League KTC aggregation | `scripts/market/ktc_pipeline.py` |
| Separate Market Value | `scripts/market/build_market_value.py` |
| Value Uncertainty | `scripts/validation/build_value_uncertainty.py` |
| Historical model capture | `scripts/validation/capture_model_history.py` |
| Realized outcomes | `scripts/validation/capture_realized_outcomes.py` |
| Fundamental evaluator | `scripts/validation/evaluate_model_history.py` |
| Market evaluator | `scripts/validation/evaluate_market_history.py` |
| Free-agent canonical sync | `scripts/sync/sync_free_agent_valuation.py` |
| Free-agent parity validator | `scripts/validation/validate_free_agent_valuation_parity.py` |
| Scheduled refresh | `.github/workflows/scheduled-data-refresh.yml` |
| Final regression safety gate | `.github/workflows/repo-regression-checks.yml` |

---

**End of technical model breakdown.**
