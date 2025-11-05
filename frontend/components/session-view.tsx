"use client";

import { toastAlert } from "@/components/alert-toast";
import { AgentControlBar } from "@/components/livekit/agent-control-bar/agent-control-bar";
import { ChatEntry } from "@/components/livekit/chat/chat-entry";
import { ChatMessageView } from "@/components/livekit/chat/chat-message-view";
import { MediaTiles } from "@/components/livekit/media-tiles";
import useChatAndTranscription from "@/hooks/useChatAndTranscription";
import { useDebugMode } from "@/hooks/useDebug";
import type { AppConfig } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  type AgentState,
  type ReceivedChatMessage,
  useRoomContext,
  useVoiceAssistant,
} from "@livekit/components-react";
import { AnimatePresence, motion } from "motion/react";
import React, { useEffect, useState } from "react";

function isAgentAvailable(agentState: AgentState) {
  return (
    agentState == "listening" ||
    agentState == "thinking" ||
    agentState == "speaking"
  );
}

interface SessionViewProps {
  appConfig: AppConfig;
  disabled: boolean;
  sessionStarted: boolean;
  isPopupMode?: boolean;
  selectedVoice?: string;
  onVoiceChange?: (voice: string) => void;
}

export const SessionView = ({
  appConfig,
  disabled,
  sessionStarted,
  isPopupMode = false,
  selectedVoice,
  onVoiceChange,
  ref,
}: React.ComponentProps<"div"> & SessionViewProps) => {
  const { state: agentState } = useVoiceAssistant();
  const [chatOpen, setChatOpen] = useState(false);
  const { messages, send } = useChatAndTranscription();
  const room = useRoomContext();
  const [isLoading, setIsLoading] = useState(false);

  // Track if user is speaking (agent is listening)
  const isUserSpeaking = agentState === "listening";

  // Loading state effect - show "Loading..." for 6 seconds when session starts
  useEffect(() => {
    if (sessionStarted) {
      setIsLoading(true);
      const timer = setTimeout(() => {
        setIsLoading(false);
      }, 6000); // 6 seconds
      return () => clearTimeout(timer);
    }
  }, [sessionStarted]);

  useDebugMode({
    enabled: process.env.NODE_END !== "production",
  });

  async function handleSendMessage(message: string) {
    await send(message);
  }

  // When user speaks, close chat mode to show centered waveform
  useEffect(() => {
    if (isPopupMode && chatOpen && isUserSpeaking) {
      setChatOpen(false);
    }
  }, [isUserSpeaking, isPopupMode, chatOpen]);

  useEffect(() => {
    if (sessionStarted) {
      const timeout = setTimeout(() => {
        if (!isAgentAvailable(agentState)) {
          const reason =
            agentState === "connecting"
              ? "Agent did not join the room. "
              : "Agent connected but did not complete initializing. ";

          toastAlert({
            title: "Session ended",
            description: (
              <p className="w-full">
                {reason}
                Please try again or check your connection.
              </p>
            ),
          });
          room.disconnect();
        }
      }, 20_000);

      return () => clearTimeout(timeout);
    }
  }, [agentState, sessionStarted, room]);

  const { supportsChatInput, supportsVideoInput, supportsScreenShare } =
    appConfig;
  const capabilities = {
    supportsChatInput,
    supportsVideoInput,
    supportsScreenShare,
  };

  if (isPopupMode) {
    return (
      <section
        ref={ref}
        inert={disabled}
        className="relative flex h-full w-full flex-col overflow-hidden"
      >
        {/* Content Area */}
        <div className="relative flex flex-1 flex-col overflow-hidden">
          {/* Chat Messages - only shown when chatOpen */}
          <AnimatePresence>
            {chatOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="absolute inset-0 z-30 flex flex-col bg-background"
              >
                <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2">
                  <ChatMessageView className="min-h-full">
                    <div className="space-y-3 whitespace-pre-wrap">
                      <AnimatePresence>
                        {messages.map((message: ReceivedChatMessage) => (
                          <motion.div
                            key={message.id}
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{
                              opacity: 1,
                              height: "auto",
                              translateY: 0.001,
                            }}
                            transition={{ duration: 0.5, ease: "easeOut" }}
                          >
                            <ChatEntry
                              hideName
                              key={message.id}
                              entry={message}
                            />
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </div>
                  </ChatMessageView>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Agent Tile - smoothly transitions between center and corner */}
          <motion.div
            className="absolute z-50"
            initial={false}
            animate={{
              left: chatOpen ? "calc(100% - 208px)" : "50%",
              top: chatOpen ? "calc(100% - 208px)" : "50%",
              x: chatOpen ? 0 : "-50%",
              y: chatOpen ? 0 : "-50%",
            }}
            transition={{
              type: "spring",
              stiffness: 200,
              damping: 35,
              mass: 0.5,
              restSpeed: 0.01,
              restDelta: 0.01,
            }}
            style={{
              willChange: "transform",
            }}
          >
            <MediaTiles chatOpen={chatOpen} isPopupMode={isPopupMode} />
          </motion.div>

          {/* Helper text - only shown when not in chat mode */}
          {!chatOpen && appConfig.isPreConnectBufferEnabled && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{
                opacity: sessionStarted && messages.length === 0 ? 1 : 0,
                transition: {
                  ease: "easeIn",
                  delay: messages.length > 0 ? 0 : 0.8,
                  duration: messages.length > 0 ? 0.2 : 0.5,
                },
              }}
              aria-hidden={messages.length > 0}
              className="absolute bottom-[140px] left-0 right-0 z-10 text-center text-xs text-muted-foreground"
            >
              <p className="animate-text-shimmer inline-block !bg-clip-text font-semibold text-transparent">
                {isLoading
                  ? "Initializing a new session..."
                  : "Agent is listening, ask it a question and start going!"}
              </p>
            </motion.div>
          )}
        </div>

        {/* Control Bar - Always at Bottom */}
        <motion.div
          key="control-bar"
          initial={{ opacity: 0, translateY: "100%" }}
          animate={{
            opacity: sessionStarted ? 1 : 0,
            translateY: sessionStarted ? "0%" : "100%",
          }}
          transition={{
            duration: 0.3,
            delay: sessionStarted ? 0.5 : 0,
            ease: "easeOut",
          }}
          className="relative border-t border-border bg-background p-3"
        >
          <AgentControlBar
            capabilities={capabilities}
            onChatOpenChange={setChatOpen}
            onSendMessage={handleSendMessage}
            showMessageInput={!chatOpen && sessionStarted}
            messageInputDisabled={!isAgentAvailable(agentState) || isLoading}
            messageInputPlaceholder="Type your message ..."
          />
        </motion.div>
      </section>
    );
  }

  return (
    <section
      ref={ref}
      inert={disabled}
      className={cn(
        "opacity-0",
        // prevent page scrollbar
        // when !chatOpen due to 'translate-y-20'
        !chatOpen && "max-h-svh overflow-hidden",
      )}
    >
      <ChatMessageView
        className={cn(
          "mx-auto min-h-svh w-full max-w-2xl px-3 pt-32 pb-40 transition-[opacity,translate] duration-300 ease-out md:px-0 md:pt-36 md:pb-48",
          chatOpen
            ? "translate-y-0 opacity-100 delay-200"
            : "translate-y-20 opacity-0",
        )}
      >
        <div className="space-y-3 whitespace-pre-wrap">
          <AnimatePresence>
            {messages.map((message: ReceivedChatMessage) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 1, height: "auto", translateY: 0.001 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              >
                <ChatEntry hideName key={message.id} entry={message} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </ChatMessageView>

      <div className="bg-background mp-12 fixed top-0 right-0 left-0 h-32 md:h-36">
        {/* skrim */}
        <div className="from-background absolute bottom-0 left-0 h-12 w-full translate-y-full bg-gradient-to-b to-transparent" />
      </div>

      <MediaTiles chatOpen={chatOpen} />

      <div className="bg-background fixed right-0 bottom-0 left-0 z-50 px-3 pt-2 pb-3 md:px-12 md:pb-12">
        <motion.div
          key="control-bar"
          initial={{ opacity: 0, translateY: "100%" }}
          animate={{
            opacity: sessionStarted ? 1 : 0,
            translateY: sessionStarted ? "0%" : "100%",
          }}
          transition={{
            duration: 0.3,
            delay: sessionStarted ? 0.5 : 0,
            ease: "easeOut",
          }}
        >
          <div className="relative z-10 mx-auto w-full max-w-2xl">
            {appConfig.isPreConnectBufferEnabled && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{
                  opacity: sessionStarted && messages.length === 0 ? 1 : 0,
                  transition: {
                    ease: "easeIn",
                    delay: messages.length > 0 ? 0 : 0.8,
                    duration: messages.length > 0 ? 0.2 : 0.5,
                  },
                }}
                aria-hidden={messages.length > 0}
                className={cn(
                  "absolute inset-x-0 -top-12 text-center",
                  sessionStarted &&
                    messages.length === 0 &&
                    "pointer-events-none",
                )}
              >
                <p className="animate-text-shimmer inline-block !bg-clip-text text-sm font-semibold text-transparent">
                  {isLoading
                    ? "Initializing a new session..."
                    : "Agent is listening, ask it a question and start going!"}
                </p>
              </motion.div>
            )}

            <AgentControlBar
              capabilities={capabilities}
              onChatOpenChange={setChatOpen}
              onSendMessage={handleSendMessage}
              showMessageInput={!chatOpen && sessionStarted}
              messageInputDisabled={!isAgentAvailable(agentState) || isLoading}
              messageInputPlaceholder="Type your message ..."
            />
          </div>
          {/* skrim */}
          <div className="from-background border-background absolute top-0 left-0 h-12 w-full -translate-y-full bg-gradient-to-t to-transparent" />
        </motion.div>
      </div>
    </section>
  );
};
