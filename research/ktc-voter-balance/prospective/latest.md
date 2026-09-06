# KTC Voter-Balance Prospective Evaluation

Method: `ktc-voter-balance-prospective-v1`  
Status: **`READY_WAITING_FOR_MORE_FUTURE_VOTES`**  
Directional result: **`insufficient_future_evidence`**

## Guardrail

**Research-only. Market Value V1 remains on `league_only.player_ratings`.**

This evaluation freezes a KTC rating snapshot, then scores raw and voter-balanced Bradley-Terry probabilities only against league ballots submitted afterward. Evaluation windows are disjoint, so the same future ballot is not repeatedly counted across successive snapshots.

## Evidence volume

- Distinct rating snapshots: **4**
- Eligible future ballots: **1**
- Distinct future voters: **1**
- Evidence threshold: **30 ballots** and **4 voters**

## Aggregate metrics

| Target | Model | Log loss ↓ | Brier ↓ | Pairwise accuracy ↑ |
|---|---|---:|---:|---:|
| Raw future stream | Raw KTC | 0.696243 | 0.251442 | 66.67% |
| Raw future stream | Balanced KTC | 0.717604 | 0.262162 | 33.33% |
| Equal-voter future consensus | Raw KTC | 0.696243 | 0.251442 | 66.67% |
| Equal-voter future consensus | Balanced KTC | 0.717604 | 0.262162 | 33.33% |

Negative `balanced_minus_raw` log-loss/Brier deltas favor the balanced model.

## Interval detail

| Snapshot | Window end | Future ballots | Voters | Consensus Δ log loss | Consensus Δ Brier |
|---|---|---:|---:|---:|---:|
| 2026-09-03T17:28:07.064521Z | 2026-09-04T17:41:00.347245Z | 0 | 0 | — | — |
| 2026-09-04T17:41:00.347245Z | 2026-09-05T16:52:38.726632Z | 0 | 0 | — | — |
| 2026-09-05T16:52:38.726632Z | 2026-09-06T17:10:35.454751Z | 1 | 1 | 0.021361 | 0.01072 |
| 2026-09-06T17:10:35.454751Z | current | 0 | 0 | — | — |

## Decision rule

The primary research target is **equal-voter future consensus**, because it prevents one future high-volume voter from defining the evaluation target. The raw future stream is retained as a secondary reality check.

A single favorable interval is not enough to promote voter-balanced ratings. Promotion would require a sustained advantage across multiple intervals, enough future ballots, and multiple distinct voters.
