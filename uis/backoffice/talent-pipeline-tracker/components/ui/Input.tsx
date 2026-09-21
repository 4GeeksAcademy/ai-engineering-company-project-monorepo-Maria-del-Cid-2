import { type InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label className="text-sm font-medium text-zinc-700">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`rounded-lg border border-zinc-300 px-3 py-2 text-sm placeholder-zinc-400 transition-colors focus:border-nexova-500 focus:outline-none focus:ring-2 focus:ring-nexova-200 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400 ${error ? "border-red-500 focus:border-red-500 focus:ring-red-200" : ""} ${className}`}
          {...props}
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";
