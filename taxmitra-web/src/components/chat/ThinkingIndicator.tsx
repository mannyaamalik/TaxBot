"use client";
import { motion } from "framer-motion";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { DURATION } from "@/lib/motion";

export function ThinkingIndicator() {
  const { duration } = useMotionSafe();

  return (
    <div
      role="status"
      aria-label="TaxMitra is thinking"
      className="flex items-center gap-3 px-4 py-3 rounded-2xl glass border border-white/[0.08] shadow-glass w-fit"
    >
      <div className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="w-2 h-2 rounded-full bg-saffron"
            animate={{ scale: [1, 1.4, 1], opacity: [0.4, 1, 0.4] }}
            transition={{
              duration: duration(DURATION.slow * 1.5),
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
      <span className="text-sm text-[var(--color-text-secondary)]">Retrieving sources…</span>
    </div>
  );
}
