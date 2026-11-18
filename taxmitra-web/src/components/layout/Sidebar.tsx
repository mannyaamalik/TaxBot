"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Search, Trash2, Edit3, MessageSquare, X } from "lucide-react";
import { useChatStore } from "@/store/chatStore";
import { TaxMitraLogo } from "@/components/brand/TaxMitraLogo";
import { ThemeToggle } from "@/components/brand/ThemeToggle";
import { cn } from "@/lib/utils";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { slideRight, DURATION } from "@/lib/motion";

interface SidebarProps {
  open:     boolean;
  onClose:  () => void;
  language: "en" | "hi";
}

export function Sidebar({ open, onClose, language }: SidebarProps) {
  const { sessions, activeSid, newChat, selectSession, renameSession, deleteSession } = useChatStore();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const { duration } = useMotionSafe();

  const filtered = sessions.filter((s) =>
    s.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      {/* Overlay (mobile) */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: duration(DURATION.base) }}
            className="fixed inset-0 z-20 bg-black/60 md:hidden"
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.aside
            key="sidebar"
            variants={slideRight}
            initial="hidden"
            animate="visible"
            exit="exit"
            className={cn(
              "fixed left-0 top-0 z-30 h-full w-72 flex flex-col",
              "glass border-r border-white/[0.08] shadow-popup"
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
              <TaxMitraLogo size="sm" />
              <button
                onClick={onClose}
                aria-label="Close sidebar"
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors duration-fast"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* New chat */}
            <div className="p-3 border-b border-white/[0.06]">
              <button
                onClick={() => { newChat(); onClose(); }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium",
                  "text-[var(--color-text-inverse)] transition-colors duration-fast",
                  "hover:opacity-90 active:scale-[0.98]"
                )}
                style={{ background: "var(--gradient-accent)" }}
              >
                <Plus className="w-4 h-4" />
                {language === "hi" ? "नई बातचीत" : "New chat"}
              </button>
            </div>

            {/* Search */}
            <div className="px-3 py-2">
              <div className="flex items-center gap-2 rounded-xl bg-white/[0.04] border border-white/[0.06] px-3 py-2">
                <Search className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={language === "hi" ? "खोजें…" : "Search chats…"}
                  className="flex-1 bg-transparent text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none"
                />
              </div>
            </div>

            {/* Sessions list */}
            <nav aria-label="Chat history" className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
              {filtered.map((session) => (
                <div
                  key={session.id}
                  className={cn(
                    "group flex items-center gap-2 rounded-xl px-3 py-2.5 cursor-pointer",
                    "transition-colors duration-fast text-sm",
                    activeSid === session.id
                      ? "bg-saffron/10 text-[var(--color-text-primary)]"
                      : "text-[var(--color-text-secondary)] hover:bg-white/[0.04] hover:text-[var(--color-text-primary)]"
                  )}
                  onClick={() => { selectSession(session.id); onClose(); }}
                >
                  <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70" />

                  {editing === session.id ? (
                    <input
                      autoFocus
                      value={editVal}
                      onChange={(e) => setEditVal(e.target.value)}
                      onBlur={() => {
                        if (editVal.trim()) renameSession(session.id, editVal.trim());
                        setEditing(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          if (editVal.trim()) renameSession(session.id, editVal.trim());
                          setEditing(null);
                        }
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 bg-transparent text-sm focus:outline-none border-b border-saffron"
                    />
                  ) : (
                    <span className="flex-1 truncate">{session.title}</span>
                  )}

                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-fast">
                    <button
                      aria-label="Rename chat"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing(session.id);
                        setEditVal(session.title);
                      }}
                      className="p-1 rounded hover:text-[var(--color-text-primary)]"
                    >
                      <Edit3 className="w-3 h-3" />
                    </button>
                    <button
                      aria-label="Delete chat"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSession(session.id);
                      }}
                      className="p-1 rounded hover:text-red-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </nav>

            {/* Footer */}
            <div className="border-t border-white/[0.06] p-3 flex items-center justify-between">
              <ThemeToggle />
              <span className="text-xs text-[var(--color-text-muted)]">
                {sessions.length} {language === "hi" ? "बातचीत" : "chats"}
              </span>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
