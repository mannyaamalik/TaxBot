"use client";
import { useReducedMotion } from "framer-motion";

/** Gate all animations behind prefers-reduced-motion. */
export function useMotionSafe() {
  const reduced = useReducedMotion();
  return {
    duration: (d: number) => (reduced ? 0 : d),
    animate:  (variants: object) => (reduced ? {} : variants),
    reduced:  !!reduced,
  };
}
