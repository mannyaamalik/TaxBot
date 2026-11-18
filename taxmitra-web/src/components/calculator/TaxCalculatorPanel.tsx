"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, TrendingDown } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TaxCalcInput } from "@/types";
import { calculateTax } from "@/lib/taxCalc";
import { formatRupee, cn } from "@/lib/utils";
import { GlassCard } from "@/components/primitives/GlassCard";
import { DURATION } from "@/lib/motion";

interface TaxCalculatorPanelProps {
  open:      boolean;
  onClose:   () => void;
  language?: "en" | "hi";
}

type AgeGroup = "below60" | "60to80" | "above80";

function NumberInput({
  label, value, onChange, max, step = 10000,
}: {
  label: string; value: number; onChange: (n: number) => void; max?: number; step?: number;
}) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-[var(--color-text-secondary)] font-medium">{label}</label>
      <input
        type="number"
        value={value === 0 ? "" : value}
        min={0}
        max={max}
        step={step}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
        className={cn(
          "w-full rounded-xl px-3 py-2 text-sm bg-white/[0.04] border border-white/[0.08]",
          "text-[var(--color-text-primary)] focus:outline-none focus:border-saffron",
          "placeholder:text-[var(--color-text-muted)] transition-colors"
        )}
        placeholder="0"
      />
    </div>
  );
}

