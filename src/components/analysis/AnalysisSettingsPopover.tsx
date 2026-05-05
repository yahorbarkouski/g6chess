import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Settings2 } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "../../lib/utils";
import { AnimatedIconButton } from "../ui/animated-icon-button";
import type { MarkerDisplayMode } from "./MoveList";

interface AnalysisSettingsPopoverProps {
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
}

export function AnalysisSettingsPopover({
  arrowCount,
  onArrowCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
}: AnalysisSettingsPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverId = useId();
  const prefersReducedMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={rootRef}>
      <AnimatedIconButton
        aria-controls={popoverId}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Board settings"
        active={open}
        className="size-6"
        icon={<Settings2 className="size-3.5" />}
        onClick={() => setOpen((value) => !value)}
        title="Board settings"
      />
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            animate={{ opacity: 1, scale: 1, x: 0 }}
            className="absolute top-0 left-[calc(100%+0.5rem)] z-50 flex w-52 origin-left flex-col gap-2.5 rounded-lg bg-white p-2.5 text-sm text-stone-900 shadow-md ring-1 ring-stone-950/10 outline-none dark:bg-stone-900 dark:text-stone-100 dark:ring-white/10"
            exit={{ opacity: 0, scale: 0.96, x: prefersReducedMotion ? 0 : -4 }}
            id={popoverId}
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.96, x: -4 }}
            role="dialog"
            transition={
              prefersReducedMotion ? { duration: 0 } : { duration: 0.16, ease: [0.22, 1, 0.36, 1] }
            }
          >
            <div className="space-y-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    className="text-xs font-medium text-stone-700 dark:text-stone-300"
                    htmlFor={`${popoverId}-arrows`}
                  >
                    Best line arrows
                  </label>
                  <span className="text-xs text-stone-400 tabular-nums dark:text-stone-500">
                    {arrowCount}
                  </span>
                </div>
                <input
                  className="h-1 w-full cursor-pointer appearance-none rounded-full bg-stone-200 accent-stone-950 dark:bg-stone-700 dark:accent-stone-100"
                  id={`${popoverId}-arrows`}
                  max={3}
                  min={0}
                  onChange={(event) => onArrowCountChange(Number(event.target.value))}
                  step={1}
                  type="range"
                  value={arrowCount}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-stone-700 dark:text-stone-300">
                  Natural move arrow
                </span>
                <button
                  aria-checked={showMaiaArrow}
                  className={cn(
                    "relative inline-flex h-[14px] w-6 shrink-0 items-center rounded-full border border-transparent transition-colors after:absolute after:-inset-x-3 after:-inset-y-2",
                    showMaiaArrow
                      ? "bg-stone-900 dark:bg-stone-100"
                      : "bg-stone-200 dark:bg-stone-700",
                  )}
                  onClick={() => onShowMaiaArrowChange(!showMaiaArrow)}
                  role="switch"
                  type="button"
                >
                  <motion.span
                    animate={{ x: showMaiaArrow ? 10 : 0 }}
                    className="block size-3 rounded-full bg-white shadow-sm dark:bg-stone-950"
                    transition={
                      prefersReducedMotion
                        ? { duration: 0 }
                        : { type: "spring", duration: 0.24, bounce: 0 }
                    }
                  />
                </button>
              </div>
              <div className="space-y-2">
                <span className="text-xs font-medium text-stone-700 dark:text-stone-300">
                  Move markers
                </span>
                <div className="grid grid-cols-2 rounded bg-stone-100 p-0.5 dark:bg-stone-800">
                  {(["critical", "all"] as const).map((mode) => (
                    <button
                      className={cn(
                        "h-7 rounded text-xs font-medium transition-colors",
                        markerDisplayMode === mode
                          ? "bg-white text-stone-900 shadow-sm dark:bg-stone-700 dark:text-stone-100"
                          : "text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200",
                      )}
                      key={mode}
                      onClick={() => onMarkerDisplayModeChange(mode)}
                      type="button"
                    >
                      {mode === "critical" ? "Critical" : "All"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
