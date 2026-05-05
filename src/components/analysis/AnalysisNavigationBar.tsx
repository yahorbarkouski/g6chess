import { ChevronLeft, ChevronRight, CornerUpLeft, SkipBack, SkipForward } from "lucide-react";
import type { ReactNode } from "react";

interface AnalysisNavigationBarProps {
  onGoToStart: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onGoToEnd: () => void;
  onExitPreview: () => void;
  canGoBack: boolean;
  canGoForward: boolean;
  showExitPreview: boolean;
  exitLabel?: string;
}

export function AnalysisNavigationBar({
  onGoToStart,
  onStepBack,
  onStepForward,
  onGoToEnd,
  onExitPreview,
  canGoBack,
  canGoForward,
  showExitPreview,
  exitLabel = "Exit preview",
}: AnalysisNavigationBarProps) {
  return (
    <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center gap-2 p-1.5 sm:p-2 sm:pr-0">
      <div />
      <div className="flex items-center gap-1.5 sm:gap-2">
        <NavButton disabled={!canGoBack} label="Go to start" onClick={onGoToStart}>
          <SkipBack className="size-6" />
        </NavButton>
        <NavButton disabled={!canGoBack} label="Previous move" onClick={onStepBack}>
          <ChevronLeft className="size-6" />
        </NavButton>
        {showExitPreview ? (
          <NavButton label={exitLabel} onClick={onExitPreview}>
            <CornerUpLeft className="size-6" />
          </NavButton>
        ) : null}
        <NavButton disabled={!canGoForward} label="Next move" onClick={onStepForward}>
          <ChevronRight className="size-6" />
        </NavButton>
        <NavButton disabled={!canGoForward} label="Go to end" onClick={onGoToEnd}>
          <SkipForward className="size-6" />
        </NavButton>
      </div>
      <div />
    </div>
  );
}

function NavButton({
  children,
  disabled = false,
  label,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      className="flex h-12 min-w-12 cursor-pointer items-center justify-center rounded-xl border border-stone-200 bg-white/80 px-0 text-stone-600 shadow-sm shadow-stone-950/[0.03] backdrop-blur-sm transition-[background-color,border-color,box-shadow,color,transform] hover:border-stone-300 hover:bg-white hover:text-stone-800 active:scale-[0.96] disabled:pointer-events-none disabled:border-stone-100 disabled:bg-stone-50/60 disabled:text-stone-300 disabled:shadow-none dark:border-stone-800 dark:bg-stone-900/60 dark:text-stone-400 dark:shadow-black/10 dark:hover:border-stone-700 dark:hover:bg-stone-900 dark:hover:text-stone-200 dark:disabled:border-stone-900 dark:disabled:bg-stone-950/30 dark:disabled:text-stone-700 sm:h-14 sm:min-w-14"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}