/** Animated number counter */
function AnimatedNumber({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(value);

  useEffect(() => {
    let start: number | null = null;
    const from = displayed;
    const to   = value;
    const duration = 600;

    const step = (ts: number) => {
      if (start === null) start = ts;
      const pct  = Math.min((ts - start) / duration, 1);
      const ease = 1 - Math.pow(1 - pct, 3);
      setDisplayed(Math.round(from + (to - from) * ease));
      if (pct < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span>{formatRupee(displayed)}</span>;
}

export function TaxCalculatorPanel({ open, onClose, language = "en" }: TaxCalculatorPanelProps) {
  const [input, setInput] = useState<TaxCalcInput>({
    income:          500000,
    age:             "below60",
    deductions80C:   150000,
    deductions80D:   25000,
    otherDeductions: 0,
    homeLoanInterest: 0,
  });

  const result = calculateTax(input);

  const chartData = [
    { name: language === "hi" ? "पुरानी व्यवस्था" : "Old Regime", tax: result.oldRegimeTax,  fill: "#FF9933" },
    { name: language === "hi" ? "नई व्यवस्था"    : "New Regime",  tax: result.newRegimeTax,   fill: "#138808" },
  ];

  const set = (k: keyof TaxCalcInput) => (v: number | AgeGroup) =>
    setInput((prev) => ({ ...prev, [k]: v }));

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="calc-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DURATION.fast }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            key="calc-panel"
            initial={{ opacity: 0, x: "100%" }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 z-50 h-full w-full max-w-md overflow-y-auto"
          >
            <GlassCard
              padding="none"
              className="h-full rounded-none border-l border-[var(--color-border)] flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
                <div>
                  <h2 className="font-semibold text-sm">
                    {language === "hi" ? "कर कैलकुलेटर" : "Tax Calculator"}
                  </h2>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
                    {language === "hi" ? "पुरानी vs नई व्यवस्था AY 2024-25" : "Old vs New Regime · AY 2024-25"}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  aria-label="Close calculator"
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-white/[0.06] transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-5">
                {/* Inputs */}
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                    {language === "hi" ? "आय विवरण" : "Income Details"}
                  </h3>

                  <NumberInput
                    label={language === "hi" ? "कुल वार्षिक आय (₹)" : "Annual Income (₹)"}
                    value={input.income}
                    onChange={set("income") as (n: number) => void}
                    step={50000}
                  />

                  {/* Age */}
                  <div className="space-y-1">
                    <label className="text-xs text-[var(--color-text-secondary)] font-medium">
                      {language === "hi" ? "आयु वर्ग" : "Age Group"}
                    </label>
                    <div className="flex gap-2">
                      {(["below60", "60to80", "above80"] as AgeGroup[]).map((a) => (
                        <button
                          key={a}
                          onClick={() => setInput((p) => ({ ...p, age: a }))}
                          className={cn(
                            "flex-1 rounded-lg py-1.5 text-xs font-medium border transition-colors",
                            input.age === a
                              ? "bg-saffron/15 border-saffron text-saffron"
                              : "border-white/[0.08] text-[var(--color-text-secondary)] hover:border-white/20"
                          )}
                        >
                          {a === "below60" ? "< 60" : a === "60to80" ? "60–80" : "80+"}
                        </button>
                      ))}
                    </div>
                  </div>
                </section>

                {/* Deductions */}
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                    {language === "hi" ? "कटौती (पुरानी व्यवस्था)" : "Deductions (Old Regime only)"}
                  </h3>
                  <NumberInput
                    label="Section 80C (max ₹1,50,000)"
                    value={input.deductions80C}
                    onChange={set("deductions80C") as (n: number) => void}
                    max={150000}
                  />
                  <NumberInput
                    label="Section 80D — Health Insurance (max ₹25,000)"
                    value={input.deductions80D}
                    onChange={set("deductions80D") as (n: number) => void}
                    max={25000}
                  />
                  <NumberInput
                    label={language === "hi" ? "गृह ऋण ब्याज – धारा 24(b) (max ₹2,00,000)" : "Home Loan Interest – Sec 24(b) (max ₹2,00,000)"}
                    value={input.homeLoanInterest}
                    onChange={set("homeLoanInterest") as (n: number) => void}
                    max={200000}
                  />
                  <NumberInput
                    label={language === "hi" ? "अन्य कटौती" : "Other Deductions"}
                    value={input.otherDeductions}
                    onChange={set("otherDeductions") as (n: number) => void}
                  />
                </section>

                {/* Results */}
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                    {language === "hi" ? "परिणाम" : "Results"}
                  </h3>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: language === "hi" ? "पुरानी व्यवस्था" : "Old Regime", value: result.oldRegimeTax, color: "#FF9933", best: result.recommendation === "old" },
                      { label: language === "hi" ? "नई व्यवस्था"    : "New Regime",  value: result.newRegimeTax,  color: "#138808", best: result.recommendation === "new" },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className={cn(
                          "rounded-xl p-3 border",
                          item.best
                            ? "border-saffron/40 bg-saffron/5"
                            : "border-white/[0.06] bg-white/[0.03]"
                        )}
                      >
                        <p className="text-xs text-[var(--color-text-secondary)] mb-1">{item.label}</p>
                        <p className="text-lg font-bold font-mono" style={{ color: item.color }}>
                          <AnimatedNumber value={item.value} />
                        </p>
                        {item.best && (
                          <div className="mt-1 flex items-center gap-1 text-[10px] text-emerald-400">
                            <TrendingDown className="w-3 h-3" />
                            {language === "hi" ? "बेहतर विकल्प" : "Better option"}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {result.saving > 0 && (
                    <p className="text-xs text-center text-[var(--color-text-secondary)]">
                      {language === "hi" ? "बचत: " : "You save "}
                      <span className="font-semibold text-emerald-400">{formatRupee(result.saving)}</span>
                      {language === "hi"
                        ? ` ${result.recommendation === "old" ? "पुरानी" : "नई"} व्यवस्था में`
                        : ` with the ${result.recommendation} regime`}
                    </p>
                  )}

                  {/* Bar chart */}
                  <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3">
                    <ResponsiveContainer width="100%" height={150}>
                      <BarChart data={chartData} barSize={40} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                        <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} axisLine={false} tickLine={false} />
                        <YAxis
                          tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                          tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                          axisLine={false}
                          tickLine={false}
                          width={50}
                        />
                        <Tooltip
                          formatter={(v) => [formatRupee(typeof v === "number" ? v : 0), "Tax"]}
                          contentStyle={{
                            background: "var(--color-bg-raised)",
                            border: "1px solid var(--color-border)",
                            borderRadius: "8px",
                            fontSize: "12px",
                          }}
                        />
                        <Bar dataKey="tax" radius={[6, 6, 0, 0]}>
                          {chartData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} fillOpacity={0.85} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Slab breakdown */}
                  <details className="text-xs">
                    <summary className="cursor-pointer text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors py-1">
                      {language === "hi" ? "स्लैब विवरण देखें" : "View slab breakdown"}
                    </summary>
                    <div className="mt-2 space-y-3">
                      {[
                        { title: language === "hi" ? "पुरानी व्यवस्था" : "Old Regime", slabs: result.oldRegimeSlabs },
                        { title: language === "hi" ? "नई व्यवस्था" : "New Regime",    slabs: result.newRegimeSlabs },
                      ].map(({ title, slabs }) => (
                        <div key={title}>
                          <p className="font-semibold text-[var(--color-text-primary)] mb-1">{title}</p>
                          <table className="w-full text-[11px]">
                            <thead>
                              <tr className="text-[var(--color-text-muted)]">
                                <th className="text-left py-0.5">{language === "hi" ? "स्लैब" : "Slab"}</th>
                                <th className="text-right py-0.5">{language === "hi" ? "दर" : "Rate"}</th>
                                <th className="text-right py-0.5">{language === "hi" ? "कर" : "Tax"}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {slabs.map((s, i) => (
                                <tr key={i} className="border-t border-white/[0.04]">
                                  <td className="py-0.5 text-[var(--color-text-secondary)]">{s.slab}</td>
                                  <td className="text-right py-0.5 text-[var(--color-text-secondary)]">{s.rate}%</td>
                                  <td className="text-right py-0.5 font-mono text-[var(--color-text-primary)]">{formatRupee(s.tax)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </div>
                  </details>
                </section>

                <p className="text-[10px] text-[var(--color-text-muted)] text-center pb-2">
                  {language === "hi"
                    ? "केवल अनुमान। ₹50L+ आय पर अधिभार लागू हो सकता है।"
                    : "Estimates only. Surcharge may apply for income > ₹50L. Consult a CA for accurate filing."}
                </p>
              </div>
            </GlassCard>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
