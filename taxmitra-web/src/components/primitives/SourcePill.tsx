import { cn } from "@/lib/utils";
import { SourceItem } from "@/types";
import { FileText } from "lucide-react";

interface SourcePillProps {
  source:    SourceItem;
  index:     number;
  className?: string;
}

export function SourcePill({ source, index, className }: SourcePillProps) {
  return (
    <div
      className={cn(
        "gradient-border flex items-start gap-2 rounded-xl p-3 text-sm",
        "bg-white/[0.03] hover:bg-white/[0.06] transition-colors duration-fast",
        className
      )}
    >
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-saffron/15 text-xs font-mono font-medium text-saffron">
        {index}
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-1 font-medium text-[var(--color-text-primary)] truncate">
          <FileText className="w-3 h-3 shrink-0 opacity-60" />
          <span className="truncate">{source.doc_title}</span>
        </div>
        {source.section_heading && (
          <div className="mt-0.5 font-mono text-xs text-[var(--color-text-secondary)] truncate">
            {source.section_heading}
          </div>
        )}
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--color-text-muted)]">
          {source.page_number > 0 && <span>Page {source.page_number}</span>}
          {source.assessment_year !== "unknown" && (
            <span>AY {source.assessment_year}</span>
          )}
          <span className="truncate opacity-60">{source.filename}</span>
        </div>
      </div>
    </div>
  );
}
