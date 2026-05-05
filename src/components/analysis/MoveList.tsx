import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowRight, BookOpen, Star, ThumbsUp } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef } from "react";
import { analysisTagLabel, primaryClassLabel } from "../../lib/analysis-format";
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

type PieceType = "K" | "Q" | "R" | "B" | "N";
export type MarkerDisplayMode = "critical" | "all";

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
  const pairs = useMemo(() => pairMoves(moves), [moves]);
  const displayedMarkers = useMemo(
    () => (markerDisplayMode === "all" ? moveMarkers : moveMarkers.filter(isDefaultVisibleMarker)),
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

  return (
    <div className={cn("group/moves flex h-full min-h-0 flex-col", className)}>
      <div className="relative grid grid-cols-[10%_1fr_1fr] items-center border-stone-200 px-2 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.08em] text-stone-400 dark:border-stone-800 dark:text-stone-500">
        <span className="text-center pt-2" />
        <span className="border-stone-200 border-t pt-2 pr-1 text-center dark:border-stone-800">
          White
        </span>
        <span className="border-stone-200 border-t pt-2 pl-1 text-center dark:border-stone-800">
          Black
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-1.5 py-1">
        {pairs.map((pair) => (
          <MoveRow
            blackIsActive={pair.black?.ply === currentPly}
            blackIsCritical={Boolean(pair.black && criticalPlys.has(pair.black.ply))}
            blackMarker={pair.black ? markerByPly.get(pair.black.ply) : undefined}
            key={`${pair.moveNumber}-${pair.white?.ply ?? "w"}-${pair.black?.ply ?? "b"}`}
            onSelectPly={onSelectPly}
            pair={pair}
            whiteIsActive={pair.white?.ply === currentPly}
            whiteIsCritical={Boolean(pair.white && criticalPlys.has(pair.white.ply))}
            whiteMarker={pair.white ? markerByPly.get(pair.white.ply) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

function MoveRow({
  pair,
  whiteMarker,
  blackMarker,
  whiteIsActive,
  blackIsActive,
  whiteIsCritical,
  blackIsCritical,
  onSelectPly,
}: {
  pair: MovePair;
  whiteMarker: AnalysisMoveMarker | undefined;
  blackMarker: AnalysisMoveMarker | undefined;
  whiteIsActive: boolean;
  blackIsActive: boolean;
  whiteIsCritical: boolean;
  blackIsCritical: boolean;
  onSelectPly: (ply: number) => void;
}) {
  return (
    <div className="grid grid-cols-[10%_1fr_1fr] items-center py-px">
      <span className="text-center text-[10px] text-stone-400 dark:text-stone-500">
        {pair.moveNumber}.
      </span>
      <div className="border-stone-200/60 border-r pr-1 dark:border-stone-800/60">
        <MoveCell
          isActive={whiteIsActive}
          isCritical={whiteIsCritical}
          marker={whiteMarker}
          move={pair.white}
          onClick={onSelectPly}
        />
      </div>
      <div className="pl-1">
        <MoveCell
          isActive={blackIsActive}
          isCritical={blackIsCritical}
          marker={blackMarker}
          move={pair.black}
          onClick={onSelectPly}
        />
      </div>
    </div>
  );
}

function MoveCell({
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
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (isActive) {
      ref.current?.scrollIntoView({ block: "nearest" });
    }
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
        isActive && prefersReducedMotion && "bg-stone-100 dark:bg-stone-800/80",
      )}
      onClick={() => onClick(move.ply)}
      ref={isActive ? ref : undefined}
      title={
        marker?.tags.length
          ? marker.tags.map((tag) => analysisTagLabel(tag)).join(" · ")
          : undefined
      }
      type="button"
    >
      <AnimatePresence initial={false}>
        {isActive ? (
          <motion.div
            animate={{ opacity: 1, scale: 1 }}
            className="absolute inset-0 rounded bg-stone-100 dark:bg-stone-800/80"
            exit={{ opacity: 0, scale: 0.95 }}
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.95 }}
            transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.2, ease: "easeOut" }}
          />
        ) : null}
      </AnimatePresence>
      <span className="relative z-10 flex min-w-0 flex-1 items-center gap-1 pl-0.5">
        <span className="inline-flex w-5 shrink-0 items-center justify-center">
          {token ? (
            <span
              className={cn(
                "inline-flex size-3.5 items-center justify-center rounded-full text-[9px] font-semibold",
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
}

function isCriticalMarker(marker: AnalysisMoveMarker): boolean {
  return (
    marker.label_metadata.requires_explanation === true ||
    marker.tags.includes("critical_significance")
  );
}

function isDefaultVisibleMarker(marker: AnalysisMoveMarker): boolean {
  return isCriticalMarker(marker) || marker.primary_class === "book";
}

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

function qualityToken(
  marker: AnalysisMoveMarker | undefined,
): { content: ReactNode; className: string } | null {
  if (!marker) {
    return null;
  }
  const pc = marker.primary_class;
  if (pc === "blunder") {
    return { content: "??", className: "bg-rose-500/80 text-white" };
  }
  if (pc === "mistake" || pc === "miss") {
    return { content: "?", className: "bg-orange-400 text-white" };
  }
  if (pc === "inaccuracy") {
    return { content: "?!", className: "bg-yellow-400 text-stone-900" };
  }
  if (pc === "brilliant" || pc === "great") {
    return { content: "!", className: "bg-blue-500 text-white" };
  }
  if (pc === "best") {
    return {
      content: <Star className="size-2 fill-current" />,
      className: "bg-emerald-500 text-white",
    };
  }
  if (pc === "excellent") {
    return {
      content: <ThumbsUp className="size-2 fill-current" />,
      className: "bg-emerald-500 text-white",
    };
  }
  if (pc === "book") {
    return {
      content: <BookOpen className="size-2 fill-current" />,
      className: "bg-amber-800/80 text-amber-100 dark:bg-amber-700/80",
    };
  }
  if (marker.tags.includes("forced")) {
    return {
      content: <ArrowRight className="size-2" />,
      className: "bg-stone-400 text-white dark:bg-stone-500",
    };
  }
  return { content: "✓", className: "bg-[#7a8a72] text-white" };
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
