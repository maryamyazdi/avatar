"use client";

import { useLanguage } from "@/lib/language-context";
import { motion } from "motion/react";

const FLAGS = {
  fa: "/flag-iran.svg",
  en: "/flag-usa.svg",
};

const LABELS = {
  fa: "Fa",
  en: "En",
};

interface LanguageBadgeProps {
  className?: string;
}

export function LanguageBadge({ className = "" }: LanguageBadgeProps) {
  const { language } = useLanguage();

  return (
    <motion.div
      className={`flex items-center gap-1.5 rounded-full bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm px-2.5 py-2 shadow-md border border-gray-200/60 dark:border-gray-600/60 h-10 ${className}`}
      style={{
        boxShadow: "0 2px 6px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08)",
      }}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      <motion.div
        className="flex items-center justify-center w-4 h-4 rounded-sm overflow-hidden flex-shrink-0"
        key={language}
        initial={{ scale: 0.8, opacity: 0, rotate: -10 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        <img
          src={FLAGS[language]}
          alt={`${language === "fa" ? "Iran" : "USA"} flag`}
          className="w-full h-full object-cover"
          style={{ imageRendering: "crisp-edges" }}
        />
      </motion.div>
      <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 leading-none tracking-tight whitespace-nowrap">
        {LABELS[language]}
      </span>
    </motion.div>
  );
}

