import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-md text-sm font-medium tracking-normal transition-[background-color,box-shadow,color,transform] duration-150 ease-out active:scale-[0.96] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-emerald-800 text-white shadow-sm shadow-emerald-950/20 hover:bg-emerald-900",
        secondary: "bg-stone-200 text-stone-950 hover:bg-stone-300",
        outline:
          "bg-white text-stone-950 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.18)] hover:bg-stone-50",
        ghost: "text-stone-700 hover:bg-stone-200/80 hover:text-stone-950",
      },
      size: {
        sm: "h-10 px-3",
        md: "h-11 px-4",
        icon: "size-10 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      ref={ref}
      type={type}
      {...props}
    />
  ),
);

Button.displayName = "Button";
