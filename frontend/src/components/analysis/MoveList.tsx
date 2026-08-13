import { memo, useEffect, useMemo, useRef } from "react";
import {
  analysisTagLabel,
  isCriticalMarker,
  primaryClassLabel,
  qualityToken,
} from "../../lib/analysis-format";
import { formatClock } from "../../lib/chess";
import { cn } from "../../lib/utils";
import type { AnalysisMoveMarker, GameMove } from "../../types/analysis";

interface MoveListProps {
  moves: GameMove[];
  moveMarkers: AnalysisMoveMarker[];
  currentPly: number;
  onSelectPly: (ply: number) => void;
  markerDisplayMode?: MarkerDisplayMode;
  className?: string;
}

interface MovePair {
  moveNumber: number;
  white: GameMove | null;
  black: GameMove | null;
}

interface MoveRowData extends MovePair {
  key: string;
  whiteMarker: AnalysisMoveMarker | undefined;
  blackMarker: AnalysisMoveMarker | undefined;
  whiteIsCritical: boolean;
  blackIsCritical: boolean;
}

type PieceType = "K" | "Q" | "R" | "B" | "N";
export type MarkerDisplayMode = "critical" | "all";

const ACTIVE_MOVE_SCROLL_MARGIN_PX = 4;

const PIECE_GLYPH: Record<"white" | "black", Record<PieceType, string>> = {
  white: { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘" },
  black: { K: "♚", Q: "♛", R: "♜", B: "♝", N: "♞" },
};

export function MoveList({
  moves,
  moveMarkers,
  currentPly,
  onSelectPly,
  markerDisplayMode = "critical",
  className,
}: MoveListProps) {
  const displayedMarkers = useMemo(
    () => (markerDisplayMode === "all" ? moveMarkers : moveMarkers.filter(isCriticalMarker)),
    [markerDisplayMode, moveMarkers],
  );
  const markerByPly = useMemo(
    () => new Map(displayedMarkers.map((marker) => [marker.ply, marker])),
    [displayedMarkers],
  );
  const criticalPlys = useMemo(
    () => new Set(moveMarkers.filter(isCriticalMarker).map((marker) => marker.ply)),
    [moveMarkers],
  );
  const rows = useMemo(
    () => buildMoveRows(moves, markerByPly, criticalPlys),
    [criticalPlys, markerByPly, moves],
  );

  return (
    <div className={cn("group/moves flex h-full min-h-0 flex-col", className)}>
      <div className="relative grid grid-cols-[10%_1fr_1fr] items-center border-stone-200 px-2 pb-2 md:pt-4 text-[10px] font-semibold uppercase tracking-[0.08em] text-stone-400 dark:border-stone-800 dark:text-stone-500">
        <span className="text-center pt-2" />
        <span className="border-stone-200 border-t pt-2 pr-1 text-center dark:border-stone-800">
          White
        </span>
        <span className="border-stone-200 border-t pt-2 pl-1 text-center dark:border-stone-800">
          Black
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-1.5 py-1">
        {rows.map((row) => (
          <MoveRow
            blackIsActive={row.black?.ply === currentPly}
            key={row.key}
            onSelectPly={onSelectPly}
            row={row}
            whiteIsActive={row.white?.ply === currentPly}
          />
        ))}
      </div>
    </div>
  );
}

const MoveRow = memo(function MoveRow({
  row,
  whiteIsActive,
  blackIsActive,
  onSelectPly,
}: {
  row: MoveRowData;
  whiteIsActive: boolean;
  blackIsActive: boolean;
  onSelectPly: (ply: number) => void;
}) {
  return (
    <div className="grid grid-cols-[10%_1fr_1fr] items-center py-px">
      <span className="text-center text-[10px] text-stone-400 dark:text-stone-500">
        {row.moveNumber}.
      </span>
      <div className="border-stone-200/60 border-r pr-1 dark:border-stone-800/60">
        <MoveCell
          isActive={whiteIsActive}
          isCritical={row.whiteIsCritical}
          marker={row.whiteMarker}
          move={row.white}
          onClick={onSelectPly}
        />
      </div>
      <div className="pl-1">
        <MoveCell
          isActive={blackIsActive}
          isCritical={row.blackIsCritical}
          marker={row.blackMarker}
          move={row.black}
          onClick={onSelectPly}
        />
      </div>
    </div>
  );
});

const MoveCell = memo(function MoveCell({
  move,
  marker,
  isActive,
  isCritical,
  onClick,
}: {
  move: GameMove | null;
  marker: AnalysisMoveMarker | undefined;
  isActive: boolean;
  isCritical: boolean;
  onClick: (ply: number) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isActive) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      scrollIntoViewIfNeeded(ref.current);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [isActive]);

  if (!move) {
    return <div className="h-7" />;
  }

  const token = qualityToken(marker);
  const pieceType = extractPieceType(move.san);
  const glyph = pieceType ? PIECE_GLYPH[move.side][pieceType] : null;
  const timeLabel = formatThinkTime(move);
  const tagHint = marker?.tags.length
    ? ` · ${marker.tags.map((tag) => analysisTagLabel(tag)).join(", ")}`
    : "";

  return (
    <button
      aria-label={`${move.move_number}${move.side === "white" ? "." : "..."} ${move.san}${
        marker ? ` ${primaryClassLabel(marker.primary_class)}` : ""
      }${tagHint}`}
      className={cn(
        "relative flex h-7 w-full min-w-0 items-center rounded px-1 text-left text-xs",
        "transition-colors hover:bg-stone-100 dark:hover:bg-stone-800/60",
        isActive && "bg-stone-100 dark:bg-stone-800/80",
      )}
      onClick={() => onClick(move.ply)}
      ref={isActive ? ref : undefined}
      aria-current={isActive ? "step" : undefined}
      title={
        marker?.tags.length
          ? marker.tags.map((tag) => analysisTagLabel(tag)).join(" · ")
          : undefined
      }
      type="button"
    >
      <span className="relative z-10 flex min-w-0 flex-1 items-center gap-1 pl-0.5">
        <span className="inline-flex w-5 shrink-0 items-center justify-center">
          {token ? (
            <span
              className={cn(
                "inline-flex size-3.5 items-center justify-center rounded-full text-[9px] font-semibold leading-none",
                token.className,
              )}
            >
              {token.content}
            </span>
          ) : null}
        </span>
        <span
          className="inline-flex w-[17px] shrink-0 items-center justify-center"
          style={{ fontFamily: '"Apple Symbols","Noto Sans Symbols 2","Segoe UI Symbol",serif' }}
        >
          {glyph ? (
            <span
              className={cn(
                "text-[17px] leading-none",
                move.side === "white"
                  ? "text-stone-800 dark:text-stone-200"
                  : "text-stone-500 dark:text-stone-400",
              )}
            >
              {glyph}
            </span>
          ) : null}
        </span>
        <span
          className={cn(
            "truncate font-mono text-[13px]",
            isActive
              ? "font-semibold text-stone-900 dark:text-stone-100"
              : "font-medium text-stone-700 dark:text-stone-300",
          )}
        >
          {move.san}
        </span>
      </span>
      <span className="relative z-10 flex w-8 shrink-0 items-center justify-end gap-0.5">
        {isCritical ? (
          <span className="text-[9px] font-semibold text-amber-500 dark:text-amber-400">!</span>
        ) : null}
        {timeLabel ? (
          <span className="text-right text-[10px] text-stone-400 tabular-nums dark:text-stone-500">
            {timeLabel}
          </span>
        ) : null}
      </span>
    </button>
  );
});

