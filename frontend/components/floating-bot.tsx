"use client";

import { toastAlert } from "@/components/alert-toast";
import { Toaster } from "@/components/ui/sonner";
import useConnectionDetails from "@/hooks/useConnectionDetails";
import type { AppConfig } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  RoomAudioRenderer,
  RoomContext,
  StartAudio,
} from "@livekit/components-react";
import { ChatCircle, X } from "@phosphor-icons/react/dist/ssr";
import { Room, RoomEvent } from "livekit-client";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { SessionView } from "./session-view";
import { LanguageSelector } from "./language-selector";
import { useLanguage } from "@/lib/language-context";
import { useTranslation } from "@/lib/use-translation";

// 🔄 Shared pulse animation for avatar + speech bubble
const pulseSync = {
  animate: {
    scale: [1, 1.08, 1],
  },
  transition: {
    duration: 2.5,
    repeat: Infinity,
    ease: "easeInOut",
  },
};

// Avatar Slideshow Component
function AvatarSlideshow() {
  const avatarImages = ["/button-icon2.png", "/button-icon4.png"];
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex(
        (prevIndex: number) => (prevIndex + 1) % avatarImages.length,
      );
    }, 4500);
    return () => clearInterval(interval);
  }, [avatarImages.length]);

  return (
    <div className="relative w-full h-full overflow-hidden rounded-full">
      {avatarImages.map((src, index) => (
        <motion.div
          key={src}
          className="absolute inset-0 overflow-hidden rounded-full"
          initial={{ opacity: 0 }}
          animate={{
            opacity: currentIndex === index ? 1 : 0,
            scale: currentIndex === index ? [1, 1.05, 1] : 1,
          }}
          transition={{
            opacity: { duration: 0.75, ease: "easeInOut" },
            scale: { duration: 5, ease: "easeInOut", repeat: Infinity },
          }}
        >
          <img
            src={src}
            alt={`AI Avatar ${index + 1}`}
            className="w-full h-full rounded-full object-cover"
            style={{ boxShadow: "0 10px 40px rgba(239, 59, 86, 0.3)" }}
          />
        </motion.div>
      ))}
    </div>
  );
}

