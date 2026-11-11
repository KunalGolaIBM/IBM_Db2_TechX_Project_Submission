import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, id, disabled, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id || generatedId;

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-slate-700"
          >
            {label}
          </label>
        )}
        <input
          id={inputId}
          ref={ref}
          disabled={disabled}
          className={cn(
            'flex h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500',
            error && 'border-rose-500 focus:ring-rose-500',
            className
          )}
          {...props}
        />
        {helperText && !error && (
          <p className="text-xs text-slate-500">{helperText}</p>
        )}
        {error && (
          <p className="text-xs font-medium text-rose-600">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
