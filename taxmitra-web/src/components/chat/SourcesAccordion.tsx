"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { SourceItem } from "@/types";
import { SourcePill } from "@/components/primitives/SourcePill";
import { cn } from "@/lib/utils";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { DURATION, EASING } from "@/lib/motion";

interface SourcesAccordionProps {
  sources:      SourceItem[];
  defaultOpen?: boolean;
  className?:   string;
}

export function SourcesAccordion({ sources, defaultOpen = false, className }: SourcesAccordionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const { duration } = useMotionSafe();

  if (!sources.length) return null;

  return (
    <div className={cn("mt-3", className)}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="sources-list"
        className={cn(
          "flex w-full items-center gap-2 text-sm font-medium",
          "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
          "transition-colors duration-fast rounded-lg py-1 px-2 -ml-2",
          "focus-visible:outline-2 focus-visible:outline-[var(--color-border-focus)]"
        )}
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-saffron/15 text-xs font-mono text-saffron">
          {sources.length}
        </span>
        <span>Sources</span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: duration(DURATION.fast), ease: EASING.enter }}
        >
          <ChevronDown className="w-4 h-4" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.nav
            id="sources-list"
            aria-label="Sources for this answer"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: duration(DURATION.base), ease: EASING.enter }}
            className="overflow-hidden"
          >
            <div className="mt-2 flex flex-col gap-2">
              {sources.map((src, i) => (
                <SourcePill key={`${src.filename}-${src.section_heading}-${i}`} source={src} index={i + 1} />
              ))}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </div>
  );
}
