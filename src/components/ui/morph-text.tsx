import { useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { TextMorph } from "torph/react";

interface MorphTextProps {
  children: ReactNode;
  animate?: boolean;
}

export function MorphText({ children, animate = true }: MorphTextProps) {
  const prefersReducedMotion = useReducedMotion();

  if (!animate || prefersReducedMotion) {
    return <>{children}</>;
  }

  return <TextMorph>{children}</TextMorph>;
}
