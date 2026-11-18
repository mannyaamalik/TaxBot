"use client";
/**
 * /design — Component showcase page.
 * Shows all TaxMitra primitives, chat components, and states.
 */
import { useState } from "react";
import { PageBackground } from "@/components/layout/PageBackground";
import { TaxMitraLogo } from "@/components/brand/TaxMitraLogo";
import { ThemeToggle } from "@/components/brand/ThemeToggle";
import { GlassCard } from "@/components/primitives/GlassCard";
import { SectionBadge } from "@/components/primitives/SectionBadge";
import { SourcePill } from "@/components/primitives/SourcePill";
import { Spinner } from "@/components/primitives/Spinner";
import { MonoAmount } from "@/components/primitives/MonoAmount";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ThinkingIndicator } from "@/components/chat/ThinkingIndicator";
import { SuggestedQuestions } from "@/components/chat/SuggestedQuestions";
import { QuestionInput } from "@/components/input/QuestionInput";
import { FeedbackButtons } from "@/components/feedback/FeedbackButtons";
import { TaxCalculatorPanel } from "@/components/calculator/TaxCalculatorPanel";
import { CommandPalette } from "@/components/ui/CommandPalette";
import { Message, SourceItem } from "@/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-lg font-semibold mb-4 gradient-text">{title}</h2>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-[var(--color-text-muted)] mb-2 font-mono">{label}</p>
      <div className="flex flex-wrap items-start gap-3">{children}</div>
    </div>
  );
}

const DEMO_SOURCE: SourceItem = {
  doc_title:       "Income Tax Act 1961",
  section_heading: "Section 80C — Deductions",
  page_number:     112,
  filename:        "IT_Act_1961_AY2024.pdf",
  assessment_year: "2024-25",
};

const DEMO_MSGS: Message[] = [
  {
    id: "u1", role: "user", content: "What is the Section 80C deduction limit?",
    status: "normal", sources: [], timestamp: new Date(),
  },
  {
    id: "a1", role: "assistant",
    content: "Under **Section 80C** of the Income Tax Act, the aggregate deduction limit is **₹1,50,000** per financial year. This includes investments in ELSS funds, PPF, NSC, life insurance premiums, and tuition fees for children.\n\n> Note: The limit has remained unchanged since AY 2015-16.",
    status: "normal", sources: [DEMO_SOURCE], timestamp: new Date(),
  },
  {
    id: "a2", role: "assistant",
    content: "I could not find an answer to this question in my knowledge base. Please consult a qualified tax professional.",
    status: "not_found", sources: [], timestamp: new Date(),
  },
  {
    id: "a3", role: "assistant",
    content: "I can only answer questions about Indian Income Tax and GST.",
    status: "out_of_scope", sources: [], timestamp: new Date(),
  },
  {
    id: "a4", role: "assistant", content: "Something went wrong.",
    status: "error", sources: [], timestamp: new Date(),
  },
  {
    id: "a5", role: "assistant",
    content: "Streaming answer appears here token by token…",
    status: "normal", sources: [], timestamp: new Date(), streaming: true,
  },
];

