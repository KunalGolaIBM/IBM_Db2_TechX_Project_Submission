// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  if (dateStr === "Always open" || dateStr === "Ongoing") return dateStr;
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function getDaysLeft(dateStr: string): number | null {
  if (dateStr === "Always open" || dateStr === "Ongoing") return null;
  const deadline = new Date(dateStr);
  const now = new Date();
  const diff = deadline.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function getDeadlineLabel(dateStr: string): string {
  const days = getDaysLeft(dateStr);
  if (days === null) return "Always open";
  if (days < 0) return "Open";
  if (days === 0) return "Closes today";
  if (days === 1) return "1 day left";
  if (days <= 7) return `${days} days left`;
  return `Due ${formatDate(dateStr)}`;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "open": return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
    case "closed": return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
    default: return "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";
  }
}

export function getDifficultyColor(difficulty: string): string {
  switch (difficulty) {
    case "Beginner": return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
    case "Intermediate": return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
    case "Advanced":
    case "Professional": return "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400";
    case "Associate": return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
    default: return "bg-gray-100 text-gray-600";
  }
}
