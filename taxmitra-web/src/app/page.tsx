"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, Languages, Calculator, AlertCircle, X } from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "@/store/chatStore";
import { sendChatStream } from "@/lib/api";
import { isOutOfScope, isClarification } from "@/lib/utils";
import { PageBackground } from "@/components/layout/PageBackground";
import { Sidebar } from "@/components/layout/Sidebar";
import { TaxMitraLogo } from "@/components/brand/TaxMitraLogo";
import { ThemeToggle } from "@/components/brand/ThemeToggle";
import { ChatThread } from "@/components/chat/ChatThread";
import { SuggestedQuestions } from "@/components/chat/SuggestedQuestions";
import { QuestionInput } from "@/components/input/QuestionInput";
import { TaxCalculatorPanel } from "@/components/calculator/TaxCalculatorPanel";
import { CommandPalette } from "@/components/ui/CommandPalette";
import { MessageStatus, SourceItem } from "@/types";
import { fadeUp, staggerContainer } from "@/lib/motion";
import { useMotionSafe } from "@/hooks/useReducedMotion";

/** Animated typewriter hero text */
function TypewriterHero({ language }: { language: "en" | "hi" }) {
  const text =
    language === "hi"
      ? "Income Tax और GST के बारे में कुछ भी पूछें"
      : "Ask me anything about Income Tax & GST";
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  const idxRef = useRef(0);

  useEffect(() => {
    setDisplayed("");
    setDone(false);
    idxRef.current = 0;
    const id = setInterval(() => {
      idxRef.current++;
      setDisplayed(text.slice(0, idxRef.current));
      if (idxRef.current >= text.length) {
        clearInterval(id);
        setDone(true);
      }
    }, 42);
    return () => clearInterval(id);
  }, [text]);

  return (
    <h1 className="text-3xl sm:text-4xl font-bold leading-tight tracking-tight">
      <span className="gradient-text">{displayed}</span>
      {!done && (
        <span
          aria-hidden="true"
          className="inline-block w-0.5 h-8 bg-[var(--color-primary)] ml-1 animate-[blink_1s_step-end_infinite] align-middle"
        />
      )}
    </h1>
  );
}

