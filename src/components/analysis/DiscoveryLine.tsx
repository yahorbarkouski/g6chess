import { X } from "lucide-react";
import type { DiscoveryState } from "../../hooks/useAnalysisBoard";
import { formatEval } from "../../lib/chess";
import { cn } from "../../lib/utils";
import { MorphText } from "../ui/morph-text";

function formatDiscoveryMoves(rootFen: string, moves: string[]) {
  const parts = rootFen.split(" ");
  let turn: "w" | "b" = parts[1] === "b" ? "b" : "w";
  let moveNum = Number.parseInt(parts[5] ?? "1", 10);
  if (!Number.isFinite(moveNum) || moveNum < 1) {
    moveNum = 1;
  }

  return moves.map((san, index) => {
    let prefix = "";
    if (turn === "w") {
      prefix = `${moveNum}. `;
    } else if (index === 0) {
      prefix = `${moveNum}... `;
    }
    if (turn === "w") {
      turn = "b";
    } else {
      turn = "w";
      moveNum += 1;
    }
    return { prefix, san };
  });
}

export function DiscoveryLineBar({
  discovery,
  onStepClick,
  onExit,
}: {
  discovery: DiscoveryState;
  onStepClick: (step: number) => void;
  onExit: () => void;
}) {
  const formattedMoves = formatDiscoveryMoves(discovery.rootFen, discovery.moves);

  return (
    <div className="mx-auto mt-3 flex w-full max-w-[820px] items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2 dark:border-amber-900/60 dark:bg-amber-950/40">
      <span className="shrink-0 text-[11px] font-medium uppercase tracking-wider text-amber-600 dark:text-amber-400">
        Analysis
      </span>
      <div className="scrollbar-hide flex min-w-0 flex-wrap items-center gap-1 overflow-x-auto">
        {formattedMoves.length > 0 ? (
          formattedMoves.map(({ prefix, san }, index) => {
            const isActive = index === discovery.currentStep - 1;
            const moveKey = discovery.moves.slice(0, index + 1).join(" ");
            return (
              <button
                className={cn(
                  "rounded border px-1.5 py-0.5 font-mono text-sm transition-colors",
                  isActive
                    ? "border-amber-400/60 bg-amber-200/60 text-amber-900 dark:border-amber-500/40 dark:bg-amber-800/40 dark:text-amber-100"
                    : "border-transparent text-amber-700 hover:bg-amber-100 dark:text-amber-300 dark:hover:bg-amber-900/30",
                )}
                key={moveKey}
                onClick={() => onStepClick(index + 1)}
                type="button"
              >
                {prefix}
                {san}
              </button>
            );
          })
        ) : (
          <span className="text-sm text-amber-700 dark:text-amber-300">
            Play a move on the board
          </span>
        )}
      </div>
      <button
        aria-label="Exit analysis"
        className="ml-auto shrink-0 text-amber-500 transition-colors hover:text-amber-700 dark:hover:text-amber-300"
        onClick={onExit}
        title="Exit analysis"
        type="button"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

export function DiscoveryLineSidebar({
  discovery,
  evalCp,
  onStepClick,
}: {
  discovery: DiscoveryState;
  evalCp: number | null;
  onStepClick: (step: number) => void;
}) {
  const formattedMoves = formatDiscoveryMoves(discovery.rootFen, discovery.moves);

  return (
    <div className="rounded bg-amber-50/80 px-2 py-1.5 dark:bg-amber-950/40">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600 dark:text-amber-400">
          Custom
        </span>
        <span className={cn("shrink-0 font-mono text-[11px] tabular-nums", evalColor(evalCp))}>
          <MorphText>{evalCp !== null ? formatEval(evalCp) : "..."}</MorphText>
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        {formattedMoves.map(({ prefix, san }, index) => {
          const isActive = index === discovery.currentStep - 1;
          const moveKey = discovery.moves.slice(0, index + 1).join(" ");
          return (
            <button
              className={cn(
                "inline-flex max-w-full items-center rounded border px-1 py-0.5 transition-colors",
                isActive
                  ? "border-amber-400/50 bg-amber-200/60 text-amber-900 dark:border-amber-500/40 dark:bg-amber-800/40 dark:text-amber-100"
                  : "border-amber-200 bg-white/60 hover:border-amber-300 dark:border-amber-800 dark:bg-amber-950/60 dark:hover:border-amber-700",
              )}
              key={moveKey}
              onClick={() => onStepClick(index + 1)}
              type="button"
            >
              <span className="truncate font-mono text-[12px] text-amber-700 dark:text-amber-300">
                {prefix}
                {san}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function evalColor(evalCp: number | null): string {
  if (evalCp === null) {
    return "text-stone-500 dark:text-stone-400";
  }
  if (evalCp >= 50) {
    return "text-emerald-600 dark:text-emerald-400";
  }
  if (evalCp <= -50) {
    return "text-rose-500 dark:text-rose-400";
  }
  return "text-stone-500 dark:text-stone-400";
}
