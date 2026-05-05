import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex min-h-7 items-center rounded-md px-2.5 py-1 text-xs font-medium tabular-nums tracking-normal",
  {
    variants: {
      tone: {
        neutral: "bg-stone-200 text-stone-800",
        green: "bg-emerald-100 text-emerald-900",
        amber: "bg-amber-100 text-amber-900",
        red: "bg-red-100 text-red-900",
        blue: "bg-sky-100 text-sky-900",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
