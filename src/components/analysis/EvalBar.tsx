import { parseMateFromCp } from "../../lib/chess";
import { cn } from "../../lib/utils";
import { MorphText } from "../ui/morph-text";

const EVAL_BAR_TRANSITION = {
  transitionProperty: "height",
  transitionDuration: "260ms",
  transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
} as const;

interface EvalBarProps {
  evalCp: number | null;
  orientation: "white" | "black";
  className?: string;
}

export function EvalBar({ evalCp, orientation, className }: EvalBarProps) {
  const whiteShare = evalToWhiteShare(evalCp);
  const topIsBlack = orientation === "white";
  const topShare = orientation === "white" ? 100 - whiteShare : whiteShare;
  const winnerIsTop = topIsBlack ? (evalCp ?? 0) < 0 : (evalCp ?? 0) >= 0;
  const label = evalCp === null ? "" : formatEvalBar(evalCp);

  return (
    <div
      className={cn(
        "relative min-h-[320px] w-7 overflow-hidden rounded bg-stone-900 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.16)] dark:bg-stone-950",
        className,
      )}
    >
      <div
        className={cn(
          "absolute inset-x-0 top-0 bg-stone-100 text-stone-900 dark:bg-stone-200",
          topIsBlack && "bg-stone-800 text-stone-100 dark:bg-black",
        )}
        style={{ height: `${topShare}%`, ...EVAL_BAR_TRANSITION }}
      >
        {winnerIsTop && label ? (
          <span className="absolute inset-x-0 bottom-1 text-center font-mono font-semibold text-[9px] leading-none tabular-nums">
            <MorphText>{label}</MorphText>
          </span>
        ) : null}
      </div>
      <div
        className={cn(
          "absolute inset-x-0 bottom-0 bg-stone-800 text-stone-100 dark:bg-black",
          topIsBlack && "bg-stone-100 text-stone-900 dark:bg-stone-200",
        )}
        style={{ height: `${100 - topShare}%`, ...EVAL_BAR_TRANSITION }}
      >
        {!winnerIsTop && label ? (
          <span className="absolute inset-x-0 top-1 text-center font-mono font-semibold text-[9px] leading-none tabular-nums">
            <MorphText>{label}</MorphText>
          </span>
        ) : null}
      </div>
    </div>
  );
}

function evalToWhiteShare(evalCp: number | null): number {
  if (evalCp === null) {
    return 50;
  }
  if (parseMateFromCp(evalCp) !== null) {
    return evalCp > 0 ? 96 : 4;
  }
  return 50 + Math.max(-46, Math.min(46, evalCp / 21.7));
}

function formatEvalBar(evalCp: number): string {
  const mate = parseMateFromCp(evalCp);
  if (mate !== null) {
    const n = Math.abs(mate);
    return n === 0 ? "M" : `M${n}`;
  }
  const sign = evalCp >= 0 ? "+" : "";
  return `${sign}${(evalCp / 100).toFixed(1)}`;
}
