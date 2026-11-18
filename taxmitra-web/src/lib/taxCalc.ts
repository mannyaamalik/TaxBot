import { TaxCalcInput, TaxCalcResult } from "@/types";

/** ---- Slabs AY 2024-25 ---- */

// Old regime slabs (< 60 years)
const OLD_BELOW60 = [
  { upto: 250000,   rate: 0,   label: "Up to ₹2.5L" },
  { upto: 500000,   rate: 0.05, label: "₹2.5L–5L" },
  { upto: 1000000,  rate: 0.20, label: "₹5L–10L" },
  { upto: Infinity, rate: 0.30, label: "Above ₹10L" },
];
const OLD_60TO80 = [
  { upto: 300000,   rate: 0,    label: "Up to ₹3L" },
  { upto: 500000,   rate: 0.05, label: "₹3L–5L" },
  { upto: 1000000,  rate: 0.20, label: "₹5L–10L" },
  { upto: Infinity, rate: 0.30, label: "Above ₹10L" },
];
const OLD_ABOVE80 = [
  { upto: 500000,   rate: 0,    label: "Up to ₹5L" },
  { upto: 1000000,  rate: 0.20, label: "₹5L–10L" },
  { upto: Infinity, rate: 0.30, label: "Above ₹10L" },
];

// New regime slabs (AY 2024-25 onwards, same for all ages)
const NEW_REGIME = [
  { upto: 300000,   rate: 0,    label: "Up to ₹3L" },
  { upto: 600000,   rate: 0.05, label: "₹3L–6L" },
  { upto: 900000,   rate: 0.10, label: "₹6L–9L" },
  { upto: 1200000,  rate: 0.15, label: "₹9L–12L" },
  { upto: 1500000,  rate: 0.20, label: "₹12L–15L" },
  { upto: Infinity, rate: 0.30, label: "Above ₹15L" },
];

type Slab = { upto: number; rate: number; label: string };

function computeTaxFromSlabs(
  income: number,
  slabs: Slab[]
): { total: number; breakdown: { slab: string; rate: number; tax: number }[] } {
  let remaining = income;
  let total = 0;
  let prev = 0;
  const breakdown: { slab: string; rate: number; tax: number }[] = [];
  for (const { upto, rate, label } of slabs) {
    const bandSize = upto - prev;
    const taxable  = Math.min(remaining, bandSize);
    const tax      = taxable * rate;
    if (taxable > 0) {
      breakdown.push({ slab: label, rate: rate * 100, tax: Math.round(tax) });
    }
    total     += tax;
    remaining -= taxable;
    prev       = upto;
    if (remaining <= 0) break;
  }
  return { total: Math.round(total), breakdown };
}

/** Add 4% health & education cess */
function withCess(tax: number): number {
  return Math.round(tax * 1.04);
}

/** Section 87A rebate — old regime: up to ₹5L income, rebate up to ₹12,500 */
function applyOldRebate(tax: number, taxableIncome: number): number {
  if (taxableIncome <= 500000) return 0;
  return tax;
}

/** Section 87A rebate — new regime: up to ₹7L income, rebate up to ₹25,000 */
function applyNewRebate(tax: number, taxableIncome: number): number {
  if (taxableIncome <= 700000) return 0;
  return tax;
}

export function calculateTax(input: TaxCalcInput): TaxCalcResult {
  const { income, age, deductions80C, deductions80D, otherDeductions, homeLoanInterest } = input;

  // ---- OLD REGIME ----
  const totalDeductions = Math.min(deductions80C, 150000)   // 80C cap
                        + Math.min(deductions80D, 25000)    // 80D (simplified)
                        + otherDeductions
                        + Math.min(homeLoanInterest, 200000); // 24(b) cap
  const standardDeductionOld = 50000; // salaried
  const oldTaxableIncome = Math.max(0, income - standardDeductionOld - totalDeductions);
  const oldSlabSet = age === "below60" ? OLD_BELOW60 : age === "60to80" ? OLD_60TO80 : OLD_ABOVE80;
  const { total: oldRaw, breakdown: oldBreakdown } = computeTaxFromSlabs(oldTaxableIncome, oldSlabSet);
  const oldAfterRebate = applyOldRebate(oldRaw, oldTaxableIncome);
  const oldRegimeTax   = withCess(oldAfterRebate);

  // ---- NEW REGIME ----
  const standardDeductionNew = 75000; // FY 2024-25 budget enhancement
  const newTaxableIncome = Math.max(0, income - standardDeductionNew);
  const { total: newRaw, breakdown: newBreakdown } = computeTaxFromSlabs(newTaxableIncome, NEW_REGIME);
  const newAfterRebate = applyNewRebate(newRaw, newTaxableIncome);
  const newRegimeTax   = withCess(newAfterRebate);

  const saving = Math.abs(oldRegimeTax - newRegimeTax);
  const recommendation = oldRegimeTax <= newRegimeTax ? "old" : "new";

  return {
    oldRegimeTax,
    newRegimeTax,
    oldRegimeSlabs: oldBreakdown,
    newRegimeSlabs: newBreakdown,
    recommendation,
    saving,
  };
}
