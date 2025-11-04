"use client";

import { useLanguage, type Language } from "@/lib/language-context";
import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";

const FLAGS = {
  fa: "/flag-iran.svg",
  en: "/flag-usa.svg",
};

const LABELS = {
  fa: "Fa",
  en: "En",
};

export function LanguageSelector() {
  const { language, setLanguage } = useLanguage();

  const toggleLanguage = () => {
    setLanguage(language === "fa" ? "en" : "fa");
  };

  return (
    <motion.button
      onClick={toggleLanguage}
      className="flex items-center gap-1 rounded-full bg-white/95 dark:bg-gray-800/95 backdrop-blur-sm px-1.5 py-0.5 shadow-md transition-all hover:shadow-lg border border-gray-200/60 dark:border-gray-600/60"
      style={{
        boxShadow: "0 2px 6px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08)",
      }}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.95 }}
      aria-label={`Switch to ${language === "fa" ? "English" : "Persian"}`}
    >
      <motion.div
        className="flex items-center justify-center w-3.5 h-3.5 rounded-sm overflow-hidden"
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
      <span className="text-[10px] font-semibold text-gray-800 dark:text-gray-200 leading-none tracking-tight">
        {LABELS[language]}
      </span>
    </motion.button>
  );
}

