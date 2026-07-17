import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type Variant = "primary" | "secondary" | "ghost" | "danger";
export type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
}

export const BUTTON_BASE =
  "inline-flex items-center justify-center rounded-btn font-medium whitespace-nowrap transition-colors duration-hover disabled:opacity-50 disabled:pointer-events-none";

export const VARIANT: Record<Variant, string> = {
  primary: "bg-steel text-white hover:bg-steel-hover",
  secondary: "bg-surface text-ink border border-hairline-strong hover:bg-sunken",
  ghost: "bg-transparent text-ink-2 hover:bg-sunken hover:text-ink",
  danger: "bg-critical text-white hover:brightness-95",
};

// §6.7. One primary per view.
export const SIZE: Record<Size, string> = {
  sm: "h-7 px-3 text-sm gap-1.5",
  md: "h-8 px-3 text-body gap-2",
  lg: "h-10 px-4 text-body gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, block, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center rounded-btn font-medium whitespace-nowrap",
        "transition-colors duration-hover disabled:opacity-50 disabled:pointer-events-none",
        VARIANT[variant],
        SIZE[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
});

/** Stage tick, not decoration: waiting is honest work here (§10.9). */
function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
      <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