export default function DesignPage() {
  const [inputVal,    setInputVal]    = useState("");
  const [calcOpen,    setCalcOpen]    = useState(false);
  const [cmdOpen,     setCmdOpen]     = useState(false);

  return (
    <div className="min-h-screen bg-[var(--color-bg-base)] noise-bg relative">
      <PageBackground />

      <div className="relative z-10 max-w-4xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-12">
          <div>
            <h1 className="text-3xl font-bold gradient-text">TaxMitra Design System</h1>
            <p className="text-sm text-[var(--color-text-secondary)] mt-1">
              Component showcase — visit <code className="text-saffron">/design</code> to see all components.
            </p>
          </div>
          <ThemeToggle />
        </div>

        {/* Logo */}
        <Section title="Brand / Logo">
          <Row label="TaxMitraLogo — size=sm/md/lg, showTagline">
            <TaxMitraLogo size="sm" />
            <TaxMitraLogo size="md" />
            <TaxMitraLogo size="lg" showTagline />
          </Row>
        </Section>

        {/* Primitives */}
        <Section title="Primitives">
          <Row label="GlassCard — padding=sm/md/lg, hover">
            <GlassCard padding="sm" className="text-sm">Small</GlassCard>
            <GlassCard padding="md" className="text-sm">Medium</GlassCard>
            <GlassCard hover padding="lg" className="text-sm">Hover me</GlassCard>
          </Row>

          <Row label="SectionBadge">
            {["80C", "80D", "24b", "194C", "LTCG"].map((s) => (
              <SectionBadge key={s} section={s} />
            ))}
          </Row>

          <Row label="MonoAmount">
            <MonoAmount value={150000} />
            <MonoAmount value={2500000} />
            <MonoAmount value={18} currency="%" />
          </Row>

          <Row label="Spinner — sm/md/lg">
            <Spinner size="sm" />
            <Spinner size="md" />
            <Spinner size="lg" />
          </Row>

          <Row label="SourcePill">
            <SourcePill index={1} source={DEMO_SOURCE} />
            <SourcePill index={2} source={{ ...DEMO_SOURCE, doc_title: "CGST Act 2017", section_heading: "Section 23 — Registration Exemption" }} />
          </Row>
        </Section>

        {/* Feedback */}
        <Section title="Feedback Buttons">
          <Row label="FeedbackButtons — submits POST /feedback">
            <FeedbackButtons
              messageId="demo-1"
              sessionId="demo-session"
              question="What is 80C limit?"
              answer="₹1,50,000"
            />
          </Row>
        </Section>

        {/* Chat messages */}
        <Section title="Message Bubbles">
          <Row label="All message states">
            <div className="w-full max-w-2xl space-y-4">
              {DEMO_MSGS.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
            </div>
          </Row>

          <Row label="ThinkingIndicator">
            <ThinkingIndicator />
          </Row>
        </Section>

        {/* Suggested Questions */}
        <Section title="Suggested Questions">
          <SuggestedQuestions onSelect={(q) => alert(`Selected: ${q}`)} />
        </Section>

        {/* Input */}
        <Section title="Question Input">
          <Row label="QuestionInput with voice mic">
            <div className="w-full max-w-2xl">
              <QuestionInput
                value={inputVal}
                onChange={setInputVal}
                onSubmit={() => alert(`Submit: ${inputVal}`)}
                loading={false}
              />
            </div>
          </Row>
          <Row label="QuestionInput — loading state">
            <div className="w-full max-w-2xl">
              <QuestionInput
                value="What is the new regime slab for ₹8L income?"
                onChange={() => {}}
                onSubmit={() => {}}
                loading={true}
              />
            </div>
          </Row>
        </Section>

        {/* Colour palette */}
        <Section title="Colour Tokens">
          <Row label="Brand colours">
            {[
              { name: "Saffron", bg: "bg-[#FF9933]" },
              { name: "Emerald", bg: "bg-[#138808]" },
              { name: "Info",    bg: "bg-[var(--color-info)]" },
              { name: "Warning", bg: "bg-[var(--color-warning)]" },
              { name: "Error",   bg: "bg-[var(--color-error)]" },
              { name: "Success", bg: "bg-[var(--color-success)]" },
            ].map((c) => (
              <div key={c.name} className="flex flex-col items-center gap-1.5">
                <div className={`w-10 h-10 rounded-xl ${c.bg}`} />
                <span className="text-xs text-[var(--color-text-muted)]">{c.name}</span>
              </div>
            ))}
          </Row>

          <Row label="Gradient accent (Indian tricolour)">
            <div className="h-8 w-48 rounded-xl" style={{ background: "var(--gradient-accent)" }} />
          </Row>

          <Row label="gradient-text utility">
            <span className="text-2xl font-bold gradient-text">TaxMitra</span>
          </Row>

          <Row label="glass card">
            <div className="glass rounded-2xl border border-[var(--color-border)] p-4 text-sm w-48">
              glass + backdrop-filter
            </div>
          </Row>
        </Section>

        {/* Panels */}
        <Section title="Overlay Panels">
          <Row label="Tax Calculator Panel + Command Palette">
            <button
              onClick={() => setCalcOpen(true)}
              className="rounded-xl px-4 py-2 text-sm font-medium text-[var(--color-text-inverse)]"
              style={{ background: "var(--gradient-accent)" }}
            >
              Open Tax Calculator
            </button>
            <button
              onClick={() => setCmdOpen(true)}
              className="rounded-xl px-4 py-2 text-sm font-medium glass border border-[var(--color-border)] text-[var(--color-text-primary)]"
            >
              Open Command Palette (⌘K)
            </button>
          </Row>
        </Section>

        <footer className="mt-16 pt-6 border-t border-[var(--color-border)] text-center text-xs text-[var(--color-text-muted)]">
          TaxMitra Design System — not professional tax advice.
        </footer>
      </div>

      <TaxCalculatorPanel open={calcOpen} onClose={() => setCalcOpen(false)} />
      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        language="en"
        onNewChat={() => setCmdOpen(false)}
        onOpenCalculator={() => { setCalcOpen(true); setCmdOpen(false); }}
        onToggleLanguage={() => setCmdOpen(false)}
        onToggleTheme={() => setCmdOpen(false)}
      />
    </div>
  );
}
