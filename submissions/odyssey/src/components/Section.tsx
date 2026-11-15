import React from 'react';

interface SectionProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode;
  divider?: boolean;
  spacing?: 'none' | 'sm' | 'md' | 'lg';
}

export default function Section({
  children,
  divider = false,
  spacing = 'md',
  className = '',
  ...props
}: SectionProps) {
  const spacingStyles = {
    none: '',
    sm: 'py-6 md:py-8',
    md: 'py-12 md:py-16',
    lg: 'py-20 md:py-24',
  };

  return (
    <section
      className={`w-full ${spacingStyles[spacing]} ${
        divider ? 'border-b border-brand-border' : ''
      } ${className}`}
      {...props}
    >
      {children}
    </section>
  );
}
