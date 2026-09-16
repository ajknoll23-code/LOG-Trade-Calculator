# Draft Pick FV V4 — Clean Source Recovery Preregistration

**Status:** `FROZEN_PRE_SEARCH_PRE_OUTCOME`

V4 asks one question first: can we build a sufficiently large cohort of **genuine** historical
12-team SF/2QB rookie drafts after screening source contamination correctly?

## What V4 inherits without modification

The source-sufficiency bars are **not lowered** from V3:

- R1–R4 clean nonmock total: **≥ 180**
- R5 clean non-IDP total: **≥ 60**
- R6 clean non-IDP total: **≥ 36**
- R6 clean non-IDP minimum in every year: **≥ 3**
- R6 effective years: **≥ 4.5**
- R6 maximum single-year share: **≤ 30%**
- IDP R6 sensitivity total: **≥ 20**
- IDP R6 sensitivity represented years: **≥ 5**

## Contamination rule

A league is excluded from V4 primary/source-sufficiency scopes if its audited draft contains
positive evidence of an earlier NFL class, a later NFL class, or an explicit Devy custom player.
MFL custom-player IDs are treated as **league-scoped**, never globally unique.

Unknown identities are reported; they are not manually relabeled after the recovery counts are known.

## Frozen expanded search

The search remains MFL 2018–2023. The bounded search union uses the preregistered term list,
deterministic SHA-256 ordering, up to **250 results per term**, and up to **1,200 unique candidates
per year**. Search expansion after seeing recovery counts is forbidden.

## Firewall

This stage reads source metadata and draft identities only. It does **not** read historical player
outcomes, fit candidate FV curves, score validation, use KTC/package votes as targets, or authorize
a production change.

Passing source recovery does not itself authorize outcomes. A new V4 catalog/preregistration must
be frozen first.
