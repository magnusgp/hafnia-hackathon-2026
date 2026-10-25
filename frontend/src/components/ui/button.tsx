import type { ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--aw-primary)] text-white hover:brightness-95 px-5 py-3",
        outline:
          "border border-[var(--aw-border)] bg-transparent text-[var(--aw-text)] hover:bg-[var(--aw-surface-subtle)] px-4 py-2",
        ghost:
          "text-[var(--aw-text-secondary)] hover:text-[var(--aw-text)] px-2 py-2",
      },
    },
    defaultVariants: { variant: "default" },
  },
);
export function Button({
  className,
  variant,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>) {
  return (
    <button
      className={twMerge(clsx(buttonVariants({ variant }), className))}
      {...props}
    />
  );
}
