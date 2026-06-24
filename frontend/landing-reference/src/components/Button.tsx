import { cn } from '../utils/cn';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: ReactNode;
}

export function Button({ variant = 'primary', className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-all duration-200',
        variant === 'primary' && 'bg-brand-500 text-white hover:bg-brand-600 shadow-lg shadow-brand-500/25',
        variant === 'secondary' && 'border border-border bg-surface-card text-zinc-200 hover:bg-zinc-800',
        variant === 'ghost' && 'text-zinc-400 hover:text-white hover:bg-white/5',
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
