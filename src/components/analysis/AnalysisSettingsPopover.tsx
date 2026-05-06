import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpDown, Settings2 } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { triggerHaptic } from "../../lib/haptics";
import { cn } from "../../lib/utils";
import { AnimatedIconButton } from "../ui/animated-icon-button";
import type { MarkerDisplayMode } from "./MoveList";

interface AnalysisSettingsPopoverProps {
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  engineLineCount: number;
  onEngineLineCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  flippedBoard?: boolean;
  onFlipBoard?: () => void;
  buttonClassName?: string;
  iconClassName?: string;
  className?: string;
  placement?: "side" | "bottom-start" | "top-start" | "top-end";
  popoverClassName?: string;
}

const ARROW_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 0, label: "Off" },
  { value: 1, label: "1" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
];

const ENGINE_LINE_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 1, label: "1" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
];

const MAIA_OPTIONS: ReadonlyArray<{ value: boolean; label: string }> = [
  { value: false, label: "Off" },
  { value: true, label: "On" },
];

const MARKER_OPTIONS: ReadonlyArray<{ value: MarkerDisplayMode; label: string }> = [
  { value: "critical", label: "Critical" },
  { value: "all", label: "All" },
];

export function AnalysisSettingsPopover({
  arrowCount,
  buttonClassName,
  className,
  engineLineCount,
  flippedBoard = false,
  iconClassName,
  onArrowCountChange,
  onEngineLineCountChange,
  onFlipBoard,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  placement = "side",
  popoverClassName,
}: AnalysisSettingsPopoverProps) {
  const [open, setOpen] = useState(false);
  const popoverId = useId();
  const prefersReducedMotion = useReducedMotion() ?? false;
  const rootRef = useRef<HTMLDivElement | null>(null);
  const opensBelow = placement === "bottom-start";
  const opensAboveLeft = placement === "top-start";
  const opensAboveRight = placement === "top-end";
  const positionClassName = opensBelow
    ? "top-[calc(100%+0.5rem)] left-0 origin-top-left"
    : opensAboveLeft
      ? "bottom-[calc(100%+0.5rem)] left-0 origin-bottom-left"
      : opensAboveRight
        ? "bottom-[calc(100%+0.5rem)] right-0 origin-bottom-right"
        : "top-0 left-[calc(100%+0.5rem)] origin-left";
  const initialOffset = prefersReducedMotion
    ? { x: 0, y: 0 }
    : opensBelow
      ? { x: 0, y: -4 }
      : opensAboveLeft || opensAboveRight
        ? { x: 0, y: 4 }
        : { x: -4, y: 0 };

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
        icon={<Settings2 className={cn("size-3.5", iconClassName)} />}
        onClick={() => {
          triggerHaptic("selection");
          setOpen((value) => !value);
        }}
        title="Board settings"
      />
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
            className={cn(
              "absolute z-50 w-64 rounded-xl border border-stone-200/80 bg-white p-1 pt-0.5 text-stone-900 shadow-[0_18px_45px_rgba(28,25,23,0.15),0_1px_0_rgba(255,255,255,0.7)_inset] outline-none dark:border-stone-700/70 dark:bg-stone-900 dark:text-stone-100 dark:shadow-[0_18px_45px_rgba(0,0,0,0.5)]",
              positionClassName,
              popoverClassName,
            )}
            exit={{ opacity: 0, scale: 0.96, ...initialOffset }}
            id={popoverId}
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.96, ...initialOffset }}
            role="dialog"
            transition={
              prefersReducedMotion ? { duration: 0 } : { duration: 0.16, ease: [0.22, 1, 0.36, 1] }
            }
          >
            <SectionCaption>Board hints</SectionCaption>
            <SettingsRow label="Engine arrows">
              <SegmentedControl
                ariaLabel="Best line arrows"
                layoutId={`${popoverId}-arrows`}
                options={ARROW_OPTIONS.map((option) => ({
                  key: String(option.value),
                  label: option.label,
                  active: option.value === arrowCount,
                  onSelect: () => onArrowCountChange(option.value),
                }))}
                prefersReducedMotion={prefersReducedMotion}
              />
            </SettingsRow>
            <SettingsRow label="Engine lines">
              <SegmentedControl
                ariaLabel="Shown engine lines"
                layoutId={`${popoverId}-engine-lines`}
                options={ENGINE_LINE_OPTIONS.map((option) => ({
                  key: String(option.value),
                  label: option.label,
                  active: option.value === engineLineCount,
                  onSelect: () => onEngineLineCountChange(option.value),
                }))}
                prefersReducedMotion={prefersReducedMotion}
              />
            </SettingsRow>
            <SettingsRow label="Human move">
              <SegmentedControl
                ariaLabel="Show Maia human move"
                layoutId={`${popoverId}-maia`}
                options={MAIA_OPTIONS.map((option) => ({
                  key: String(option.value),
                  label: option.label,
                  active: option.value === showMaiaArrow,
                  onSelect: () => onShowMaiaArrowChange(option.value),
                }))}
                prefersReducedMotion={prefersReducedMotion}
              />
            </SettingsRow>

            <Divider />

            <SectionCaption>Move list</SectionCaption>
            <SettingsRow label="Move markers">
              <SegmentedControl
                ariaLabel="Move markers"
                layoutId={`${popoverId}-markers`}
                options={MARKER_OPTIONS.map((option) => ({
                  key: option.value,
                  label: option.label,
                  active: option.value === markerDisplayMode,
                  onSelect: () => onMarkerDisplayModeChange(option.value),
                }))}
                prefersReducedMotion={prefersReducedMotion}
              />
            </SettingsRow>

            {onFlipBoard ? (
              <>
                <Divider />
                <button
                  className="flex h-9 w-full cursor-pointer items-center gap-2 rounded-md px-2 text-[12px] text-stone-700 transition-colors hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
                  onClick={onFlipBoard}
                  type="button"
                >
                  <ArrowUpDown
                    className={cn(
                      "size-4 text-stone-500 transition-transform duration-300 ease-out dark:text-stone-400",
                      flippedBoard && "rotate-180",
                    )}
                  />
                  Flip board
                </button>
              </>
            ) : null}

            <PopoverFooter />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function SectionCaption({ children }: { children: ReactNode }) {
  return (
    <div className="px-2 pt-1.5 text-[11px] font-medium text-stone-500 dark:text-stone-500">
      {children}
    </div>
  );
}