export default function ChatPage() {
  const { activeSession, addUserMessage, addAssistantMessage, updateMessage,
          language, setLanguage, calculatorOpen, setCalculatorOpen } = useChatStore();
  const { reduced } = useMotionSafe();

  const session          = activeSession();
  const hasMessages      = session.messages.length > 0;

  const [sidebarOpen,    setSidebarOpen]    = useState(false);
  const [commandOpen,    setCommandOpen]    = useState(false);
  const [inputValue,     setInputValue]     = useState("");
  const [loading,        setLoading]        = useState(false);
  const [thinking,       setThinking]       = useState(false);
  const [dismissedBanner, setDismissedBanner] = useState(false);
  const abortRef         = useRef<AbortController | null>(null);

  /* Cmd+K → command palette */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  /* Open calculator if bot references it */
  const handleSendMessage = useCallback(async (question: string) => {
    if (!question.trim() || loading) return;

    // Detect calculator intent
    if (/calculator|compare.*regime|tax.*slab.*compare/i.test(question)) {
      setCalculatorOpen(true);
    }

    setInputValue("");
    setLoading(true);
    setThinking(true);

    addUserMessage(question);

    // Placeholder assistant message
    const assistantId = addAssistantMessage("", "normal", [], true);

    const controller = new AbortController();
    abortRef.current = controller;

    let streamedContent = "";

    try {
      await sendChatStream(
        { question, session_id: session.session_id, language },
        (token) => {
          setThinking(false);
          streamedContent += token;
          updateMessage(assistantId, { content: streamedContent, streaming: true });
        },
        (response) => {
          const status: MessageStatus = response.not_found
            ? "not_found"
            : isClarification(response.answer)
            ? "clarification"
            : isOutOfScope(response.answer)
            ? "out_of_scope"
            : "normal";

          updateMessage(assistantId, {
            content:  response.answer,
            status,
            sources:  response.sources as SourceItem[],
            streaming: false,
          });
        },
        controller.signal
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      const message =
        err instanceof Error && err.message === "RATE_LIMITED"
          ? "Too many requests — please wait a moment before asking again."
          : "Something went wrong. Please check your connection and try again.";
      updateMessage(assistantId, {
        content:  message,
        status:   "error",
        sources:  [],
        streaming: false,
      });
      toast.error("Error", { description: message });
    } finally {
      setLoading(false);
      setThinking(false);
      abortRef.current = null;
    }
  }, [loading, session.session_id, language, addUserMessage, addAssistantMessage, updateMessage, setCalculatorOpen]);

  const handleRegenerate = useCallback(async (msgId: string) => {
    const msgs = session.messages;
    const idx  = msgs.findIndex((m) => m.id === msgId);
    if (idx <= 0) return;
    const userMsg = msgs[idx - 1];
    if (userMsg.role !== "user") return;
    updateMessage(msgId, { content: "", streaming: true, status: "normal", sources: [] });
    setThinking(true);
    setLoading(true);
    let streamed = "";
    try {
      await sendChatStream(
        { question: userMsg.content, session_id: session.session_id, language },
        (tok) => { setThinking(false); streamed += tok; updateMessage(msgId, { content: streamed, streaming: true }); },
        (resp) => {
          const status: MessageStatus = resp.not_found ? "not_found" : isOutOfScope(resp.answer) ? "out_of_scope" : "normal";
          updateMessage(msgId, { content: resp.answer, status, sources: resp.sources as SourceItem[], streaming: false });
        }
      );
    } catch {
      updateMessage(msgId, { content: "Regeneration failed.", status: "error", sources: [], streaming: false });
    } finally { setLoading(false); setThinking(false); }
  }, [session, language, updateMessage]);

  return (
    <div className="relative flex h-dvh overflow-hidden bg-[var(--color-bg-base)] noise-bg">
      <PageBackground />

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} language={language} />

      {/* Main column */}
      <div className="relative z-10 flex flex-1 flex-col min-w-0">

        {/* ── Disclaimer Banner ── */}
        <AnimatePresence>
          {!dismissedBanner && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-center gap-2 px-4 py-2 bg-[var(--color-warning-muted)] border-b border-[var(--color-warning)]/20 text-[var(--color-warning)] text-xs">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span className="flex-1">
                  {language === "hi"
                    ? "केवल सूचनात्मक — यह पेशेवर कर सलाह नहीं है। आधिकारिक जानकारी के लिए incometax.gov.in या gst.gov.in देखें।"
                    : "Informational only — not professional tax advice. For official guidance visit incometax.gov.in or gst.gov.in."}
                </span>
                <button
                  onClick={() => setDismissedBanner(true)}
                  aria-label="Dismiss disclaimer"
                  className="shrink-0 hover:opacity-70 transition-opacity"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Top Bar ── */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)] glass">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open chat history sidebar"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-white/[0.06] transition-colors"
          >
            <Menu className="w-4 h-4" />
          </button>

          <TaxMitraLogo size="sm" className="flex-1" />

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setLanguage(language === "en" ? "hi" : "en")}
              aria-label={`Switch to ${language === "en" ? "Hindi" : "English"}`}
              title={language === "en" ? "हिंदी में बदलें" : "Switch to English"}
              className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-white/[0.06] transition-colors"
            >
              <Languages className="w-4 h-4" />
              <span>{language === "en" ? "हिंदी" : "EN"}</span>
            </button>

            <button
              onClick={() => setCalculatorOpen(true)}
              aria-label="Open tax calculator"
              title="Tax calculator"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] hover:bg-saffron/10 transition-colors"
            >
              <Calculator className="w-4 h-4" />
            </button>

            <ThemeToggle />

            <kbd
              onClick={() => setCommandOpen(true)}
              className="hidden sm:flex items-center gap-1 rounded-md border border-[var(--color-border)] px-2 py-1 text-[10px] text-[var(--color-text-muted)] cursor-pointer hover:border-saffron/40 hover:text-[var(--color-text-secondary)] transition-colors"
              title="Open command palette"
            >
              <span>⌘K</span>
            </kbd>
          </div>
        </header>

        {/* ── Empty / Hero state ── */}
        <AnimatePresence mode="wait">
          {!hasMessages && (
            <motion.div
              key="hero"
              variants={reduced ? {} : staggerContainer(0.1)}
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, transition: { duration: 0.15 } }}
              className="flex-1 overflow-y-auto px-4 py-10 flex flex-col items-center"
            >
              <motion.div
                variants={reduced ? {} : fadeUp}
                className="w-full max-w-3xl text-center mb-10 space-y-3"
              >
                <TaxMitraLogo size="lg" className="justify-center mb-4" />
                <TypewriterHero language={language} />
                <p className="text-sm text-[var(--color-text-secondary)] max-w-md mx-auto">
                  {language === "hi"
                    ? "आधिकारिक दस्तावेज़ों पर आधारित उत्तर, स्रोत के साथ।"
                    : "Answers grounded in official documents, with citations."}
                </p>
              </motion.div>

              <motion.div variants={reduced ? {} : fadeUp} className="w-full max-w-3xl">
                <SuggestedQuestions
                  language={language}
                  onSelect={handleSendMessage}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Chat thread ── */}
        {hasMessages && (
          <ChatThread
            messages={session.messages}
            thinking={thinking}
            onRegenerate={handleRegenerate}
            className="flex-1"
          />
        )}

        {/* ── Input bar ── */}
        <div className="glass border-t border-[var(--color-border)] px-4 py-3 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <QuestionInput
              value={inputValue}
              onChange={setInputValue}
              onSubmit={() => handleSendMessage(inputValue)}
              loading={loading}
              language={language}
            />
          </div>
        </div>
      </div>

      {/* ── Calculator panel ── */}
      <TaxCalculatorPanel open={calculatorOpen} onClose={() => setCalculatorOpen(false)} language={language} />

      {/* ── Command palette ── */}
      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        language={language}
        onOpenCalculator={() => { setCalculatorOpen(true); setCommandOpen(false); }}
        onNewChat={() => { useChatStore.getState().newChat(); setCommandOpen(false); }}
        onToggleLanguage={() => { setLanguage(language === "en" ? "hi" : "en"); setCommandOpen(false); }}
        onToggleTheme={() => { const el = document.documentElement; el.classList.toggle("theme-light"); setCommandOpen(false); }}
      />
    </div>
  );
}
