import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'text';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-brand transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent-secondary focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none cursor-pointer';

  const variants = {
    primary: 'bg-brand-accent-secondary text-white shadow-sm hover:bg-[#a34f2d] active:scale-[0.98]',
    secondary: 'bg-brand-accent text-white shadow-sm hover:bg-[#4f5c43] active:scale-[0.98]',
    outline: 'border border-brand-border text-brand-text bg-white hover:bg-brand-muted hover:border-brand-border/80 active:scale-[0.98]',
    text: 'text-brand-text hover:bg-brand-muted active:scale-[0.98]',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
