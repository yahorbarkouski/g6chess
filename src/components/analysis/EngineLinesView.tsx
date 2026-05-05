import { Info } from "lucide-react";
import { formatEvalLong, sideToMoveFromFen } from "../../lib/chess";
import { cn } from "../../lib/utils";
import type { BestLine, BoardSide, BookLine } from "../../types/analysis";
import { MorphText } from "../ui/morph-text";

type PieceType = "K" | "Q" | "R" | "B" | "N";

const PIECE_GLYPH: Record<BoardSide, Record<PieceType, string>> = {
  white: { K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘" },
  black: { K: "♚", Q: "♛", R: "♜", B: "♝", N: "♞" },
};

const PIECE_FONT_STYLE = {
  fontFamily: '"Apple Symbols","Noto Sans Symbols 2","Segoe UI Symbol",serif',
} as const;

export interface PreviewState {
  rootFen: string;
  lineMoves: string[];
  step: number;
}

interface EngineLinesViewProps {
  rootFen: string;
  lines: BestLine[];
  onPreview: (rootFen: string, moves: string[], step: number) => void;
  activePreview?: PreviewState | null;
  playerSide?: BoardSide;
  className?: string;
}

export function EngineLinesView({
  rootFen,
  lines,
  onPreview,
  activePreview = null,
  playerSide = "white",
  className,
}: EngineLinesViewProps) {
  if (lines.length === 0) {
    return null;
  }

  return (
    <section className={cn("space-y-2", className)}>
      <h3 className="font-serif text-lg text-stone-900 dark:text-stone-100">Engine lines</h3>
      <div className="space-y-1.5">
        {lines.slice(0, 2).map((line, index) => (
          <LineRow
            activePreview={activePreview}
            fen={rootFen}
            key={`${line.uci}-${line.san}`}
            label={index === 0 ? "Best line" : `Line ${index + 1}`}
            line={line}
            onPreview={onPreview}
            playerSide={playerSide}
          />
        ))}
      </div>
    </section>
  );
}

interface BookLinesViewProps {
  bookLines: BookLine[];
  rootFen: string;
  onPreview: (rootFen: string, moves: string[], step: number) => void;
  activePreview?: PreviewState | null;
  className?: string;
}

const BOOK_LINE_COLORS = {
  rowBg: "bg-amber-50/70 dark:bg-stone-800/50",
  barBg: "bg-amber-100/70 dark:bg-amber-900/20",
  label: "text-amber-900 dark:text-amber-300",
  info: "text-amber-800 dark:text-amber-300",
  chipActive: "border-amber-300/70 bg-amber-100/90 dark:border-amber-600/60 dark:bg-amber-900/55",
  chipIdle:
    "border-amber-200/60 bg-white/70 hover:border-amber-300 dark:border-stone-700 dark:bg-stone-900/60 dark:hover:border-stone-600",
} as const;

export function BookLinesView({
  activePreview = null,
  bookLines,
  className,
  onPreview,
  rootFen,
}: BookLinesViewProps) {
  if (bookLines.length === 0) {
    return null;
  }

  const rootSide = sideToMoveFromFen(rootFen);
  const maxWeight = Math.max(...bookLines.map((line) => line.weight));

  return (
    <section className={cn("space-y-1.5", className)} aria-label="Opening book lines">
      {bookLines.map((line, index) => {
        const moveSans = line.moves.map((move) => move.san);
        const percent = maxWeight > 0 ? Math.max(6, (line.weight / maxWeight) * 100) : 0;
        const label = openingLineLabel(line, index);
        const key = line.moves[0]?.uci ?? `${label}-${index}`;

        return (
          <div className={cn("relative rounded px-2 py-1.5", BOOK_LINE_COLORS.rowBg)} key={key}>
            {percent > 0 ? (
              <div className="absolute inset-0 overflow-hidden rounded">
                <div
                  className={cn("absolute inset-y-0 left-0", BOOK_LINE_COLORS.barBg)}
                  style={{ width: `${percent}%` }}
                />
              </div>
            ) : null}

            <div className="relative">
              <div className="mb-1 flex min-w-0 items-center gap-1">
                <span
                  className={cn(
                    "truncate text-[10px] font-medium uppercase tracking-wide",
                    BOOK_LINE_COLORS.label,
                  )}
                >
                  {label}
                </span>
                {line.opening_name?.includes(":") ? (
                  <span className="group relative inline-flex shrink-0">
                    <Info className={cn("size-3 cursor-help", BOOK_LINE_COLORS.info)} />
                    <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 max-w-72 -translate-x-1/2 whitespace-nowrap rounded bg-stone-900 px-2 py-1 text-[10px] font-normal tracking-normal text-stone-100 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-stone-100 dark:text-stone-900">
                      {line.opening_name}
                    </span>
                  </span>
                ) : null}
              </div>

              <div className="scrollbar-hide flex items-center gap-1 overflow-x-auto">
                {moveSans.map((san, stepIndex) => {
                  const moveSide = stepIndex % 2 === 0 ? rootSide : otherSide(rootSide);
                  const isActive = previewMatches(activePreview, rootFen, moveSans, stepIndex + 1);
                  const moveKey = moveSans.slice(0, stepIndex + 1).join(" ");
                  return (
                    <button
                      aria-label={`Preview ${moveKey}`}
                      className={cn(
                        "inline-flex shrink-0 items-center rounded border px-1 py-0.5 transition-colors",
                        isActive ? BOOK_LINE_COLORS.chipActive : BOOK_LINE_COLORS.chipIdle,
                      )}
                      key={moveKey}
                      onClick={() => onPreview(rootFen, moveSans, stepIndex + 1)}
                      type="button"
                    >
                      <SanMove san={san} side={moveSide} />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
}

function LineRow({
  line,
  fen,
  onPreview,
  activePreview,
  label,
  playerSide,
}: {
  line: BestLine;
  fen: string;
  onPreview: (rootFen: string, moves: string[], step: number) => void;
  activePreview: PreviewState | null;
  label: string;
  playerSide: BoardSide;
}) {
  const rootSide = sideToMoveFromFen(fen);
  const moves = line.pv_san.length <= 15 ? line.pv_san : line.pv_san.slice(0, 8);

  return (
    <div className="rounded bg-stone-100/80 px-2 py-1.5 dark:bg-stone-800/40">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-stone-400 dark:text-stone-500">
          <MorphText>{label}</MorphText>
        </span>
        <span className={cn("font-mono text-[11px]", evalColorClass(line.eval_cp, playerSide))}>
          <MorphText>{formatEvalLong(line.eval_cp)}</MorphText>
        </span>
        {typeof line.expectation === "number" ? (
          <span className={cn("font-mono text-[11px]", evalColorClass(line.eval_cp, playerSide))}>
            <MorphText>{(line.expectation * 100).toFixed(0)}%</MorphText>
          </span>
        ) : null}
      </div>
      <div className="scrollbar-hide flex items-center gap-1 overflow-x-auto">
        {moves.map((san, stepIndex) => {
          const moveSide = stepIndex % 2 === 0 ? rootSide : otherSide(rootSide);
          const isActive = previewMatches(activePreview, fen, moves, stepIndex + 1);
          const moveKey = moves.slice(0, stepIndex + 1).join(" ");
          return (
            <button
              className={cn(
                "inline-flex shrink-0 items-center rounded border px-1 py-0.5 transition-colors",
                isActive
                  ? "border-stone-300 bg-stone-100 dark:border-stone-500/50 dark:bg-stone-700"
                  : "border-stone-200 bg-white/60 hover:border-stone-300 dark:border-stone-700 dark:bg-stone-900/60 dark:hover:border-stone-600",
              )}
              key={moveKey}
              onClick={() => onPreview(fen, moves, stepIndex + 1)}
              type="button"
            >
              <SanMove san={san} side={moveSide} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SanMove({ san, side }: { san: string; side: BoardSide }) {
  const isCastle = san.startsWith("O-O") || san.startsWith("0-0");
  const first = san[0];

  if (isCastle) {
    return (
      <span className="inline-flex min-w-0 items-center gap-0.5">
        <span
          className="text-[14px] leading-none text-stone-700 dark:text-stone-300"
          style={PIECE_FONT_STYLE}
        >
          {PIECE_GLYPH[side].K}
        </span>
        <span className="truncate font-mono text-[12px] text-stone-700 dark:text-stone-300">
          {san}
        </span>
      </span>
    );
  }

  if (first !== undefined && isPieceType(first)) {
    return (
      <span className="inline-flex min-w-0 items-center gap-0.5">
        <span
          className="text-[14px] leading-none text-stone-700 dark:text-stone-300"
          style={PIECE_FONT_STYLE}
        >
          {PIECE_GLYPH[side][first]}
        </span>
        <span className="truncate font-mono text-[12px] text-stone-700 dark:text-stone-300">
          {san.slice(1)}
        </span>
      </span>
    );
  }

  return (
    <span className="truncate font-mono text-[12px] text-stone-700 dark:text-stone-300">{san}</span>
  );
}

function evalColorClass(evalCp: number, playerSide: BoardSide): string {
  const adjusted = playerSide === "black" ? -evalCp : evalCp;
  if (adjusted >= 50) {
    return "text-emerald-600 dark:text-emerald-400";
  }
  if (adjusted <= -50) {
    return "text-rose-500 dark:text-rose-400";
  }
  return "text-stone-500 dark:text-stone-400";
}

function openingLineLabel(line: BookLine, index: number): string {
  if (!line.opening_name) {
    return index === 0 ? "Main line" : "Alternative";
  }
  const splitAt = line.opening_name.indexOf(":");
  return splitAt === -1 ? line.opening_name : line.opening_name.slice(0, splitAt);
}

function otherSide(side: BoardSide): BoardSide {
  return side === "white" ? "black" : "white";
}

function isPieceType(c: string): c is PieceType {
  return c === "K" || c === "Q" || c === "R" || c === "B" || c === "N";
}

function previewMatches(
  activePreview: PreviewState | null,
  rootFen: string,
  moves: string[],
  step: number,
) {
  if (!activePreview || activePreview.rootFen !== rootFen || activePreview.step !== step) {
    return false;
  }
  if (activePreview.lineMoves.length !== moves.length) {
    return false;
  }
  return activePreview.lineMoves.every((move, index) => move === moves[index]);
}
