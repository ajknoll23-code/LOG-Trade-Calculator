# KTC Voter-Balance Prospective Evaluation

Method: `ktc-voter-balance-prospective-v1`  
Status: **`EVIDENCE_AVAILABLE_RESEARCH_ONLY`**  
Directional result: **`raw_better_on_equal_voter_future_consensus`**

## Guardrail

**Research-only. Market Value V1 remains on `league_only.player_ratings`.**

This evaluation freezes a KTC rating snapshot, then scores raw and voter-balanced Bradley-Terry probabilities only against league ballots submitted afterward. Evaluation windows are disjoint, so the same future ballot is not repeatedly counted across successive snapshots.

## Evidence volume

- Distinct rating snapshots: **7**
- Eligible future ballots: **57**
- Distinct future voters: **5**
- Evidence threshold: **30 ballots** and **4 voters**

## Aggregate metrics

| Target | Model | Log loss ↓ | Brier ↓ | Pairwise accuracy ↑ |
|---|---|---:|---:|---:|
| Raw future stream | Raw KTC | 0.609304 | 0.210968 | 67.25% |
| Raw future stream | Balanced KTC | 0.666067 | 0.236452 | 60.23% |
| Equal-voter future consensus | Raw KTC | 0.626322 | 0.218755 | 66.96% |
| Equal-voter future consensus | Balanced KTC | 0.679097 | 0.242786 | 55.55% |

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
| 2026-09-09T17:53:09.546717Z | current | 0 | 0 | — | — |

## Decision rule

The primary research target is **equal-voter future consensus**, because it prevents one future high-volume voter from defining the evaluation target. The raw future stream is retained as a secondary reality check.

A single favorable interval is not enough to promote voter-balanced ratings. Promotion would require a sustained advantage across multiple intervals, enough future ballots, and multiple distinct voters.
