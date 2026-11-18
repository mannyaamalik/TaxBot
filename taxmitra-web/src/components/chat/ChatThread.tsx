"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { cn } from "@/lib/utils";
import { fadeUp } from "@/lib/motion";
import { useMotionSafe } from "@/hooks/useReducedMotion";

interface ChatThreadProps {
  messages:      Message[];
  thinking:      boolean;
  onRegenerate?: (msgId: string) => void;
  className?:    string;
}

export function ChatThread({ messages, thinking, onRegenerate, className }: ChatThreadProps) {
  const { ref, scrollToBottom, showScrollBtn } = useAutoScroll([messages, thinking]);
  const { reduced } = useMotionSafe();

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={ref}
        role="log"
        aria-label="TaxMitra conversation"
        aria-live="polite"
        className={cn(
          "h-full overflow-y-auto px-4 py-6 space-y-6",
          "scroll-smooth",
          className
        )}
      >
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onRegenerate={onRegenerate ? () => onRegenerate(msg.id) : undefined}
            />
          ))}
          {thinking && (
            <motion.div
              key="thinking"
              variants={reduced ? {} : fadeUp}
              initial="hidden"
              animate="visible"
              exit="exit"
            >
              <ThinkingIndicator />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Scroll-to-latest FAB */}
      <AnimatePresence>
        {showScrollBtn && (
          <motion.button
            initial={{ opacity: 0, y: 8, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.9 }}
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll to latest message"
            className={cn(
              "absolute bottom-4 right-4 z-10",
              "flex h-9 w-9 items-center justify-center",
              "rounded-full glass border border-white/[0.12] shadow-glass",
              "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]",
              "transition-colors duration-fast"
            )}
          >
            <ChevronDown className="w-4 h-4" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
