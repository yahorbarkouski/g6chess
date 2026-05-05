import { AnimatePresence, motion } from "framer-motion";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "../../lib/utils";

const ICON_TRANSITION = {
  type: "spring" as const,
  duration: 0.3,
  bounce: 0,
};

interface AnimatedIconButtonProps extends Omit<ComponentProps<"button">, "children" | "onChange"> {
  active?: boolean;
  activeIcon?: ReactNode;
  icon: ReactNode;
  onChange?: (active: boolean) => void;
}

export function AnimatedIconButton({
  active = false,
  activeIcon,
  className,
  icon,
  onChange,
  onClick,
  type = "button",
  ...props
}: AnimatedIconButtonProps) {
  return (
    <button
      className={cn(
        "flex size-8 cursor-pointer items-center justify-center overflow-hidden rounded-full text-stone-400 transition-[background-color,color,transform] hover:bg-stone-100/70 hover:text-stone-700 active:scale-[0.96] dark:text-stone-500 dark:hover:bg-stone-800/70 dark:hover:text-stone-300",
        active &&
          "bg-stone-200 text-stone-800 hover:bg-stone-200 hover:text-stone-900 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-800 dark:hover:text-stone-100",
        className,
      )}
      onClick={(event) => {
        onChange?.(!active);
        onClick?.(event);
      }}
      type={type}
      {...props}
    >
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          className="flex items-center justify-center"
          exit={{ opacity: 0, scale: 0.25, filter: "blur(4px)" }}
          initial={{ opacity: 0, scale: 0.25, filter: "blur(4px)" }}
          key={active ? "active" : "default"}
          transition={ICON_TRANSITION}
        >
          {active && activeIcon ? activeIcon : icon}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
