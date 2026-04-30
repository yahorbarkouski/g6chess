# Agent Capabilities And Checks

## Required Capabilities

Agents working here should be able to:

- parse and replay chess games deterministically
- call Stockfish through UCI at depth 16 or deeper and parse results
- call optional Maia or replacement human-likeness providers
- validate JSON schemas
- run deterministic chess verification
- run unit, integration, golden, and regression tests
- inspect data manifests and source rights
- update the concise ADR set when durable decisions change

## Pre-Implementation Checklist

- What product slice is changing?
- Which ADRs govern it?
- Which schemas are involved?
- Which verifier checks protect it?
- Which test fixture proves it?
- Which failure mode should become a regression test?

## Completion Checklist

- Relevant tests passed.
- Schema changes were validated.
- Chess correctness checks passed.
- New behavior has tests or eval fixtures.
- Docs or ADRs changed when contracts changed.
- Skipped checks and residual risks are named.

## Review Checklist

Prioritize:

- wrong perspective
- illegal moves
- unsupported PV references
- mate/centipawn confusion
- ambiguous or unlicensed data use
- LLM-invented chess facts
- tests that mock away the main chess risk
- broad scaffolding outside the current slice

## Future Check Surface

Add single documented commands only after the relevant stack exists for schema
validation, verifier fixtures, golden incidents, eval smoke tests, and data
manifest validation.
