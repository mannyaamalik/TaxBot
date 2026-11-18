import { cn } from "@/lib/utils";

interface SectionBadgeProps {
  section:   string;
  className?: string;
}

export function SectionBadge({ section, className }: SectionBadgeProps) {
  return (
    <span
      className={cn(
        "font-mono text-xs px-2 py-0.5 rounded-full",
        "bg-saffron/10 text-saffron border border-saffron/20",
        className
      )}
    >
      {section}
    </span>
  );
}
