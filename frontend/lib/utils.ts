import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatTimeRemaining(expiryString: string): { text: string; isUrgent: boolean } {
  try {
    const expiry = new Date(expiryString).getTime();
    const now = Date.now();
    const diffMs = expiry - now;

    if (diffMs <= 0) {
      return { text: "Expired", isUrgent: true };
    }

    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffHours < 2) {
      return { text: `${diffMinutes}m remaining`, isUrgent: true };
    }
    if (diffHours < 24) {
      return { text: `${diffHours}h ${diffMinutes}m remaining`, isUrgent: false };
    }
    const diffDays = Math.floor(diffHours / 24);
    return { text: `${diffDays}d remaining`, isUrgent: false };
  } catch {
    return { text: "Unknown", isUrgent: false };
  }
}
