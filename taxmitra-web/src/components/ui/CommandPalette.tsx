"use client";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Command, MessageSquarePlus, Calculator, Languages, Sun,
  Moon, FileText, Info, Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DURATION } from "@/lib/motion";

interface CommandItem {
  id:      string;
  label:   string;
  labelHi: string;
  icon:    React.ElementType;
  group:   string;
  action:  () => void;
  keys?:   string[];
}

interface CommandPaletteProps {
  open:              boolean;
  onClose:           () => void;
  language:          "en" | "hi";
  onNewChat:         () => void;
  onOpenCalculator:  () => void;
  onToggleLanguage:  () => void;
  onToggleTheme:     () => void;
}

export function CommandPalette({
  open, onClose, language,
  onNewChat, onOpenCalculator, onToggleLanguage, onToggleTheme,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const COMMANDS: CommandItem[] = [
    { id: "new-chat",    label: "New Chat",          labelHi: "नई बातचीत",         icon: MessageSquarePlus, group: "Chat",     action: onNewChat,        keys: ["N"] },
    { id: "calculator",  label: "Tax Calculator",    labelHi: "कर कैलकुलेटर",      icon: Calculator,       group: "Tools",    action: onOpenCalculator, keys: ["C"] },
    { id: "language",    label: `Switch to ${language === "en" ? "Hindi" : "English"}`, labelHi: language === "en" ? "हिंदी में बदलें" : "अंग्रेज़ी में बदलें", icon: Languages, group: "Settings", action: onToggleLanguage },
    { id: "theme",       label: "Toggle Dark/Light", labelHi: "थीम बदलें",          icon: Sun,              group: "Settings", action: onToggleTheme },
    { id: "itr1",        label: "How to file ITR-1?", labelHi: "ITR-1 कैसे भरें?",  icon: FileText,         group: "Quick Ask", action: () => { onClose(); /* parent handles */ } },
    { id: "80c",         label: "Section 80C investments", labelHi: "धारा 80C",    icon: Info,             group: "Quick Ask", action: () => { onClose(); } },
    { id: "regime",      label: "Old vs new regime", labelHi: "पुरानी vs नई व्यवस्था", icon: Moon,          group: "Quick Ask", action: () => { onClose(); } },
  ];

  const filtered = query
    ? COMMANDS.filter((c) =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.labelHi.includes(query)
      )
    : COMMANDS;

  const groups = Array.from(new Set(filtered.map((c) => c.group)));

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape")  { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)); }
      if (e.key === "ArrowUp")   { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = filtered[selected];
        if (item) { item.action(); onClose(); }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, selected, onClose]);

  let idx = -1;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="cmd-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Dialog */}
          <motion.div
            key="cmd-dialog"
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1,    y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2"
            role="dialog"
            aria-label="Command palette"
            aria-modal="true"
          >
            <div className="glass rounded-2xl border border-[var(--color-border)] shadow-popup overflow-hidden">
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)]">
                <Search className="w-4 h-4 text-[var(--color-text-muted)] shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={language === "hi" ? "कमांड खोजें…" : "Search commands…"}
                  className="flex-1 bg-transparent text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none"
                  aria-label="Command search"
                />
                <kbd className="rounded px-1.5 py-0.5 text-[10px] border border-[var(--color-border)] text-[var(--color-text-muted)]">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-72 overflow-y-auto py-2">
                {filtered.length === 0 ? (
                  <p className="px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">
                    {language === "hi" ? "कोई परिणाम नहीं" : "No results"}
                  </p>
                ) : (
                  groups.map((group) => (
                    <div key={group}>
                      <p className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                        {group}
                      </p>
                      {filtered
                        .filter((c) => c.group === group)
                        .map((item) => {
                          idx++;
                          const isActive = idx === selected;
                          const Icon = item.icon;
                          return (
                            <button
                              key={item.id}
                              onClick={() => { item.action(); onClose(); }}
                              onMouseEnter={() => setSelected(idx)}
                              className={cn(
                                "flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors duration-fast",
                                isActive
                                  ? "bg-saffron/10 text-[var(--color-text-primary)]"
                                  : "text-[var(--color-text-secondary)] hover:bg-white/[0.04]"
                              )}
                            >
                              <div className={cn(
                                "flex h-7 w-7 items-center justify-center rounded-lg",
                                isActive ? "bg-saffron/20" : "bg-white/[0.04]"
                              )}>
                                <Icon className="w-3.5 h-3.5" />
                              </div>
                              <span className="flex-1 text-left">
                                {language === "hi" ? item.labelHi : item.label}
                              </span>
                              {item.keys && (
                                <div className="flex gap-1">
                                  {item.keys.map((k) => (
                                    <kbd
                                      key={k}
                                      className="rounded px-1.5 py-0.5 text-[10px] border border-[var(--color-border)] text-[var(--color-text-muted)]"
                                    >
                                      {k}
                                    </kbd>
                                  ))}
                                </div>
                              )}
                            </button>
                          );
                        })}
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-[var(--color-border)] px-4 py-2 flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
                <span className="flex items-center gap-1">
                  <Command className="w-3 h-3" /> K
                </span>
                <span>{language === "hi" ? "नेविगेट करें" : "navigate"} ↑↓</span>
                <span>Enter {language === "hi" ? "चुनें" : "select"}</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
