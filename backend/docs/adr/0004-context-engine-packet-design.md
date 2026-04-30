# ADR 0004: Context Engine Packet Design

Date: 2026-04-30
Status: Superseded
Superseded by: ADR 0005

## Context

The focused product returns one explanation string for one move. The explanation
quality depends on the context given to the LLM. Raw FEN, raw Stockfish lines,
or uncurated tags are not enough and invite hallucination, wrong-side
attribution, overlong engine dumps, and unsupported tactic claims.

The system needs a durable direction for how context is built before
implementation begins.

## Decision

The context engine will produce two internal artifacts:

1. **Evidence Packet**: the complete machine-readable truth record for the move.
2. **Coach Context**: a smaller, curated packet sent to the LLM to produce one
   explanation string.

The evidence packet is used for verification, tests, debugging, and evaluation.
The coach context is used for generation.

The context engine must reconstruct the position, verify the move, collect
Stockfish and optional Maia/concept evidence, normalize scores from the player's
perspective, classify move quality, choose the explanation agenda, and provide
allowed and forbidden claims.

## Consequences

This keeps chess truth outside the LLM while giving the model enough context to
sound like a strong coach. It also lets us iterate on prompts and model choices
without rerunning all engine analysis, and it lets the verifier check generated
strings against the fuller evidence packet.

The context engine should be versioned. Early versions can use Stockfish-only
context. Later versions can add WDL, concept confidence, Maia human-likeness, and
evaluation-calibrated context selection.

## Alternatives Considered

### Send raw evidence directly to the LLM

Rejected. Raw engine output is too easy to misread and tends to produce engine
dumps instead of coach-quality explanations.

### Build only one packet

Rejected. A single packet either overloads the LLM or starves the verifier. The
LLM and verifier need different levels of detail.

### Let the LLM infer the teaching point

Rejected. The context engine should choose the safest explanation agenda from
verified evidence. The LLM should phrase it, not discover it from scratch.

## Validation

This decision is working if:

- generated explanations mention only supported claims
- wrong-side attribution is caught before response
- move quality labels match normalized engine evidence
- explanations become shorter and clearer as coach context improves
- optional Maia/concept fields improve output without becoming required truth
- context versions can be compared on frozen examples
