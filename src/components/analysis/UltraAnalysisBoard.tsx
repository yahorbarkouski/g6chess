import {
  type Arrow,
  type BoardModel,
  decodePackedMove,
  type PackedMove,
  type SquareIndex,
} from "@ultrachess/core";
import { chesscom } from "@ultrachess/pieces/chesscom";
import {
  Chessboard,
  type MoveHapticOptions,
  type MoveSoundOptions,
  type PositionTransition,
  useChessGame,
} from "@ultrachess/react";
import { green } from "@ultrachess/themes/green";
import {
  type CSSProperties,
  memo,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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
const COARSE_POINTER_QUERY = "(hover: none), (pointer: coarse)";

export type BoardArrow = readonly [string, string, string?];
export type BoardTransitionMove = PositionTransition;

interface UltraAnalysisBoardProps {
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
  feedbackSide?: "white" | "black" | null;
  onWheel?: (event: WheelEvent) => void;
  className?: string;
}

function UltraAnalysisBoardBase({
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
  feedbackSide = null,
  onWheel,
  className,
}: UltraAnalysisBoardProps) {
  const game = useChessGame();
  const boardRef = useRef<HTMLDivElement | null>(null);

  const managedArrows = useManagedArrows(arrows);
  const animation = useMemo(
    () => (animationMs > 0 ? { ...BOARD_ANIMATION, durationMs: animationMs } : NO_ANIMATION),
    [animationMs],
  );
  const renderSquare = useHighlightedSquareOverlay(highlightedMove);
  const handleMove = useOnMoveAdapter(game, onPieceDrop);
  const coarsePointer = useCoarsePointer();
  const feedbackPerspective = useMemo(
    () => sideToFeedbackPerspective(feedbackSide),
    [feedbackSide],
  );
  const moveSound = useMemo<false | MoveSoundOptions>(
    () =>
      coarsePointer
        ? false
        : {
            enabled: true,
            ...(feedbackPerspective === undefined ? {} : { perspective: feedbackPerspective }),
          },
    [coarsePointer, feedbackPerspective],
  );
  const moveHaptics = useMemo<false | MoveHapticOptions>(
    () =>
      coarsePointer
        ? {
            enabled: true,
            ...(feedbackPerspective === undefined ? {} : { perspective: feedbackPerspective }),
          }
        : false,
    [coarsePointer, feedbackPerspective],
  );

  useEffect(() => {
    const board = boardRef.current;
    if (!board || !onWheel) {
      return;
    }
    board.addEventListener("wheel", onWheel, { capture: true, passive: false });
    return () => board.removeEventListener("wheel", onWheel, { capture: true });
  }, [onWheel]);

  return (
    <div
      className={cn(
        "chess-board-wrap relative w-full overflow-hidden rounded-[5px]",
        shadowed &&
          "shadow-[0_18px_44px_rgba(41,37,36,0.22)] dark:shadow-[0_18px_44px_rgba(0,0,0,0.38)]",
        dimmed && "opacity-95",
        className,
      )}
      ref={boardRef}
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
        haptics={moveHaptics}
        sound={moveSound}
        theme={green}
      />
    </div>
  );
}

export const UltraAnalysisBoard = memo(UltraAnalysisBoardBase, areUltraAnalysisBoardPropsEqual);

function areUltraAnalysisBoardPropsEqual(
  previous: UltraAnalysisBoardProps,
  next: UltraAnalysisBoardProps,
): boolean {
  return (
    previous.fen === next.fen &&
    (previous.orientation ?? "white") === (next.orientation ?? "white") &&
    areBoardArrowsEqual(previous.arrows ?? EMPTY_BOARD_ARROWS, next.arrows ?? EMPTY_BOARD_ARROWS) &&
    (previous.highlightedMove ?? null) === (next.highlightedMove ?? null) &&
    areTransitionMovesEqual(previous.transitionMove ?? null, next.transitionMove ?? null) &&
    (previous.allowDragging ?? false) === (next.allowDragging ?? false) &&
    (previous.allowDrawingArrows ?? true) === (next.allowDrawingArrows ?? true) &&
    previous.onPieceDrop === next.onPieceDrop &&
    (previous.animationMs ?? 45) === (next.animationMs ?? 45) &&
    (previous.shadowed ?? true) === (next.shadowed ?? true) &&
    (previous.dimmed ?? false) === (next.dimmed ?? false) &&
    (previous.showCoordinates ?? true) === (next.showCoordinates ?? true) &&
    (previous.feedbackSide ?? null) === (next.feedbackSide ?? null) &&
    previous.onWheel === next.onWheel &&
    previous.className === next.className
  );
}

function sideToFeedbackPerspective(side: "white" | "black" | null): 0 | 1 | undefined {
  if (side === "white") {
    return 0;
  }
  if (side === "black") {
    return 1;
  }
  return undefined;
}

function useCoarsePointer(): boolean {
  const [coarsePointer, setCoarsePointer] = useState(readCoarsePointer);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mediaQuery = window.matchMedia(COARSE_POINTER_QUERY);
    const update = () => setCoarsePointer(mediaQuery.matches);
    update();
    mediaQuery.addEventListener?.("change", update);
    return () => mediaQuery.removeEventListener?.("change", update);
  }, []);

  return coarsePointer;
}

function readCoarsePointer(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(COARSE_POINTER_QUERY).matches;
}

function areBoardArrowsEqual(
  previous: ReadonlyArray<BoardArrow>,
  next: ReadonlyArray<BoardArrow>,
): boolean {
  if (previous === next) {
    return true;
  }
  if (previous.length !== next.length) {
    return false;
  }
  return previous.every((arrow, index) => {
    const nextArrow = next[index];
    return (
      nextArrow !== undefined &&
      arrow[0] === nextArrow[0] &&
      arrow[1] === nextArrow[1] &&
      arrow[2] === nextArrow[2]
    );
  });
}

function areTransitionMovesEqual(
  previous: BoardTransitionMove | null,
  next: BoardTransitionMove | null,
): boolean {
  if (previous === next) {
    return true;
  }
  if (previous === null || next === null) {
    return false;
  }
  return (
    previous.uci === next.uci && previous.direction === next.direction && previous.key === next.key
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