export function FloatingBot({ appConfig }: { appConfig: AppConfig }) {
  const room = useMemo(() => new Room(), []);
  const [isOpen, setIsOpen] = useState(false);
  const [sessionStarted, setSessionStarted] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState(
    appConfig.defaultTTSVoice || "",
  );
  const { language } = useLanguage();
  const { t, isRTL } = useTranslation();
  const { refreshConnectionDetails, existingOrRefreshConnectionDetails } =
    useConnectionDetails(appConfig, language);

  useEffect(() => {
    const onDisconnected = () => {
      setSessionStarted(false);
      setIsOpen(false);
      refreshConnectionDetails();
    };
    const onMediaDevicesError = (error: Error) => {
      toastAlert({
        title: t("MEDIA_DEVICES_ERROR"),
        description: `${error.name}: ${error.message}`,
      });
    };
    room.on(RoomEvent.MediaDevicesError, onMediaDevicesError);
    room.on(RoomEvent.Disconnected, onDisconnected);
    return () => {
      room.off(RoomEvent.Disconnected, onDisconnected);
      room.off(RoomEvent.MediaDevicesError, onMediaDevicesError);
    };
  }, [room, refreshConnectionDetails]);

  useEffect(() => {
    let aborted = false;

    // Only connect if session is starting for the first time
    if (sessionStarted && room.state === "disconnected") {
      Promise.all([
        room.localParticipant.setMicrophoneEnabled(true, undefined, {
          preConnectBuffer: appConfig.isPreConnectBufferEnabled,
        }),
        existingOrRefreshConnectionDetails().then((connectionDetails) =>
          room.connect(
            connectionDetails.serverUrl,
            connectionDetails.participantToken,
          ),
        ),
      ]).catch((error) => {
        if (aborted) return;
        toastAlert({
          title: t("CONNECTION_ERROR_TITLE"),
          description: `${error.name}: ${error.message}`,
        });
      });
    }

    // Cleanup only on component unmount (page refresh/navigation)
    return () => {
      aborted = true;
      if (room.state === "connected") {
        room.localParticipant
          .setMicrophoneEnabled(false)
          .then(() => room.disconnect())
          .catch((error) =>
            console.error("Error during page unload cleanup:", error),
          );
      }
    };
  }, [
    room,
    sessionStarted,
    appConfig.isPreConnectBufferEnabled,
    existingOrRefreshConnectionDetails,
  ]);

  useEffect(() => {
    if (sessionStarted && room.state === "connected" && selectedVoice) {
      const encoder = new TextEncoder();
      const data = encoder.encode(
        JSON.stringify({ type: "voice_config", voice: selectedVoice }),
      );
      room.localParticipant.publishData(data, { reliable: true });
    }
  }, [sessionStarted, room.state, selectedVoice, room.localParticipant]);

  const handleToggle = async () => {
    if (!isOpen) {
      // Opening chat window
      setIsOpen(true);
      if (!sessionStarted) {
        // Only start session if it hasn't been started yet (first time or after page refresh)
        setSessionStarted(true);
      } else {
        // Re-enable microphone for existing session
        try {
          await room.localParticipant.setMicrophoneEnabled(true);
        } catch (error) {
          console.error("Error enabling microphone:", error);
        }
      }
      window.parent.postMessage({ type: "assistant", action: "open" }, "*");
    } else {
      // Closing chat window - only disable microphone, keep session alive
      try {
        await room.localParticipant.setMicrophoneEnabled(false);
      } catch (error) {
        console.error("Error disabling microphone:", error);
      }
      setIsOpen(false);
      window.parent.postMessage({ type: "assistant", action: "close" }, "*");
    }
  };

  return (
    <>
      {/* Floating Action Button + Speech Bubble + Language Selector */}
      <div className="fixed right-6 bottom-6 z-[100]">
        <div className="relative inline-block">
          {/* 🗨️ Speech Bubble */}
          {!isOpen && (
            <motion.div
              className="pointer-events-none absolute whitespace-nowrap rounded-2xl px-5 py-3 text-sm font-medium text-white shadow-2xl"
              style={{
                background:
                  "linear-gradient(135deg, var(--secondary-blue) 0%, rgba(102,155,209,0.9) 100%)",
                bottom: "calc(100% - 12px)",
                right: "calc(100% - 12px)",
              }}
              animate={pulseSync.animate}
              transition={pulseSync.transition}
              dir={isRTL ? "rtl" : "ltr"}
              lang={isRTL ? "fa" : "en"}
            >
              <span className="relative z-10">{t("HAVE_QUESTIONS")}</span>
              {/* 🟢 Speech Bubble Corner */}
              <div
                className="absolute bottom-[-8px] right-4 w-0 h-0"
                style={{
                  borderLeft: "10px solid transparent",
                  borderRight: "10px solid transparent",
                  borderTop: "10px solid var(--secondary-blue)",
                  filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.15))",
                }}
              />
              <div
                className="absolute inset-0 rounded-2xl opacity-40 blur-md"
                style={{ backgroundColor: "var(--secondary-blue)", zIndex: -1 }}
              />
            </motion.div>
          )}

          {/* 🤖 Avatar Button with Language Selector */}
          <div className="relative">
            <motion.button
              onClick={handleToggle}
              className={cn(
                "flex h-18 w-18 items-center justify-center rounded-full shadow-2xl transition-all overflow-hidden border-2",
                isOpen ? "border-border" : "border-white",
              )}
              style={{
                backgroundColor: "var(--primary-red)",
                boxShadow: "0 10px 40px rgba(239, 59, 86, 0.6)",
              }}
              animate={!isOpen ? pulseSync.animate : {}}
              transition={pulseSync.transition}
              aria-label={isOpen ? t("CLOSE_CHAT") : t("OPEN_CHAT")}
            >
              <AnimatePresence mode="wait" initial={false}>
                {isOpen ? (
                  <motion.div
                    key="close"
                    initial={{ rotate: -90, opacity: 0 }}
                    animate={{ rotate: 0, opacity: 1 }}
                    exit={{ rotate: 90, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-white"
                  >
                    <X size={28} weight="bold" />
                  </motion.div>
                ) : (
                  <motion.div
                    key="open"
                    initial={{ rotate: 90, opacity: 0 }}
                    animate={{ rotate: 0, opacity: 1 }}
                    exit={{ rotate: -90, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center justify-center w-full h-full"
                  >
                    <img
                      src="/button-icon.png"
                      alt="Chat"
                      className="w-full h-full object-cover rounded-full"
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.button>

            {/* 🌐 Language Selector - tangent to bottom-left of avatar */}
            {!isOpen && (
              <motion.div
                className="pointer-events-auto absolute"
                style={{
                  bottom: "2px",
                  left: "-20px",
                }}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3, duration: 0.4 }}
              >
                <LanguageSelector />
              </motion.div>
            )}
          </div>
        </div>
      </div>

      {/* Popup */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="fixed inset-0 z-[98] bg-black/50 backdrop-blur-sm"
              onClick={handleToggle}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="fixed left-1/2 top-1/2 z-[99] h-[85vh] w-[90vw] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border border-border bg-background shadow-2xl"
              style={{
                maxHeight: "calc(100vh - 80px)",
                maxWidth: "calc(100vw - 80px)",
              }}
            >
              <RoomContext.Provider value={room}>
                <RoomAudioRenderer />
                <StartAudio label="Start Audio" />
                <SessionView
                  appConfig={appConfig}
                  disabled={!sessionStarted}
                  sessionStarted={sessionStarted}
                  isPopupMode={true}
                  selectedVoice={selectedVoice}
                  onVoiceChange={setSelectedVoice}
                />
              </RoomContext.Provider>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <Toaster />
    </>
  );
}
