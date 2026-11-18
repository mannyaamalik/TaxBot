"use client";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp } from "lucide-react";
import { Spinner } from "@/components/primitives/Spinner";
import { cn } from "@/lib/utils";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { DURATION } from "@/lib/motion";

interface SendButtonProps {
  loading:   boolean;
  disabled:  boolean;
  onClick:   () => void;
  className?: string;
}

export function SendButton({ loading, disabled, onClick, className }: SendButtonProps) {
  const { duration } = useMotionSafe();

  return (
    <motion.button
      onClick={onClick}
      disabled={disabled || loading}
      aria-label={loading ? "Sending…" : "Send question"}
      aria-busy={loading}
      whileTap={{ scale: 0.92 }}
      transition={{ duration: duration(DURATION.fast) }}
      className={cn(
        "relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
        "font-medium text-[var(--color-text-inverse)] shadow-card",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        "focus-visible:outline-2 focus-visible:outline-[var(--color-border-focus)]",
        "overflow-hidden",
        className
      )}
      style={
        disabled && !loading
          ? { background: "rgba(255,255,255,0.1)" }
          : { background: "var(--gradient-accent)" }
      }
    >
      <AnimatePresence mode="wait" initial={false}>
        {loading ? (
          <motion.span
            key="spinner"
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            transition={{ duration: duration(DURATION.base) }}
          >
            <Spinner size="sm" className="text-[var(--color-text-inverse)]" />
          </motion.span>
        ) : (
          <motion.span
            key="arrow"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: duration(DURATION.base) }}
          >
            <ArrowUp className="w-5 h-5" />
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
