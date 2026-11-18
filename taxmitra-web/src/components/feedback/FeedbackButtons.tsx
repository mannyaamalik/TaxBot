"use client";
import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { FeedbackType } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface FeedbackButtonsProps {
  messageId:  string;
  sessionId:  string;
  question:   string;
  answer:     string;
  language?:  "en" | "hi";
  className?: string;
}

export function FeedbackButtons({
  messageId, sessionId, question, answer, language = "en", className,
}: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<FeedbackType | null>(null);
  const [loading,   setLoading]   = useState(false);

  const submit = async (type: FeedbackType) => {
    if (submitted || loading) return;
    setLoading(true);
    try {
      await fetch(`${BASE}/feedback`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          session_id: sessionId,
          question,
          answer,
          feedback:   type,
        }),
      });
      setSubmitted(type);
      toast.success(
        language === "hi"
          ? type === "up" ? "धन्यवाद! 👍" : "फ़ीडबैक के लिए धन्यवाद"
          : type === "up" ? "Thanks for the feedback! 👍" : "Thanks — we'll improve 🙏",
        { duration: 2500 }
      );
    } catch {
      // Best-effort — don't surface errors to user
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={cn("flex items-center gap-1", className)}>
      <button
        onClick={() => submit("up")}
        disabled={!!submitted || loading}
        aria-label="Helpful"
        aria-pressed={submitted === "up"}
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-fast",
          submitted === "up"
            ? "bg-emerald-500/20 text-emerald-400"
            : "text-[var(--color-text-muted)] hover:text-emerald-400 hover:bg-emerald-500/10 active:scale-90",
          "disabled:opacity-50 disabled:cursor-default"
        )}
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => submit("down")}
        disabled={!!submitted || loading}
        aria-label="Not helpful"
        aria-pressed={submitted === "down"}
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-fast",
          submitted === "down"
            ? "bg-red-500/20 text-red-400"
            : "text-[var(--color-text-muted)] hover:text-red-400 hover:bg-red-500/10 active:scale-90",
          "disabled:opacity-50 disabled:cursor-default"
        )}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
