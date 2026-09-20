# KTC Voter-Balance Prospective Evaluation

Method: `ktc-voter-balance-prospective-v1`  
Status: **`EVIDENCE_AVAILABLE_RESEARCH_ONLY`**  
Directional result: **`raw_better_on_equal_voter_future_consensus`**

## Guardrail

**Research-only. Market Value V1 remains on `league_only.player_ratings`.**

This evaluation freezes a KTC rating snapshot, then scores raw and voter-balanced Bradley-Terry probabilities only against league ballots submitted afterward. Evaluation windows are disjoint, so the same future ballot is not repeatedly counted across successive snapshots.

## Evidence volume

- Distinct rating snapshots: **18**
- Eligible future ballots: **89**
- Distinct future voters: **5**
- Evidence threshold: **30 ballots** and **4 voters**

## Aggregate metrics

| Target | Model | Log loss ↓ | Brier ↓ | Pairwise accuracy ↑ |
|---|---|---:|---:|---:|
| Raw future stream | Raw KTC | 0.600033 | 0.206353 | 68.92% |
| Raw future stream | Balanced KTC | 0.652983 | 0.230281 | 63.29% |
| Equal-voter future consensus | Raw KTC | 0.614133 | 0.212939 | 68.31% |
| Equal-voter future consensus | Balanced KTC | 0.665111 | 0.23612 | 59.32% |

Negative `balanced_minus_raw` log-loss/Brier deltas favor the balanced model.

## Interval detail

| Snapshot | Window end | Future ballots | Voters | Consensus Δ log loss | Consensus Δ Brier |
|---|---|---:|---:|---:|---:|
| 2026-09-03T17:28:07.064521Z | 2026-09-04T17:41:00.347245Z | 0 | 0 | — | — |
| 2026-09-04T17:41:00.347245Z | 2026-09-05T16:52:38.726632Z | 0 | 0 | — | — |
| 2026-09-05T16:52:38.726632Z | 2026-09-06T17:10:35.454751Z | 1 | 1 | 0.021361 | 0.01072 |
| 2026-09-06T17:10:35.454751Z | 2026-09-07T18:47:17.224162Z | 43 | 4 | 0.059537 | 0.028103 |
| 2026-09-07T18:47:17.224162Z | 2026-09-08T17:58:00.613350Z | 0 | 0 | — | — |
| 2026-09-08T17:58:00.613350Z | 2026-09-09T17:53:09.546717Z | 13 | 1 | 0.057145 | 0.021053 |
| 2026-09-09T17:53:09.546717Z | 2026-09-10T17:45:19.490170Z | 0 | 0 | — | — |
| 2026-09-10T17:45:19.490170Z | 2026-09-11T17:48:07.728622Z | 0 | 0 | — | — |
| 2026-09-11T17:48:07.728622Z | 2026-09-12T17:18:12.421849Z | 0 | 0 | — | — |
| 2026-09-12T17:18:12.421849Z | 2026-09-13T17:29:02.705801Z | 0 | 0 | — | — |
| 2026-09-13T17:29:02.705801Z | 2026-09-14T19:30:18.363370Z | 0 | 0 | — | — |
| 2026-09-14T19:30:18.363370Z | 2026-09-15T18:30:44.556269Z | 18 | 1 | 0.050201 | 0.024852 |
| 2026-09-15T18:30:44.556269Z | 2026-09-16T18:15:57.488399Z | 0 | 0 | — | — |
| 2026-09-16T18:15:57.488399Z | 2026-09-17T18:22:26.338025Z | 0 | 0 | — | — |
| 2026-09-17T18:22:26.338025Z | 2026-09-18T17:44:31.705144Z | 14 | 1 | 0.040964 | 0.016406 |
| 2026-09-18T17:44:31.705144Z | 2026-09-19T17:20:33.873900Z | 0 | 0 | — | — |
| 2026-09-19T17:20:33.873900Z | 2026-09-20T17:33:15.233101Z | 0 | 0 | — | — |
| 2026-09-20T17:33:15.233101Z | current | 0 | 0 | — | — |

## Decision rule

The primary research target is **equal-voter future consensus**, because it prevents one future high-volume voter from defining the evaluation target. The raw future stream is retained as a secondary reality check.

A single favorable interval is not enough to promote voter-balanced ratings. Promotion would require a sustained advantage across multiple intervals, enough future ballots, and multiple distinct voters.
