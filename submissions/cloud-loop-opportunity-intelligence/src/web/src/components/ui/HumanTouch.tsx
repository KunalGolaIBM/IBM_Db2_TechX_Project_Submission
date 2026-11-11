"use client";

import { motion } from "framer-motion";

/**
 * A subtle "Made with ♥ by humans" badge rendered in a handwriting-style font,
 * adding a personal, non-AI-generated feel to the interface.
 */
export function HumanTouchBadge() {
  return (
    <motion.div
      initial={{ opacity: 0, rotate: -3, scale: 0.9 }}
      animate={{ opacity: 1, rotate: -2, scale: 1 }}
      transition={{ duration: 0.6, delay: 1.2, ease: "easeOut" }}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
        bg-white/70 dark:bg-white/5 border border-dashed border-primary/40
        text-[11px] font-medium text-text-secondary dark:text-dark-text-secondary
        shadow-sm backdrop-blur-sm select-none cursor-default hover:rotate-0
        transition-transform duration-300"
      style={{ fontFamily: "'Caveat', 'Segoe Script', cursive" }}
      title="Built with care by real humans 🤍"
    >
      <span className="text-base">✍️</span>
      <span>crafted by humans, not AI</span>
    </motion.div>
  );
}

/**
 * Small inline annotation-style tag for section headers 
 */
export function HandwrittenNote({ text }: { text: string }) {
  return (
    <span
      className="inline-block px-2 py-0.5 text-[10px] text-primary/70 dark:text-primary/60
        border border-dashed border-primary/30 rounded-md rotate-[-1deg]
        font-medium ml-2 align-middle"
      style={{ fontFamily: "'Caveat', 'Segoe Script', cursive" }}
    >
      {text}
    </span>
  );
}
