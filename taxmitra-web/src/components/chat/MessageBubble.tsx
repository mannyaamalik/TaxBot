"use client";
import { useCallback } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, RefreshCw, Share2, AlertTriangle, HelpCircle } from "lucide-react";
import { Message } from "@/types";
import { SourcesAccordion } from "./SourcesAccordion";
import { FeedbackButtons } from "@/components/feedback/FeedbackButtons";
import { cn } from "@/lib/utils";
import { useMotionSafe } from "@/hooks/useReducedMotion";
import { fadeUp, DURATION, EASING } from "@/lib/motion";
import { useChatStore } from "@/store/chatStore";
import { toast } from "sonner";

interface MessageBubbleProps {
  message:        Message;
  onRegenerate?:  () => void;
  className?:     string;
  language?:      "en" | "hi";
}

const statusStyles: Record<string, string> = {
  normal:        "border-l-4 border-l-blue-500",
  not_found:     "border-l-4 border-l-amber-500",
  clarification: "border-l-4 border-l-saffron",
  out_of_scope:  "border-l-4 border-l-amber-400",
  error:         "border-l-4 border-l-red-500",
};

const statusIcons: Record<string, React.ReactNode> = {
  not_found:     <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />,
  clarification: <HelpCircle className="w-4 h-4 text-saffron shrink-0 mt-0.5" />,
  out_of_scope:  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />,
  error:         <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />,
};

export function MessageBubble({ message, onRegenerate, className, language = "en" }: MessageBubbleProps) {
  const { reduced, duration } = useMotionSafe();
  const { activeSession } = useChatStore();
  const session = activeSession();

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(message.content);
    toast.success("Copied to clipboard");
  }, [message.content]);

  const handleShare = useCallback(() => {
    if (navigator.share) {
      navigator.share({ text: message.content, title: "TaxMitra answer" });
    } else {
      navigator.clipboard.writeText(message.content);
      toast.success("Copied to clipboard");
    }
  }, [message.content]);

  /* ── User bubble ── */
  if (message.role === "user") {
    return (
      <motion.article
        aria-label="Your question"
        variants={reduced ? {} : fadeUp}
        initial="hidden"
        animate="visible"
        className={cn("flex justify-end", className)}
      >
        <div
          className="max-w-prose rounded-2xl rounded-br-sm px-4 py-3 text-[var(--color-text-primary)] text-[15px] leading-relaxed"
          style={{ background: "var(--gradient-accent)" }}
        >
          <p className="text-[var(--color-text-inverse)] font-medium">{message.content}</p>
        </div>
      </motion.article>
    );
  }

  /* ── Assistant bubble ── */
  const isAlert = message.status === "not_found" || message.status === "error";
  const icon    = statusIcons[message.status];

  return (
    <motion.article
      aria-label="TaxMitra response"
      role={isAlert ? "alert" : "article"}
      variants={reduced ? {} : {
        hidden:  { opacity: 0, y: 12 },
        visible: { opacity: 1, y: 0, transition: { duration: duration(DURATION.base), ease: EASING.enter } },
      }}
      initial="hidden"
      animate="visible"
      className={cn("group", className)}
    >
      <div
        className={cn(
          "glass rounded-2xl rounded-bl-sm px-4 py-4",
          "border border-white/[0.08] shadow-card",
          statusStyles[message.status]
        )}
      >
        {/* Status icon for special states */}
        {icon && (
          <div className="flex items-center gap-2 mb-2 text-sm font-medium text-[var(--color-text-secondary)]">
            {icon}
            <span>
              {message.status === "not_found" && "Not found in sources"}
              {message.status === "clarification" && "Clarification needed"}
              {message.status === "out_of_scope" && "Outside my scope"}
              {message.status === "error" && "Something went wrong"}
            </span>
          </div>
        )}

        {/* Markdown content */}
        <div className={cn("prose-chat", message.streaming && "typewriter-cursor")}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Sources */}
        {message.sources.length > 0 && (
          <SourcesAccordion sources={message.sources} />
        )}

        {/* Timestamp */}
        <div className="mt-2 text-xs text-[var(--color-text-muted)]">
          {message.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>

      {/* Action bar — visible on hover */}
      {message.role === "assistant" && message.status === "normal" && (
        <div
          className={cn(
            "mt-1 flex items-center gap-1 opacity-0 group-hover:opacity-100",
            "transition-opacity duration-fast"
          )}
        >
          <ActionBtn onClick={handleCopy} label="Copy" icon={<Copy className="w-3.5 h-3.5" />} />
          <FeedbackButtons
            messageId={message.id}
            sessionId={session.session_id}
            question={session.messages.find(
              (m, i, arr) => arr[i + 1]?.id === message.id && m.role === "user"
            )?.content ?? ""}
            answer={message.content}
            language={language}
          />
          {onRegenerate && (
            <ActionBtn onClick={onRegenerate} label="Regenerate" icon={<RefreshCw className="w-3.5 h-3.5" />} />
          )}
          <ActionBtn onClick={handleShare} label="Share" icon={<Share2 className="w-3.5 h-3.5" />} />
        </div>
      )}
    </motion.article>
  );
}

function ActionBtn({
  onClick, label, icon, active,
}: {
  onClick: () => void;
  label:   string;
  icon:    React.ReactNode;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "flex items-center gap-1 rounded-lg px-2 py-1 text-xs",
        "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]",
        "hover:bg-white/[0.06] transition-colors duration-fast",
        "active:scale-95 focus-visible:outline-2 focus-visible:outline-[var(--color-border-focus)]",
        active && "text-[var(--color-text-primary)]"
      )}
    >
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
