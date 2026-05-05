import {
  type Arrow,
  type BoardModel,
  decodePackedMove,
  type PackedMove,
  type SquareIndex,
} from "@ultrachess/core";
import { chesscom } from "@ultrachess/pieces/chesscom";
import { Chessboard, type PositionTransition, useChessGame } from "@ultrachess/react";
import { green } from "@ultrachess/themes/green";
import { type CSSProperties, type ReactNode, useCallback, useMemo } from "react";
import { parseSquare } from "ultrachess";
import { pieceCodeAtSquare, squareName, uciToSquares } from "../../lib/chess";
import { cn } from "../../lib/utils";

const BOARD_ANIMATION = {
  durationMs: 45,
  easing: "cubic-bezier(0.22, 0.61, 0.36, 1)",
} as const;

const HIGHLIGHTED_SQUARE_STYLE: CSSProperties = {
  position: "absolute",
  inset: 0,
  backgroundColor: "var(--ucr-last-move)",
  pointerEvents: "none",
};

const EMPTY_ARROWS: readonly Arrow[] = Object.freeze([]);
const EMPTY_BOARD_ARROWS: ReadonlyArray<BoardArrow> = [];
const NO_ANIMATION = { durationMs: 0 } as const;

export type BoardArrow = readonly [string, string, string?];
export type BoardTransitionMove = PositionTransition;

export interface UltraAnalysisBoardProps {
  fen: string;
  orientation?: "white" | "black";
  arrows?: ReadonlyArray<BoardArrow>;
  highlightedMove?: string | null;
  transitionMove?: BoardTransitionMove | null;
  allowDragging?: boolean;
  allowDrawingArrows?: boolean;
  onPieceDrop?: (args: {
    sourceSquare: string;
    targetSquare: string | null;
    piece: string;
  }) => boolean;
  animationMs?: number;
  shadowed?: boolean;
  dimmed?: boolean;
  showCoordinates?: boolean;
  className?: string;
}

export function UltraAnalysisBoard({
  fen,
  orientation = "white",
  arrows = EMPTY_BOARD_ARROWS,
  highlightedMove = null,
  transitionMove = null,
  allowDragging = false,
  allowDrawingArrows = true,
  onPieceDrop,
  animationMs = 45,
  shadowed = true,
  dimmed = false,
  showCoordinates = true,
  className,
}: UltraAnalysisBoardProps) {
  const game = useChessGame();

  const managedArrows = useManagedArrows(arrows);
  const animation = useMemo(
    () => (animationMs > 0 ? { ...BOARD_ANIMATION, durationMs: animationMs } : NO_ANIMATION),
    [animationMs],
  );
  const renderSquare = useHighlightedSquareOverlay(highlightedMove);
  const handleMove = useOnMoveAdapter(game, onPieceDrop);

  return (
    <div
      className={cn(
        "chess-board-wrap relative w-full overflow-hidden rounded-[5px]",
        shadowed &&
          "shadow-[0_18px_44px_rgba(41,37,36,0.22)] dark:shadow-[0_18px_44px_rgba(0,0,0,0.38)]",
        dimmed && "opacity-95",
        className,
      )}
    >
      <Chessboard
        allowDrag={allowDragging}
        allowDrawingArrows={allowDrawingArrows}
        allowPremove={false}
        animation={animation}
        fallbackFen={fen}
        game={game}
        highlightLastMove={false}
        managedArrows={managedArrows}
        onMove={handleMove}
        orientation={orientation}
        pieces={chesscom}
        positionFen={fen}
        positionTransition={transitionMove}
        renderSquare={renderSquare}
        showCheckHighlight
        showCoordinates={showCoordinates}
        showLegalTargets="dots"
        sound={false}
        theme={green}
      />
    </div>
  );
}

function useManagedArrows(arrows: ReadonlyArray<BoardArrow>): readonly Arrow[] {
  return useMemo<readonly Arrow[]>(() => {
    if (arrows.length === 0) {
      return EMPTY_ARROWS;
    }
    const out: Arrow[] = [];
    for (const [from, to, color] of arrows) {
      const fromIdx = toSquareIndexFromName(from);
      const toIdx = toSquareIndexFromName(to);
      if (fromIdx === null || toIdx === null) {
        continue;
      }
      out.push({
        from: fromIdx,
        to: toIdx,
        color: color ?? "rgba(56, 189, 248, 0.62)",
        managed: true,
      });
    }
    return out;
  }, [arrows]);
}

function useHighlightedSquareOverlay(
  highlightedMove: string | null,
): (ctx: { index: SquareIndex }) => ReactNode {
  const highlighted = useMemo(() => {
    if (!highlightedMove) {
      return null;
    }
    const squares = uciToSquares(highlightedMove);
    return squares ? new Set(squares) : null;
  }, [highlightedMove]);

  return useCallback(
    ({ index }) => {
      if (highlighted === null || !highlighted.has(squareName(index))) {
        return null;
      }
      return <div aria-hidden style={HIGHLIGHTED_SQUARE_STYLE} />;
    },
    [highlighted],
  );
}

function useOnMoveAdapter(
  game: BoardModel | null,
  onPieceDrop: UltraAnalysisBoardProps["onPieceDrop"],
): (move: PackedMove) => void {
  return useCallback(
    (packed: PackedMove) => {
      if (onPieceDrop === undefined || game === null) {
        return;
      }
      const decoded = decodePackedMove(packed);
      onPieceDrop({
        sourceSquare: squareName(decoded.from),
        targetSquare: squareName(decoded.to),
        piece: pieceCodeAtSquare(game, decoded.to),
      });
    },
    [game, onPieceDrop],
  );
}

function toSquareIndexFromName(name: string): SquareIndex | null {
  const value = parseSquare(name);
  return value === null ? null : (value as SquareIndex);
}
