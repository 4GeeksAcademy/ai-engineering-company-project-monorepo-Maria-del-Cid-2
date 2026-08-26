import { type TextareaHTMLAttributes, forwardRef } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className = "", ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label className="text-sm font-medium text-zinc-700">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          className={`rounded-lg border border-zinc-300 px-3 py-2 text-sm placeholder-zinc-400 transition-colors focus:border-nexova-500 focus:outline-none focus:ring-2 focus:ring-nexova-200 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400 ${error ? "border-red-500" : ""} ${className}`}
          rows={3}
          {...props}
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";
