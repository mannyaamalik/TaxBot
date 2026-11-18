import { cn } from "@/lib/utils";
import { formatIndian } from "@/lib/utils";

interface MonoAmountProps {
  value:     number;
  currency?: "₹" | "%";
  className?: string;
}

export function MonoAmount({ value, currency = "₹", className }: MonoAmountProps) {
  const formatted = currency === "₹"
    ? `₹${formatIndian(value)}`
    : `${formatIndian(value)}%`;
  return (
    <span className={cn("font-mono", className)}>
      {formatted}
    </span>
  );
}
