/** Shared Framer Motion constants — import from here, never hard-code. */

export const EASING = {
  enter:  [0.0, 0.0, 0.2, 1.0] as const,
  exit:   [0.4, 0.0, 1.0, 1.0] as const,
  spring: { type: "spring" as const, stiffness: 300, damping: 30 },
};

export const DURATION = {
  fast:  0.15,
  base:  0.25,
  slow:  0.40,
};

export const fadeUp = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0,  transition: { duration: DURATION.base, ease: EASING.enter } },
  exit:    { opacity: 0, y: -8, transition: { duration: DURATION.fast,  ease: EASING.exit  } },
};

export const fadeIn = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: DURATION.base, ease: EASING.enter } },
  exit:    { opacity: 0, transition: { duration: DURATION.fast,  ease: EASING.exit  } },
};

export const slideRight = {
  hidden:  { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0,   transition: { duration: DURATION.base, ease: EASING.enter } },
  exit:    { opacity: 0, x: -20, transition: { duration: DURATION.fast,  ease: EASING.exit  } },
};

export const slideLeft = {
  hidden:  { opacity: 0, x: 20 },
  visible: { opacity: 1, x: 0,   transition: { duration: DURATION.base, ease: EASING.enter } },
  exit:    { opacity: 0, x: 20,  transition: { duration: DURATION.fast,  ease: EASING.exit  } },
};

export const scaleIn = {
  hidden:  { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1,   transition: { ...EASING.spring } },
  exit:    { opacity: 0, scale: 0.95, transition: { duration: DURATION.fast, ease: EASING.exit } },
};

export const staggerContainer = (stagger = 0.07) => ({
  hidden:  {},
  visible: { transition: { staggerChildren: stagger } },
});
