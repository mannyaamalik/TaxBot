"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, Building, Receipt, BarChart3, PiggyBank, FileText } from "lucide-react";
import { Category, SuggestedQuestion } from "@/types";
import { GlassCard } from "@/components/primitives/GlassCard";
import { cn } from "@/lib/utils";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { useMotionSafe } from "@/hooks/useReducedMotion";

const CATEGORIES: { id: Category; label: string; labelHi: string }[] = [
  { id: "all",          label: "All",           labelHi: "सभी" },
  { id: "income-tax",   label: "Income Tax",    labelHi: "आयकर" },
  { id: "gst",          label: "GST",           labelHi: "जीएसटी" },
  { id: "tds",          label: "TDS",           labelHi: "टीडीएस" },
  { id: "capital-gains",label: "Capital Gains", labelHi: "पूंजीगत लाभ" },
  { id: "deductions",   label: "Deductions",    labelHi: "कटौती" },
  { id: "itr-filing",   label: "ITR Filing",    labelHi: "आईटीआर फाइलिंग" },
];

const SUGGESTIONS: SuggestedQuestion[] = [
  { id: "1", text: "Old vs new regime: which saves more tax?",        category: "income-tax",    icon: "TrendingUp" },
  { id: "2", text: "How to file ITR-1 step by step?",                  category: "itr-filing",    icon: "FileText"  },
  { id: "3", text: "What is the GST registration threshold?",          category: "gst",           icon: "Building"  },
  { id: "4", text: "Section 80C investments — complete list",           category: "deductions",    icon: "PiggyBank" },
  { id: "5", text: "LTCG tax on equity shares: rate and exemption",     category: "capital-gains", icon: "BarChart3" },
  { id: "6", text: "How to avoid TDS on bank interest (Form 15G/15H)?", category: "tds",           icon: "Receipt"   },
  { id: "7", text: "What are the income tax slabs for AY 2024-25?",     category: "income-tax",    icon: "TrendingUp"},
  { id: "8", text: "GSTR-3B due date and late fee",                     category: "gst",           icon: "Building"  },
  { id: "9", text: "Home loan interest deduction under Section 24",     category: "deductions",    icon: "PiggyBank" },
  { id:"10", text: "Which ITR form for freelance income?",              category: "itr-filing",    icon: "FileText"  },
  { id:"11", text: "TDS rate on contractor payments under 194C",        category: "tds",           icon: "Receipt"   },
  { id:"12", text: "How is indexation applied to property sale?",       category: "capital-gains", icon: "BarChart3" },
];

const ICON_MAP: Record<string, React.ElementType> = {
  TrendingUp, Building, Receipt, BarChart3, PiggyBank, FileText,
};

interface SuggestedQuestionsProps {
  onSelect:  (q: string) => void;
  language?: "en" | "hi";
  className?: string;
}

export function SuggestedQuestions({ onSelect, language = "en", className }: SuggestedQuestionsProps) {
  const [active, setActive] = useState<Category>("all");
  const { reduced } = useMotionSafe();

  const filtered = active === "all" ? SUGGESTIONS : SUGGESTIONS.filter((q) => q.category === active);

  return (
    <div className={className}>
      {/* Category chips */}
      <div className="flex flex-wrap gap-2 mb-6" role="group" aria-label="Filter by category">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActive(cat.id)}
            aria-pressed={active === cat.id}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-fast",
              "border focus-visible:outline-2 focus-visible:outline-[var(--color-border-focus)]",
              active === cat.id
                ? "border-saffron bg-saffron/10 text-saffron"
                : "border-white/[0.08] text-[var(--color-text-secondary)] hover:border-white/[0.15] hover:text-[var(--color-text-primary)]"
            )}
          >
            {language === "hi" ? cat.labelHi : cat.label}
          </button>
        ))}
      </div>

      {/* Question grid */}
      <motion.div
        key={active}
        variants={reduced ? {} : staggerContainer(0.05)}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
      >
        {filtered.map((q) => {
          const Icon = ICON_MAP[q.icon] ?? FileText;
          return (
            <motion.div
              key={q.id}
              variants={reduced ? {} : fadeUp}
            >
              <GlassCard
                hover
                padding="sm"
                onClick={() => onSelect(q.text)}
                className="cursor-pointer select-none active:scale-[0.98] transition-transform duration-fast"
                role="button"
                tabIndex={0}
                onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") onSelect(q.text); }}
                aria-label={`Ask: ${q.text}`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-saffron/10">
                    <Icon className="w-4 h-4 text-saffron" />
                  </div>
                  <p className="text-sm leading-snug text-[var(--color-text-primary)]">{q.text}</p>
                </div>
              </GlassCard>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
