# Project Structure

This repository uses a conservative Python `src/` layout. The goal is to make
imports, packaging, tests, and future refactors predictable without creating
empty folders for features that do not exist yet.

## Current Structure

```text
.
  AGENTS.md
  pyproject.toml
  uv.lock
  docs/
  src/
    g6explanation/
      __init__.py
      py.typed
      context_engine/
        __init__.py
        candidate_policy.py
        contracts.py
        evidence_verification.py
        exceptions.py
        explanation_agenda.py
        maia_likelihood.py
        move_beauty.py
        move_context_builder.py
        move_quality.py
        position_reconstruction.py
        provider_protocols.py
        stockfish_analysis.py
  tests/
    g6explanation/
      context_engine/
        helpers.py
        test_evidence_verification.py
        test_golden_packet_fixtures.py
        test_maia_likelihood.py
        test_move_beauty.py
        test_move_context_builder.py
        test_position_reconstruction.py
        test_real_game_significance_examples.py
        test_schema_contracts.py
        test_stockfish_analysis.py
```

## Strategy

- Use `src/` layout so tests import the installed package shape, not accidental
  local modules.
- Keep the root package small. `g6explanation.__init__` should expose stable
  public API objects only.
- Put code under the bounded context it serves. The current bounded context is
  `g6explanation.context_engine`.
- Mirror tests by package path when that improves navigation. For example,
  `src/g6explanation/context_engine/` maps to
  `tests/g6explanation/context_engine/`.
- Keep docs at the repo root under `docs/` because they guide the whole product,
  not one package.
- Add new top-level folders only when real implementation requires them.

## Module Naming Rules

- Use domain names, not generic names.
- Avoid `utils.py`, `common.py`, `helpers.py`, `models.py`, `providers.py`, and
  `heuristics.py` in production code.
- Name modules after the responsibility that would make them change, such as
  `move_quality.py`, `candidate_policy.py`, `position_reconstruction.py`, or
  `stockfish_analysis.py`.
- Prefer public class names that describe responsibility, such as
  `MoveContextBuilder`, `EngineAnalysisProvider`,
  `HumanMoveLikelihoodProvider`, and `ContextContract`.
- Keep schema contracts in `contracts.py`; treat those names and JSON shapes as
  product contracts.
- Keep test-only helpers inside the relevant test package.
- Keep external integrations behind explicitly named provider protocols and
  concrete adapter modules.

## When To Add A New Package

Add a new package only when there is a real boundary with a different reason to
change. Good future examples might include an API transport layer or an LLM
generation layer. Do not create those packages before implementation needs them.
