import { type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-brand-orange text-brand-white hover:bg-orange-600 active:bg-orange-700 font-bold uppercase tracking-[0.12em]",
  secondary:
    "bg-brand-white text-brand-anthracite border border-brand-lightgray hover:bg-brand-lightgray/50 active:bg-brand-lightgray font-semibold",
  danger:
    "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 font-semibold",
  ghost:
    "bg-transparent text-brand-anthracite/70 hover:text-brand-anthracite hover:bg-brand-lightgray/50 active:bg-brand-lightgray font-medium",
};

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variantStyles[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg
          className="h-4 w-4 animate-spin"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
