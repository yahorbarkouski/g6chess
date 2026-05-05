# Book Lines Port Plan

Date: 2026-05-05

Repos reviewed:
- `/Users/yahorbarkouski/g6explanation-frontend`
- `/Users/yahorbarkouski/g6explanation`
- `/Users/yahorbarkouski/g6chess-frontend`
- `/Users/yahorbarkouski/g6chess-backend`

## Executive Summary

Yes, the book-lines experience from the older G6 stack can be rebuilt in `g6explanation`, but it is not a frontend-only port. The old UX worked because the backend detected opening-book moves, attached book continuations and opening identity to analysis markers, and the frontend switched the selected-move sidebar from engine lines to a compact opening-book line view.

The current `g6explanation-frontend` already has partial visual readiness: `book` is a known analysis class in the local analysis types, the move list has a book icon, and the class label/style exists. What is missing is the typed book-line payload, the mapping from backend snapshot data into markers/timeline points, and the actual `BookLinesView` branch in the workspace.

The current `g6explanation` backend has no opening-book provider or book metadata contract. Its Pydantic contracts are stricter than the old backend's dict-shaped payloads, so the port should add explicit contracts instead of copying untyped `label_metadata` behavior wholesale.

## What The Old Experience Did

The old backend performed a sequential opening-book pass before or alongside engine analysis:

- Look up each played move in a Polyglot opening book.
- Track when each side left book independently.
- Mark book moves and novelties.
- Resolve ECO/opening names from an opening-name table.
- For each book move, produce up to several main continuation lines from the position after the played move.
- Add `primary_class: "book"` and `label_metadata.book_lines` to the move marker payload.

The old frontend then made the selected book move feel different from a normal engine move:

- The move list showed a book icon for `primary_class === "book"`.
- The position badge showed the opening name base, not just the generic word "Book".
- The sidebar rendered `BookLinesView` instead of engine lines when book lines existed.
- Book line rows showed opening name, a relative popularity bar, and SAN chips.
- Hovering or clicking SAN chips previewed the continuation on the board.
- The preview root was `currentMove.fen_after`, because the backend book lines were continuations after the played book move.

## Current State

### Frontend

Relevant files:
- `/Users/yahorbarkouski/g6explanation-frontend/src/types/api.ts`
- `/Users/yahorbarkouski/g6explanation-frontend/src/types/analysis.ts`
- `/Users/yahorbarkouski/g6explanation-frontend/src/lib/game-analysis-mapping.ts`
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/AnalysisWorkspace.tsx`
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/EngineLinesView.tsx`
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/MoveList.tsx`
- `/Users/yahorbarkouski/g6explanation-frontend/src/components/analysis/PositionInfo.tsx`

The frontend can already display a book classification if a marker has `primary_class: "book"`. The missing pieces are:

- `GameMoveAnalysis` API type has no `opening_book` or `book_lines` field.
- API `MoveQualityLabel` does not include `book`, and it should not need to.
- `mapGameAnalysisSnapshot` does not copy book metadata into timeline points or markers.
- `AnalysisWorkspace` always routes the selected move to engine-line rendering.
- `EngineLinesView.tsx` has no `BookLinesView` equivalent.
- `PositionInfo` does not accept or display an opening name for book markers.

### Backend

Relevant files:
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/contracts.py`
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/game_analysis/analysis_runner.py`
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/context_engine/contracts.py`
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/context_engine/stockfish_analysis.py`
- `/Users/yahorbarkouski/g6explanation/src/g6explanation/visualization/http_api.py`
- `/Users/yahorbarkouski/g6explanation/docs/product/game-analysis.md`
- `/Users/yahorbarkouski/g6explanation/docs/development/game-analysis-integration.md`

The backend currently builds one `MoveContextRequest` per ply and parallelizes context analysis. It does not have a sequential opening-book pass. `GameMoveAnalysis` is generated from `ContextResult`, and there is no field where opening-book metadata can live.

The context engine's `MoveQualityLabel` does not include `book`. That is correct for the current architecture: book status is opening theory metadata, while move quality is engine/context truth. The frontend can derive display class `book` from `opening_book.is_book_move` without changing the core quality enum.

## Recommended Contract

Add explicit backend contracts under `g6explanation.game_analysis.contracts`:

```python
class BookLineMove(ContextContract):
    san: str
    uci: str