function pairMoves(moves: GameMove[]): MovePair[] {
  const pairs: MovePair[] = [];
  for (const move of moves) {
    const moveNumber = Math.ceil(move.ply / 2);
    if (move.side === "white") {
      pairs.push({ moveNumber, white: move, black: null });
    } else if (pairs.length > 0 && pairs[pairs.length - 1]?.black === null) {
      pairs[pairs.length - 1] = { ...pairs[pairs.length - 1], black: move } as MovePair;
    } else {
      pairs.push({ moveNumber, white: null, black: move });
    }
  }
  return pairs;
}

function buildMoveRows(
  moves: GameMove[],
  markerByPly: Map<number, AnalysisMoveMarker>,
  criticalPlys: Set<number>,
): MoveRowData[] {
  return pairMoves(moves).map((pair) => {
    const whitePly = pair.white?.ply;
    const blackPly = pair.black?.ply;
    return {
      ...pair,
      key: `${pair.moveNumber}-${whitePly ?? "w"}-${blackPly ?? "b"}`,
      whiteMarker: whitePly === undefined ? undefined : markerByPly.get(whitePly),
      blackMarker: blackPly === undefined ? undefined : markerByPly.get(blackPly),
      whiteIsCritical: whitePly === undefined ? false : criticalPlys.has(whitePly),
      blackIsCritical: blackPly === undefined ? false : criticalPlys.has(blackPly),
    };
  });
}

function extractPieceType(san: string): PieceType | null {
  if (san.startsWith("O-O")) {
    return "K";
  }
  const first = san[0];
  return first === "K" || first === "Q" || first === "R" || first === "B" || first === "N"
    ? first
    : null;
}

function formatThinkTime(move: GameMove): string {
  if (move.think_time_seconds != null) {
    const seconds = Math.max(0, move.think_time_seconds);
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }
    return `${Math.floor(seconds / 60)}m`;
  }
  if (move.remaining_clock_seconds != null) {
    return formatClock(move.remaining_clock_seconds);
  }
  return "";
}

function scrollIntoViewIfNeeded(element: HTMLElement | null): void {
  if (element === null) {
    return;
  }
  const container = nearestScrollContainer(element);
  if (container === null) {
    return;
  }

  const elementRect = element.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  const isAbove = elementRect.top < containerRect.top + ACTIVE_MOVE_SCROLL_MARGIN_PX;
  const isBelow = elementRect.bottom > containerRect.bottom - ACTIVE_MOVE_SCROLL_MARGIN_PX;
  if (!isAbove && !isBelow) {
    return;
  }

  element.scrollIntoView({ block: "nearest" });
}

function nearestScrollContainer(element: HTMLElement): HTMLElement | null {
  let current = element.parentElement;
  while (current !== null) {
    if (current.scrollHeight > current.clientHeight) {
      return current;
    }
    current = current.parentElement;
  }
  return null;
}
