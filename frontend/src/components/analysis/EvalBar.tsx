import { parseMateFromCp } from "../../lib/chess";
import { cn } from "../../lib/utils";

const EVAL_BAR_TRANSITION = {
  transitionProperty: "height",
  transitionDuration: "260ms",
  transitionTimingFunction: "cubic-bezier(0.22, 1, 0.36, 1)",
} as const;

const HORIZONTAL_EVAL_BAR_TRANSITION = {
  transitionProperty: "width",
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
            {label}
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
            {label}
          </span>
        ) : null}
      </div>
    </div>
  );
}

interface HorizontalEvalBarProps {
  evalCp: number | null;
  orientation: "white" | "black";
  className?: string;
}

export function HorizontalEvalBar({ evalCp, orientation, className }: HorizontalEvalBarProps) {
  const whiteShare = evalToWhiteShare(evalCp);
  const leftIsBlack = orientation === "black";
  const leftShare = orientation === "white" ? whiteShare : 100 - whiteShare;
  const label = evalCp === null ? "" : formatEvalBar(evalCp);

  return (
    <div
      className={cn(
        "relative h-6 w-full overflow-hidden rounded bg-stone-900 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.16)] dark:bg-stone-950",
        className,
      )}
    >
      <div
        className={cn(
          "absolute inset-y-0 left-0 bg-stone-100 dark:bg-stone-200",
          leftIsBlack && "bg-stone-800 dark:bg-black",
        )}
        style={{ width: `${leftShare}%`, ...HORIZONTAL_EVAL_BAR_TRANSITION }}
      />
      <div
        className={cn(
          "absolute inset-y-0 right-0 bg-stone-800 dark:bg-black",
          leftIsBlack && "bg-stone-100 dark:bg-stone-200",
        )}
        style={{ width: `${100 - leftShare}%`, ...HORIZONTAL_EVAL_BAR_TRANSITION }}
      />
      {label ? (
        <span className="-translate-x-1/2 -translate-y-1/2 absolute top-1/2 left-1/2 z-10 rounded-sm bg-stone-700/85 px-1.5 py-0.5 font-mono text-[10px] font-semibold leading-none text-stone-50 tabular-nums shadow-sm shadow-stone-950/20 backdrop-blur-[1px] dark:bg-stone-800/85 dark:text-stone-100">
          {label}
        </span>
      ) : null}
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