class BookLine(ContextContract):
    moves: list[BookLineMove]
    weight: int
    opening_name: str | None = None
    eco: str | None = None


class OpeningBookMetadata(ContextContract):
    is_book_move: bool
    is_novelty: bool = False
    book_lines: list[BookLine] = Field(default_factory=list)
    opening_name: str | None = None
    eco: str | None = None
```

Then extend `GameMoveAnalysis`:

```python
opening_book: OpeningBookMetadata | None = None
```

Mirror the same shape in frontend TypeScript:

```ts
export type BookLineMove = {
  san: string
  uci: string
}

export type BookLine = {
  moves: BookLineMove[]
  weight: number
  opening_name: string | null
  eco: string | null
}

export type OpeningBookMetadata = {
  is_book_move: boolean
  is_novelty: boolean
  book_lines: BookLine[]
  opening_name: string | null
  eco: string | null
}
```

Do not add `book` to backend `MoveQualityLabel` unless the product explicitly wants opening theory to become part of the move-quality taxonomy. The safer model is:

- `quality`: engine/context quality, such as `good`, `excellent`, `inaccuracy`.
- `opening_book.is_book_move`: opening-book status.
- Frontend marker `primary_class`: display class, overridden to `book` when `opening_book.is_book_move` is true.

## Implementation Plan

### Phase 1: Backend Book Provider

Port the old backend's opening-book primitives into `g6explanation`:

- Add a Polyglot reader module, for example `src/g6explanation/game_analysis/opening_book/book_reader.py`.
- Add an ECO/opening-name resolver, for example `src/g6explanation/game_analysis/opening_book/opening_names.py`.
- Use lazy, thread-safe file loading.
- Make missing assets non-fatal when the feature is disabled.
- Add settings:
  - `G6EXPLANATION_OPENING_BOOK_ENABLED`
  - `G6EXPLANATION_OPENING_BOOK_PATH`
  - `G6EXPLANATION_OPENING_NAMES_PATH`

The provider should expose these operations:

- `book_lookup(board, move)` to determine if the played move is in book.
- `book_main_lines(board_after, max_lines=3, max_depth=8)` to produce continuation lines.
- `has_book_moves(board_before)` to detect novelty.
- `lookup_opening(board)` to resolve ECO/name from the resulting position.

### Phase 2: Backend Sequential Pass

Add an opening-book pass before the context phase:

- Extend the PGN ply helper so each ply record includes `ply`, `san`, `uci`, `fen_before`, and `fen_after`.
- Iterate in game order with a real `chess.Board`.
- Track `book_ended` separately for White and Black.
- For book hits, attach opening name, ECO, and continuation lines from `board_after`.
- For misses where the side still had book moves available, mark the move as a novelty.
- Return a `dict[int, OpeningBookMetadata]` keyed by ply.

Then thread that metadata through `GameAnalysisRunner`:

- Compute `book_by_ply` once after PGN parsing.
- Keep the existing context phase for v1 so the frontend still gets FENs, engine lines, and explanation data.
- In `_move_from_context_result`, attach `opening_book=book_by_ply.get(result.ply)`.
- Keep `requires_explanation` unchanged at first. Book metadata should improve the UI without forcing extra explanations for every opening move.

### Phase 3: Frontend Types And Mapping

Update `src/types/api.ts` and `src/types/analysis.ts` with the book-line types.

Update `src/lib/game-analysis-mapping.ts`:

- Copy `move.opening_book` into timeline metadata.
- Override marker `primary_class` to `book` when `move.opening_book?.is_book_move === true`.
- Preserve the original backend `quality` in `label_metadata.quality`.
- Include `is_book_move`, `is_novelty`, `opening_name`, `eco`, and `book_lines` in marker metadata.
- Keep engine `best_lines` mapping from context evidence as-is.

This keeps the new backend fields optional, so older snapshots still render normally.

### Phase 4: Frontend UI Port

Port the old `BookLinesView` behavior into the current frontend:

- Add `BookLinesView` next to `EngineLinesView`, or split it into `BookLinesView.tsx`.
- Reuse existing `SanMove`, `sideToMoveFromFen`, board preview, and styling helpers.
- Render compact rows with:
  - relative popularity bar based on `weight`,
  - opening name base before a colon,
  - optional full-name tooltip,
  - SAN chips for each continuation move.
- In `AnalysisWorkspace`, derive:
  - `currentBookLines`
  - `currentOpeningName`
- In the sidebar slot, render book lines when the selected marker is book and has lines; otherwise keep engine lines.
- Root book previews at `currentMove?.fen_after ?? currentMove?.fen_before ?? START_FEN`.
- Pass `openingName` to `PositionInfo` and show the opening name badge for book markers.

Suggested fallback: if a move is marked book but has no continuation lines, show the opening badge but keep the engine-line panel. That avoids an empty sidebar.

### Phase 5: Tests

Backend tests:

- Unit test the opening-book pass with fake lookup functions:
  - book hits attach lines,
  - per-side book ending works,
  - novelty is marked only when the side leaves an available book line,
  - opening name and ECO propagate.
- Contract roundtrip test:
  - `GameAnalysisSnapshot.model_validate_json(...)` preserves `opening_book`.
- API integration test:
  - a fake/static analysis provider returns a snapshot with book metadata through `/api/game-analysis/{analysis_id}`.
- Missing-asset test:
  - disabled feature does not fail startup or analysis.

Frontend tests:

- Mapping test:
  - a move with `opening_book.is_book_move` maps to marker `primary_class: "book"`.
  - timeline and marker metadata include book lines and opening name.
- `BookLinesView` component test:
  - renders opening label, weights, and SAN chips.
  - chip hover/click calls preview with root FEN and SAN prefix.
- Workspace test:
  - selected book move renders `BookLinesView` instead of engine lines.
  - non-book moves still render engine lines.
- Position badge test:
  - book marker displays the opening name base before colon.

### Phase 6: Verification

Frontend verification:

- `bun run typecheck`
- targeted tests for mapping and analysis workspace components
- `bun run lint`
- `bun run build`

Backend verification:

- `uv run ruff format --check .`
- `uv run ruff check .`
- targeted opening-book and game-analysis tests
- `uv run mypy src tests`
- `uv run pyright`

For provider-facing confidence after deterministic tests pass:

- Run the real game-analysis integration gate with the existing no-mock environment expectations.

## Rollout Plan

1. Add backend contracts and disabled-by-default provider plumbing.
2. Add deterministic backend tests with fake book data.
3. Add frontend optional-field support and mapping tests.
4. Port `BookLinesView` and workspace branching.
5. Add a mock/demo snapshot with one book move for local UI review.
6. Wire real book assets in local and deployment configuration.
7. Enable the feature in staging.
8. Consider early partial book rows or engine-skipping optimizations only after the v1 contract is stable.

## Risks And Open Questions

- The old backend likely depended on local book assets such as a Polyglot `.bin` file and an ECO TSV. The `g6explanation` repo needs an explicit asset decision before enabling the feature.
- The current frontend filters mapped moves to those with `context !== null`. If the backend later wants to stream book moves before Stockfish context finishes, the frontend will need a context-less book row path with FEN metadata.
- `ContextContract` uses strict Pydantic validation, so all new fields need explicit contracts and roundtrip tests.
- Deployment needs a reliable way to ship or mount book data.
- Book popularity weights are only meaningful relative to lines from the same root position; the UI should not present them as absolute percentages.

## Recommendation

Build this as a two-sided feature with a small explicit contract. The fastest safe version is:

1. Keep Stockfish/context analysis unchanged.
2. Add opening-book metadata as an optional overlay on `GameMoveAnalysis`.
3. Let the frontend override display class to `book` and render book continuations for selected book moves.

That reproduces the old easy-to-use experience while fitting the stricter `g6explanation` architecture.
