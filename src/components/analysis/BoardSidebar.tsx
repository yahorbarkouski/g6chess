import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpDown } from "lucide-react";
import { AnalysisSettingsPopover } from "./AnalysisSettingsPopover";
import { EvalBar } from "./EvalBar";
import type { MarkerDisplayMode } from "./MoveList";

interface BoardSidebarProps {
  evalCp: number | null;
  orientation: "white" | "black";
  flippedBoard: boolean;
  onFlipBoard: () => void;
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  className?: string;
}

export function BoardSidebar({
  evalCp,
  orientation,
  flippedBoard,
  onFlipBoard,
  arrowCount,
  onArrowCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  className,
}: BoardSidebarProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className={className}>
      <AnalysisSettingsPopover
        arrowCount={arrowCount}
        buttonClassName="relative after:absolute after:-inset-2"
        onArrowCountChange={onArrowCountChange}
        onMarkerDisplayModeChange={onMarkerDisplayModeChange}
        onShowMaiaArrowChange={onShowMaiaArrowChange}
        markerDisplayMode={markerDisplayMode}
        showMaiaArrow={showMaiaArrow}
      />
      <EvalBar evalCp={evalCp} orientation={orientation} className="flex-1" />
      <button
        aria-label="Flip board"
        className="relative flex size-6 cursor-pointer items-center justify-center rounded-full text-stone-400 transition-[background-color,color,transform] after:absolute after:-inset-2 hover:bg-stone-100/70 hover:text-stone-700 active:scale-[0.96] dark:text-stone-500 dark:hover:bg-stone-800/70 dark:hover:text-stone-300"
        onClick={onFlipBoard}
        title="Flip board"
        type="button"
      >
        <motion.span
          animate={{ rotate: flippedBoard ? 180 : 0 }}
          className="flex items-center justify-center"
          transition={
            prefersReducedMotion ? { duration: 0 } : { type: "spring", duration: 0.4, bounce: 0.15 }
          }
        >
          <ArrowUpDown className="size-3.5" />
        </motion.span>
      </button>
    </div>
  );
}
