import { cn } from "@/lib/utils";

interface TaxMitraLogoProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  showTagline?: boolean;
}

export function TaxMitraLogo({ size = "md", className, showTagline }: TaxMitraLogoProps) {
  const sizeMap = {
    sm: { text: "text-lg",  mark: "w-6 h-6" },
    md: { text: "text-2xl", mark: "w-8 h-8" },
    lg: { text: "text-3xl", mark: "w-10 h-10" },
  };
  const s = sizeMap[size];

  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <div className="flex items-center gap-2">
        {/* Logo mark: stylised ₹ with gradient */}
        <div
          className={cn("flex items-center justify-center rounded-full font-mono font-bold text-[var(--color-text-inverse)]", s.mark)}
          style={{ background: "var(--gradient-accent)" }}
          aria-hidden="true"
        >
          ₹
        </div>
        {/* Wordmark */}
        <span className={cn("font-bold tracking-tight", s.text)}>
          <span className="gradient-text">Tax</span>
          <span className="text-[var(--color-text-primary)]">Mitra</span>
        </span>
      </div>
      {showTagline && (
        <p className="text-xs text-[var(--color-text-muted)] pl-10">
          Indian Income Tax &amp; GST Assistant
        </p>
      )}
    </div>
  );
}
