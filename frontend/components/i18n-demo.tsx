"use client";

import { useTranslation } from "@/lib/use-translation";
import { useLanguage } from "@/lib/language-context";
import { Button } from "@/components/ui/button";

/**
 * Demo component to showcase i18n functionality
 * This component demonstrates how all UI text changes when language is switched
 */
export function I18nDemo() {
  const { t, isRTL } = useTranslation();
  const { language, setLanguage } = useLanguage();

  const toggleLanguage = () => {
    setLanguage(language === "fa" ? "en" : "fa");
  };

  return (
    <div 
      className="p-6 max-w-md mx-auto bg-white dark:bg-gray-800 rounded-lg shadow-lg"
      dir={isRTL ? "rtl" : "ltr"}
    >
      <h2 className="text-xl font-bold mb-4 tracking-wide">
        {t("WELCOME_TITLE")}
      </h2>
      
      <p className="mb-4 text-gray-600 dark:text-gray-300 font-medium">
        {t("WELCOME_FOOTER")}
      </p>
      
      <div className="space-y-3">
        <Button 
          onClick={toggleLanguage}
          className="w-full"
        >
          {language === "fa" ? t("SWITCH_TO_ENGLISH") : t("SWITCH_TO_PERSIAN")}
        </Button>
        
        <div className="text-sm text-gray-500 dark:text-gray-400">
          <p><strong>{t("MICROPHONE")}:</strong> {t("AGENT_AVAILABLE")}</p>
          <p><strong>{t("CHAT_HISTORY")}:</strong> {t("LOADING")}</p>
          <p><strong>{t("MESSAGE_PLACEHOLDER")}:</strong> {t("HAVE_QUESTIONS")}</p>
        </div>
      </div>
      
      <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-700 rounded">
        <p className="text-xs mb-2">
          <strong>Current Language:</strong> {language.toUpperCase()} | 
          <strong> RTL:</strong> {isRTL ? "Yes" : "No"}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          <strong>Font:</strong> {isRTL ? "Vazirmatn (Persian)" : "Poppins (English)"}
        </p>
      </div>
      
      {/* Font Sample */}
      <div className="mt-4 p-3 border border-gray-200 dark:border-gray-600 rounded">
        <h3 className="text-sm font-semibold mb-2">Font Sample:</h3>
        <p className="text-lg font-medium mb-1">
          {language === "fa" ? "نمونه متن فارسی با فونت وزیرمتن" : "English text sample with Poppins font"}
        </p>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {language === "fa" ? "این متن برای نمایش زیبایی فونت فارسی است" : "This text showcases the English font beauty"}
        </p>
      </div>
    </div>
  );
}
