"use client";

import { useTranslation } from "@/lib/use-translation";
import { useEffect } from "react";

interface LayoutWrapperProps {
  children: React.ReactNode;
}

/**
 * Client-side wrapper that applies RTL direction and language attributes
 * to the document based on the current language selection
 */
export function LayoutWrapper({ children }: LayoutWrapperProps) {
  const { language, isRTL } = useTranslation();

  useEffect(() => {
    // Update document direction and language
    document.documentElement.dir = isRTL ? "rtl" : "ltr";
    document.documentElement.lang = language;
  }, [language, isRTL]);

  return <>{children}</>;
}
