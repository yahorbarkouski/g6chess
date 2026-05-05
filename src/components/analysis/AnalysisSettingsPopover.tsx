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
  buttonClassName?: string;
  className?: string;
  placement?: "side" | "bottom-start";
  popoverClassName?: string;
}

const MARKER_MODES: ReadonlyArray<{ value: MarkerDisplayMode; label: string }> = [
  { value: "critical", label: "Critical" },
  { value: "all", label: "All" },
];

const ROW_LABEL_CLASS = "text-[12px] font-medium text-stone-700 dark:text-stone-300";

export function AnalysisSettingsPopover({
  arrowCount,
  buttonClassName,
  className,
  onArrowCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  placement = "side",
  popoverClassName,
}: AnalysisSettingsPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverId = useId();
  const prefersReducedMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const opensBelow = placement === "bottom-start";

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
    <div className={cn("relative", className)} ref={rootRef}>
      <AnimatedIconButton
        aria-controls={popoverId}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Board settings"
        active={open}
        className={cn("size-6", buttonClassName)}
        icon={<Settings2 className="size-3.5" />}
        onClick={() => setOpen((value) => !value)}
        title="Board settings"
      />
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
            className={cn(
              "absolute z-50 flex w-56 flex-col rounded-lg border border-stone-200 bg-white p-3 text-sm text-stone-900 shadow-[0_18px_45px_rgba(28,25,23,0.18),0_1px_0_rgba(255,255,255,0.8)_inset] outline-none dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100 dark:shadow-[0_18px_45px_rgba(0,0,0,0.45)]",
              opensBelow
                ? "top-[calc(100%+0.5rem)] left-0 origin-top-left"
                : "top-0 left-[calc(100%+0.5rem)] origin-left",
              popoverClassName,
            )}
            exit={{
              opacity: 0,
              scale: 0.96,
              x: prefersReducedMotion || opensBelow ? 0 : -4,
              y: prefersReducedMotion || !opensBelow ? 0 : -4,
            }}
            id={popoverId}
            initial={
              prefersReducedMotion
                ? false
                : { opacity: 0, scale: 0.96, x: opensBelow ? 0 : -4, y: opensBelow ? -4 : 0 }
            }
            role="dialog"
            transition={
              prefersReducedMotion ? { duration: 0 } : { duration: 0.16, ease: [0.22, 1, 0.36, 1] }
            }
          >
            <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-3">
              <label className={ROW_LABEL_CLASS} htmlFor={`${popoverId}-arrows`}>
                Best line arrows
              </label>
              <div className="flex items-center gap-2">
                <input
                  className="h-1 min-w-0 flex-1 cursor-pointer appearance-none rounded-full bg-stone-200 accent-stone-900 dark:bg-stone-700 dark:accent-stone-100"
                  id={`${popoverId}-arrows`}
                  max={3}
                  min={0}
                  onChange={(event) => onArrowCountChange(Number(event.target.value))}
                  step={1}
                  type="range"
                  value={arrowCount}
                />
                <span className="w-2 text-right font-mono text-[11px] text-stone-500 tabular-nums dark:text-stone-400">
                  {arrowCount}
                </span>
              </div>

              <span className={ROW_LABEL_CLASS}>
                <a
                  className="underline decoration-pink-400 decoration-1 underline-offset-[3px] hover:text-stone-950 dark:hover:text-stone-50"
                  href="https://www.maiachess.com/"
                  rel="noreferrer"
                  target="_blank"
                >
                  Maia
                </a>{" "}
                human move
              </span>
              <div className="flex justify-end">
                <Switch
                  checked={showMaiaArrow}
                  label="Show Maia arrow"
                  onChange={onShowMaiaArrowChange}
                  prefersReducedMotion={prefersReducedMotion ?? false}
                />
              </div>

              <span className={ROW_LABEL_CLASS}>Move markers</span>
              <div className="flex items-center justify-end gap-1">
                {MARKER_MODES.map(({ value, label }) => {
                  const active = markerDisplayMode === value;
                  return (
                    <button
                      aria-pressed={active}
                      className={cn(
                        "h-6 cursor-pointer rounded px-2 text-[11px] font-medium transition-colors",
                        active
                          ? "bg-stone-900 text-stone-50 dark:bg-stone-100 dark:text-stone-900"
                          : "text-stone-400 hover:text-stone-700 dark:text-stone-500 dark:hover:text-stone-300",
                      )}
                      key={value}
                      onClick={() => onMarkerDisplayModeChange(value)}
                      type="button"
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

interface SwitchProps {
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
  prefersReducedMotion: boolean;
}

function Switch({ checked, label, onChange, prefersReducedMotion }: SwitchProps) {
  return (
    <button
      aria-checked={checked}
      aria-label={label}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors after:absolute after:-inset-2",
        checked
          ? "bg-stone-900 dark:bg-stone-100"
          : "bg-stone-200 hover:bg-stone-300 dark:bg-stone-700 dark:hover:bg-stone-600",
      )}
      onClick={() => onChange(!checked)}
      role="switch"
      type="button"
    >
      <motion.span
        animate={{ x: checked ? 18 : 2 }}
        className="block size-4 rounded-full bg-white shadow-[0_1px_2px_rgba(28,25,23,0.2)] dark:bg-stone-950"
        transition={
          prefersReducedMotion ? { duration: 0 } : { type: "spring", duration: 0.24, bounce: 0 }
        }
      />
    </button>
  );
}
