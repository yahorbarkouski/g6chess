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
    <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center gap-2 p-2 pr-0">
      <div />
      <div className="flex items-center gap-2">
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
      className="flex h-14 min-w-14 cursor-pointer items-center justify-center rounded-xl border border-stone-200 bg-white/60 px-0 text-stone-400 backdrop-blur-sm transition-[background-color,border-color,color,transform] hover:bg-stone-100 hover:text-stone-900 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-500 dark:hover:bg-stone-800 dark:hover:text-stone-100"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}
