import { type MotionStyle, motion, useReducedMotion } from "framer-motion";
import { type ElementType, type JSX, memo, useMemo } from "react";
import { cn } from "@/lib/utils";

type TextShimmerStyle = MotionStyle & {
  "--spread": string;
  "--base-color": string;
  "--base-gradient-color": string;
};

export type TextShimmerProps = {
  children: string;
  as?: ElementType;
  className?: string;
  duration?: number;
  spread?: number;
  baseColor?: string;
  shimmerColor?: string;
  style?: MotionStyle;
};

function TextShimmerComponent({
  children,
  as: Component = "p",
  className,
  duration = 2,
  spread = 2,
  baseColor,
  shimmerColor,
  style,
}: TextShimmerProps) {
  const prefersReducedMotion = useReducedMotion();
  const MotionComponent = useMemo(
    () => motion.create(Component as keyof JSX.IntrinsicElements),
    [Component],
  );
  const dynamicSpread = useMemo(() => children.length * spread, [children, spread]);
  const animationProps = prefersReducedMotion
    ? { initial: false as const }
    : {
        animate: { backgroundPosition: "0% center" },
        initial: { backgroundPosition: "100% center" },
        transition: {
          repeat: Infinity,
          duration,
          ease: "linear" as const,
        },
      };

  return (
    <MotionComponent
      {...animationProps}
      className={cn(
        "relative inline-block bg-size-[250%_100%,auto] bg-clip-text",
        "[-webkit-text-fill-color:transparent]",
        "[background-repeat:no-repeat,padding-box] [--bg:linear-gradient(90deg,#0000_calc(50%-var(--spread)),var(--base-gradient-color),#0000_calc(50%+var(--spread)))]",
        className,
      )}
      style={
        {
          ...style,
          "--spread": `${dynamicSpread}px`,
          "--base-color": baseColor ?? "color-mix(in oklab, currentColor 55%, transparent)",
          "--base-gradient-color": shimmerColor ?? "currentColor",
          backgroundImage: "var(--bg), linear-gradient(var(--base-color), var(--base-color))",
        } as TextShimmerStyle
      }
    >
      {children}
    </MotionComponent>
  );
}

export const TextShimmer = memo(TextShimmerComponent);
