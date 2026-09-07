# KTC Voter-Balance Prospective Evaluation

Method: `ktc-voter-balance-prospective-v1`  
Status: **`EVIDENCE_AVAILABLE_RESEARCH_ONLY`**  
Directional result: **`raw_better_on_equal_voter_future_consensus`**

## Guardrail

**Research-only. Market Value V1 remains on `league_only.player_ratings`.**

This evaluation freezes a KTC rating snapshot, then scores raw and voter-balanced Bradley-Terry probabilities only against league ballots submitted afterward. Evaluation windows are disjoint, so the same future ballot is not repeatedly counted across successive snapshots.

## Evidence volume

- Distinct rating snapshots: **5**
- Eligible future ballots: **44**
- Distinct future voters: **4**
- Evidence threshold: **30 ballots** and **4 voters**

## Aggregate metrics

| Target | Model | Log loss ↓ | Brier ↓ | Pairwise accuracy ↑ |
|---|---|---:|---:|---:|
| Raw future stream | Raw KTC | 0.62685 | 0.217871 | 66.67% |
| Raw future stream | Balanced KTC | 0.683499 | 0.244664 | 58.33% |
| Equal-voter future consensus | Raw KTC | 0.641602 | 0.224985 | 66.51% |
| Equal-voter future consensus | Balanced KTC | 0.693504 | 0.249612 | 53.33% |

Negative `balanced_minus_raw` log-loss/Brier deltas favor the balanced model.

## Interval detail

| Snapshot | Window end | Future ballots | Voters | Consensus Δ log loss | Consensus Δ Brier |
|---|---|---:|---:|---:|---:|
| 2026-09-03T17:28:07.064521Z | 2026-09-04T17:41:00.347245Z | 0 | 0 | — | — |
| 2026-09-04T17:41:00.347245Z | 2026-09-05T16:52:38.726632Z | 0 | 0 | — | — |
| 2026-09-05T16:52:38.726632Z | 2026-09-06T17:10:35.454751Z | 1 | 1 | 0.021361 | 0.01072 |
| 2026-09-06T17:10:35.454751Z | 2026-09-07T18:47:17.224162Z | 43 | 4 | 0.059537 | 0.028103 |
| 2026-09-07T18:47:17.224162Z | current | 0 | 0 | — | — |

## Decision rule

The primary research target is **equal-voter future consensus**, because it prevents one future high-volume voter from defining the evaluation target. The raw future stream is retained as a secondary reality check.

A single favorable interval is not enough to promote voter-balanced ratings. Promotion would require a sustained advantage across multiple intervals, enough future ballots, and multiple distinct voters.
