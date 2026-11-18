import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a number in Indian notation: 1,50,000 */
export function formatIndian(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

/** Format a rupee amount: ₹1,50,000 */
export function formatRupee(value: number): string {
  return `₹${formatIndian(value)}`;
}

/** Generate a UUID v4 */
export function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** Detect if answer is a clarification question */
export function isClarification(answer: string): boolean {
  return /^To give you the most accurate answer/i.test(answer.trim());
}

/** Detect if answer is out-of-scope refusal */
export function isOutOfScope(answer: string): boolean {
  return /I can only answer questions about Indian Income Tax/i.test(answer);
}

/** Detect if answer is "not found" */
export function isNotFound(answer: string): boolean {
  return /I could not find an answer to this question/i.test(answer);
}

/** Truncate text to n chars with ellipsis */
export function truncate(text: string, n: number): string {
  return text.length <= n ? text : text.slice(0, n - 1) + "…";
}
