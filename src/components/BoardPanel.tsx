import type { BoardModel } from "@ultrachess/core";
import { chesscom } from "@ultrachess/pieces/chesscom";
import { Chessboard, useChessGame } from "@ultrachess/react";
import { green } from "@ultrachess/themes/green";
import { useEffect, useMemo } from "react";
import { uciToArrow } from "../lib/chess";
import { cn } from "../lib/utils";
import type {
  CandidateMove,
  VisualizationExample,
  VisualizationMove,
  VisualizationMoveContext,
} from "../types/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface BoardPanelProps {
  example: VisualizationExample | null;
  move: VisualizationMove | null;
  context: VisualizationMoveContext | null;
  selectedPly: number;
  viewMode: "before" | "after";
  onViewModeChange: (mode: "before" | "after") => void;
}

export function BoardPanel({
  example,
  move,
  context,
  selectedPly,
  viewMode,
  onViewModeChange,
}: BoardPanelProps) {
  const displayFen = useMemo(() => {
    if (example === null) {
      return undefined;
    }
    if (move === null) {
      return example.initial_fen;
    }
    return viewMode === "before" ? move.fen_before : move.fen_after;
  }, [example, move, viewMode]);
  const startFen = example?.initial_fen;

  const game = useChessGame(startFen === undefined ? undefined : { fen: startFen });
  const keyCandidate = useMemo(() => findKeyCandidate(context), [context]);

  useEffect(() => {
    if (game === null || displayFen === undefined) {
      return;
    }
    try {
      game.load(displayFen);
      setContextArrows(game, move, keyCandidate, viewMode);
    } catch (error) {
      if (isDisposedEngineError(error)) {
        return;
      }
      throw error;
    }
  }, [displayFen, game, keyCandidate, move, viewMode]);

  return (
    <section className="rounded-lg bg-white p-3 shadow-[0_1px_2px_rgba(68,64,60,0.08),0_10px_30px_rgba(68,64,60,0.08)]">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral">Ply {selectedPly}</Badge>
          {move === null ? null : <Badge tone="amber">{move.san}</Badge>}
          {context === null ? null : <Badge tone="green">Context</Badge>}
        </div>
        <div className="inline-flex rounded-md bg-stone-100 p-1">
          {(["before", "after"] as const).map((mode) => (
            <Button
              aria-pressed={viewMode === mode}
              className={cn(
                "h-9 min-h-9 px-3 capitalize",
                viewMode === mode && "bg-white shadow-sm hover:bg-white",
              )}
              key={mode}
              onClick={() => onViewModeChange(mode)}
              size="sm"
              variant="ghost"
            >
              {mode}
            </Button>
          ))}
        </div>
      </div>
      <div className="mx-auto w-full max-w-[720px] overflow-hidden rounded-lg shadow-[0_20px_50px_rgba(41,37,36,0.18)]">
        <Chessboard
          allowDrawingArrows={false}
          game={game}
          orientation={example?.orientation ?? "white"}
          pieces={chesscom}
          showLegalTargets={false}
          sound={false}
          style={{ width: "100%", aspectRatio: "1 / 1" }}
          theme={green}
          viewOnly
          {...(displayFen === undefined ? {} : { fallbackFen: displayFen })}
        />
      </div>
    </section>
  );
}

function findKeyCandidate(context: VisualizationMoveContext | null): CandidateMove | null {
  if (context?.result.llm_context.best_or_key_move === null || context === null) {
    return null;
  }
  const keyMove = context.result.llm_context.best_or_key_move.move;
  return context.result.evidence.candidates.find((candidate) => candidate.san === keyMove) ?? null;
}

function setContextArrows(
  game: BoardModel,
  move: VisualizationMove | null,
  keyCandidate: CandidateMove | null,
  viewMode: "before" | "after",
) {
  if (move === null) {
    game.setManagedArrows([]);
    return;
  }
  const arrows = [uciToArrow(move.uci, "rgba(217, 119, 6, 0.86)")];
  if (viewMode === "before" && keyCandidate !== null && keyCandidate.uci !== move.uci) {
    arrows.push(uciToArrow(keyCandidate.uci, "rgba(2, 132, 199, 0.82)"));
  }
  game.setManagedArrows(arrows);
}

function isDisposedEngineError(error: unknown): boolean {
  return error instanceof Error && error.message.includes("disposed");
}
