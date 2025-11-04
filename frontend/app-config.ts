import type { AppConfig } from "./lib/types";

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: "TechCo",
  pageTitle: "Home - TechCo",
  pageDescription: "A modern digital experience platform",

  supportsChatInput: true,
  supportsVideoInput: true,
  supportsScreenShare: true,
  isPreConnectBufferEnabled: true,

  logo: "demis2.png",
  // accent: '#4FC3F7',
  logoDark: "/demis2.png",
  // accentDark: '#4DB6AC',
  startButtonText: "Start call",

  agentName: undefined,
};
