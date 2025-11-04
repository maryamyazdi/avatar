"use client";

import { FloatingBot } from "@/components/floating-bot";
import { Toaster } from "@/components/ui/sonner";
import type { AppConfig } from "@/lib/types";

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  return (
    <main>
      <FloatingBot appConfig={appConfig} />
      <Toaster />
    </main>
  );
}