function SettingsRow({ children, label }: { children: ReactNode; label: ReactNode }) {
  return (
    <div className="flex h-8 items-center justify-between gap-3 rounded-md px-2">
      <span className="text-[12px] text-stone-700 dark:text-stone-300">{label}</span>
      {children}
    </div>
  );
}

function Divider() {
  return <div className="my-1 h-px bg-stone-200/70 dark:bg-stone-700/60" />;
}

function PopoverFooter() {
  return (
    <div className="mt-1 border-t border-stone-200/70 px-2 pt-2 pb-1 text-[10.5px] text-stone-400 dark:border-stone-700/60 dark:text-stone-500">
      Human-move predictions by{" "}
      <a
        className="text-stone-500 underline decoration-stone-300 decoration-1 underline-offset-[3px] transition-colors hover:text-stone-800 hover:decoration-stone-500 dark:text-stone-400 dark:decoration-stone-600 dark:hover:text-stone-200 dark:hover:decoration-stone-400"
        href="https://www.maiachess.com/"
        rel="noreferrer"
        target="_blank"
      >
        Maia
      </a>
    </div>
  );
}

interface SegmentOption {
  key: string;
  label: string;
  active: boolean;
  onSelect: () => void;
}

interface SegmentedControlProps {
  ariaLabel: string;
  layoutId: string;
  options: ReadonlyArray<SegmentOption>;
  prefersReducedMotion: boolean;
}

function SegmentedControl({
  ariaLabel,
  layoutId,
  options,
  prefersReducedMotion,
}: SegmentedControlProps) {
  return (
    <div className="inline-flex h-7 items-center rounded-[7px] bg-stone-100 p-0.5 dark:bg-stone-800/80">
      {options.map((option) => (
        <button
          aria-label={`${ariaLabel}: ${option.label}`}
          aria-pressed={option.active}
          className={cn(
            "relative inline-flex h-6 min-w-[22px] cursor-pointer items-center justify-center rounded-[5px] px-2 text-[11px] font-medium transition-colors",
            option.active
              ? "text-stone-900 dark:text-stone-50"
              : "text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200",
          )}
          key={option.key}
          onClick={() => {
            if (!option.active) {
              triggerHaptic("selection");
            }
            option.onSelect();
          }}
          type="button"
        >
          {option.active ? (
            <ActiveSegmentBackground layoutId={layoutId} animated={!prefersReducedMotion} />
          ) : null}
          <span className="relative z-10">{option.label}</span>
        </button>
      ))}
    </div>
  );
}

function ActiveSegmentBackground({ animated, layoutId }: { animated: boolean; layoutId: string }) {
  const className =
    "absolute inset-0 rounded-[5px] bg-white shadow-[0_1px_1px_rgba(28,25,23,0.06),0_2px_6px_rgba(28,25,23,0.08)] dark:bg-stone-700 dark:shadow-[0_1px_1px_rgba(0,0,0,0.4)]";
  if (!animated) {
    return <span aria-hidden="true" className={className} />;
  }
  return (
    <motion.span
      aria-hidden="true"
      className={className}
      layoutId={layoutId}
      transition={{ type: "spring", duration: 0.28, bounce: 0.18 }}
    />
  );
}
