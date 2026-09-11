# Package Adjustment NextGen V2 — Generated Challenge Catalog Design

**Status: FROZEN / UNRELEASED — RESEARCH ONLY. Voting is not activated. Production V1.6 is unchanged.**

## Frozen inputs

- Generator commit: `36d5316db035a61541b40324f8f7b228014fd04a`
- Generator SHA-256: `12528caf59207fdc99490f61d0899754add47f2f5b90a438e9672327a998e66b`
- Research spec SHA-256: `6338697485a02ac1e93aeff55834e292fd0e8fba05302bfa21d88784aa8e1d8d`
- Player FV SHA-256: `a12a0fed97a95f8bbd3b33d56d1f8151de228a344af98982e6fb01b9a610012d`
- League rosters SHA-256: `0d49ee988dc07afa7b0e34daa7d5e7a62cc9e263dca637dc760e27994bc9c716`
- Controlled-live formula SHA-256: `9a1a52f3393a701fe8463fcf2179d1342debb925da1109ce73276b8b2b8cbbc7`

## Normalization

- Eligible rostered players: `493`
- V_REF (nearest-rank 95th percentile): `5401.0`

## Catalog

- Challenges: `129`
- Feasible real-player 80/20 pairs used for scale derivation: `11498`
- Unique assets used: `238`
- Maximum appearances by one asset: `11`
- Exact side reuses within the same cell/scale: `0`
- Exact side reuses across scales within one cell: `0`
- Cross-cell exact side signatures within one family: `31`
- Core cross-cell reused signatures with non-50/50 shares: `0`
- Maximum selected-goal drift from its scale anchor: `0.0028465999`
- Pick cells active: `False`
- Deferred fragmentation comparisons: `80_20_vs_80_05x4`
- Core high-value scale is reserved from fitting.
- All 3v3 structural-topology challenges are reserved from fitting.
- FV values must remain hidden from voters when activated.
- Left/right display must be randomized by the future browser activation layer.

### Challenges by family

- core_concentration_2v2: `90`
- fragmentation_filler: `15`
- structural_topology_3v3: `24`

### Challenges by split

- structural_scale_holdout: `30`
- structural_topology_holdout: `24`
- train: `75`

## Freeze

- Frozen challenge count: `129`
- Canonical challenge-payload SHA-256: `fa52f72f6f4bdeaf1a5a935bde0fb5d0ec0fc85cc2b0d58236c2101d47d4f5ab`
- Freeze-lock generator commit: `36d5316db035a61541b40324f8f7b228014fd04a`
- Freeze manifest: `research/package-adjustment-nextgen-v2/catalog_freeze_manifest.json`
- Voting activated: `False`
- Production change authorized: `False`
- The next preregistered prerequisite is the power / precision and evidence-maturity plan.

## Isolation

This generator creates only NextGen research catalog/design outputs. It does not modify production FV, Market Value, Team Utility, draft-pick values, the controlled-live Package Adjustment formula, Trade Verdict consumers, historical V3/V4/V5 catalogs, or workflow files.

A separate reviewed step is required before browser voting activation.
