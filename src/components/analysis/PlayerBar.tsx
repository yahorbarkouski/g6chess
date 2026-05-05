import { formatClock } from "../../lib/chess";
import { cn } from "../../lib/utils";
import type { CapturedPieces } from "../../types/analysis";
import { MorphText } from "../ui/morph-text";

const PIECE_UNICODE: Record<"white" | "black", Record<string, string>> = {
  white: { q: "♕", r: "♖", b: "♗", n: "♘", p: "♙" },
  black: { q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" },
};

const PIECE_ORDER = ["q", "r", "b", "n", "p"] as const;

interface PlayerBarProps {
  name: string;
  rating?: number | null;
  side: "white" | "black";
  captured: CapturedPieces;
  materialAdvantage: number;
  clockSeconds?: number | null | undefined;
  className?: string;
}

export function PlayerBar({
  name,
  rating,
  side,
  captured,
  materialAdvantage,
  clockSeconds,
  className,
}: PlayerBarProps) {
  const capturedSide = side === "white" ? "black" : "white";
  const showAdvantage =
    (side === "white" && materialAdvantage > 0) || (side === "black" && materialAdvantage < 0);

  return (
    <div className={cn("flex items-center gap-3 pl-2", className)}>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div className="flex min-w-0 items-baseline gap-1.5">
          <span className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">
            {name}
          </span>
          <span className="shrink-0 text-xs text-stone-400 dark:text-stone-500">
            {rating ? `(${rating})` : ""}
          </span>
        </div>
      </div>
      <div className="flex min-h-5 items-center gap-px">
        {capturedPieceTokens(captured).map(({ id, piece }) => (
          <span className="text-base leading-none text-stone-500 dark:text-stone-400" key={id}>
            {PIECE_UNICODE[capturedSide][piece]}
          </span>
        ))}
        {showAdvantage ? (
          <span className="ml-1 text-xs font-semibold text-stone-500 dark:text-stone-300">
            +{Math.abs(materialAdvantage)}
          </span>
        ) : null}
      </div>
      <div className="rounded border-stone-300 bg-stone-100/80 px-2 py-1 font-mono text-sm text-stone-700 tabular-nums dark:border-stone-700 dark:bg-stone-950 dark:text-stone-300">
        <MorphText>{formatClock(clockSeconds)}</MorphText>
      </div>
    </div>
  );
}

function capturedPieceTokens(captured: CapturedPieces): Array<{ id: string; piece: string }> {
  const tokens: Array<{ id: string; piece: string }> = [];
  for (const piece of PIECE_ORDER) {
    for (let occurrence = 1; occurrence <= captured[piece]; occurrence += 1) {
      tokens.push({ id: `${piece}-${occurrence}`, piece });
    }
  }
  return tokens;
}
