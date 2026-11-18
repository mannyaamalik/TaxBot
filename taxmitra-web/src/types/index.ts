/** Shared TypeScript types for TaxMitra. */

export interface SourceItem {
  doc_title:       string;
  section_heading: string;
  page_number:     number;
  filename:        string;
  assessment_year: string;
}

export interface ChatRequest {
  question:   string;
  session_id: string | null;
  language?:  "en" | "hi";
}

export interface ChatResponse {
  answer:              string;
  sources:             SourceItem[];
  session_id:          string;
  not_found:           boolean;
  needs_clarification?: boolean;
}

export type MessageStatus = "normal" | "not_found" | "clarification" | "out_of_scope" | "error";

export interface Message {
  id:         string;
  role:       "user" | "assistant";
  content:    string;
  status:     MessageStatus;
  sources:    SourceItem[];
  timestamp:  Date;
  streaming?: boolean;
}

export interface ChatSession {
  id:         string;
  title:      string;
  messages:   Message[];
  createdAt:  Date;
  updatedAt:  Date;
  session_id: string; // backend session id
}

export type Category =
  | "all"
  | "income-tax"
  | "gst"
  | "tds"
  | "capital-gains"
  | "deductions"
  | "itr-filing";

export interface SuggestedQuestion {
  id:       string;
  text:     string;
  category: Category;
  icon:     string;
}

export type FeedbackType = "up" | "down";

export interface TaxCalcInput {
  income:         number;
  age:            "below60" | "60to80" | "above80";
  deductions80C:  number;
  deductions80D:  number;
  otherDeductions: number;
  homeLoanInterest: number;
}

export interface TaxCalcResult {
  oldRegimeTax:    number;
  newRegimeTax:    number;
  oldRegimeSlabs:  { slab: string; rate: number; tax: number }[];
  newRegimeSlabs:  { slab: string; rate: number; tax: number }[];
  recommendation:  "old" | "new";
  saving:          number;
}

export interface ToastMessage {
  id:      string;
  type:    "success" | "error" | "warning" | "info";
  title:   string;
  message?: string;
}
