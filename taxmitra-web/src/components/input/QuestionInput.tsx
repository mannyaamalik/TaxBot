"use client";
import { useRef, useCallback, useEffect } from "react";
import { Mic, MicOff } from "lucide-react";
import { SendButton } from "./SendButton";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { DURATION } from "@/lib/motion";

interface QuestionInputProps {
  value:        string;
  onChange:     (v: string) => void;
  onSubmit:     () => void;
  loading:      boolean;
  placeholder?: string;
  className?:   string;
  language?:    "en" | "hi";
}

const MAX = 2000;

export function QuestionInput({
  value, onChange, onSubmit, loading,
  placeholder, className, language = "en",
}: QuestionInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { duration } = useMotionSafe();

  const { listening, supported, toggle } = useVoiceInput((text) => {
    onChange(value ? `${value} ${text}` : text);
  });

  /* Auto-resize textarea */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const handleKey = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && value.trim()) onSubmit();
    }
  }, [loading, onSubmit, value]);

  const ph = placeholder ?? (language === "hi"
    ? "Income Tax या GST के बारे में कोई भी सवाल पूछें…"
    : "Ask anything about Income Tax or GST…");

  return (
    <div className={cn("relative", className)}>
      <div
        className={cn(
          "glass rounded-2xl border shadow-glass",
          "flex items-end gap-2 px-4 py-3",
          listening ? "border-saffron" : "border-white/[0.08]",
          "transition-colors duration-fast"
        )}
      >
        {/* Animated waveform when listening */}
        <AnimatePresence>
          {listening && (
            <motion.div
              key="wave"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: duration(DURATION.fast) }}
              className="flex items-center gap-0.5 shrink-0"
            >
              {[0, 1, 2, 3, 4].map((i) => (
                <motion.span
                  key={i}
                  className="w-1 rounded-full bg-saffron"
                  animate={{ height: [4, 16, 4] }}
                  transition={{
                    duration: duration(0.6),
                    repeat: Infinity,
                    delay: i * 0.08,
                    ease: "easeInOut",
                  }}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX))}
          onKeyDown={handleKey}
          placeholder={ph}
          rows={1}
          aria-label="Ask a tax question"
          aria-describedby="input-hint"
          className={cn(
            "flex-1 resize-none bg-transparent text-[15px] leading-relaxed",
            "text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]",
            "focus:outline-none max-h-[200px] overflow-y-auto"
          )}
        />

        {/* Mic button */}
        {supported && (
          <button
            onClick={toggle}
            aria-label={listening ? "Stop listening" : "Start voice input"}
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
              "transition-colors duration-fast",
              listening
                ? "bg-saffron/20 text-saffron"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-white/[0.06]"
            )}
          >
            {listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
        )}

        <SendButton
          loading={loading}
          disabled={!value.trim() || value.length > MAX}
          onClick={onSubmit}
        />
      </div>

      {/* Character count + hint */}
      <div id="input-hint" className="mt-1.5 flex items-center justify-between px-1">
        <p className="text-xs text-[var(--color-text-muted)]">
          Shift+Enter for newline · Enter to send
        </p>
        {value.length > MAX * 0.8 && (
          <span className={cn("text-xs font-mono", value.length >= MAX ? "text-red-400" : "text-[var(--color-text-muted)]")}>
            {value.length}/{MAX}
          </span>
        )}
      </div>
    </div>
  );
}
