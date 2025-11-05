"use client";

import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import { Tooltip } from "@/components/ui/tooltip";
import { AppConfig } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  BarVisualizer,
  useRemoteParticipants,
} from "@livekit/components-react";
import { useTranslation } from "@/lib/use-translation";
import {
  ChatTextIcon,
  PhoneDisconnectIcon,
} from "@phosphor-icons/react/dist/ssr";
import { Track } from "livekit-client";
import * as React from "react";
import { useCallback } from "react";
import { DeviceSelect } from "../device-select";
import { TrackToggle } from "../track-toggle";
import {
  UseAgentControlBarProps,
  useAgentControlBar,
} from "./hooks/use-agent-control-bar";
import { LanguageBadge } from "@/components/language-badge";
import { MessageInput } from "../message-input";

export interface AgentControlBarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    UseAgentControlBarProps {
  capabilities: Pick<
    AppConfig,
    "supportsChatInput" | "supportsVideoInput" | "supportsScreenShare"
  >;
  onChatOpenChange?: (open: boolean) => void;
  onSendMessage?: (message: string) => Promise<void>;
  onDisconnect?: () => void;
  onDeviceError?: (error: { source: Track.Source; error: Error }) => void;
  showMessageInput?: boolean;
  messageInputDisabled?: boolean;
  messageInputPlaceholder?: string;
}

/**
 * A control bar specifically designed for voice assistant interfaces
 */
export function AgentControlBar({
  controls,
  saveUserChoices = true,
  capabilities,
  className,
  onSendMessage,
  onChatOpenChange,
  onDisconnect,
  onDeviceError,
  showMessageInput = false,
  messageInputDisabled = false,
  messageInputPlaceholder = "Type your message ...",
  ...props
}: AgentControlBarProps) {
  const participants = useRemoteParticipants();
  const [chatOpen, setChatOpen] = React.useState(false);
  const { t, isRTL } = useTranslation();

  const isAgentAvailable = participants.some((p) => p.isAgent);

  const [isDisconnecting, setIsDisconnecting] = React.useState(false);

  const {
    micTrackRef,
    visibleControls,
    cameraToggle,
    microphoneToggle,
    handleAudioDeviceChange,
    handleVideoDeviceChange,
    handleDisconnect,
  } = useAgentControlBar({
    controls,
    saveUserChoices,
  });

  const onLeave = async () => {
    setIsDisconnecting(true);
    await handleDisconnect();
    setIsDisconnecting(false);
    onDisconnect?.();
  };

  React.useEffect(() => {
    onChatOpenChange?.(chatOpen);
  }, [chatOpen, onChatOpenChange]);

  const onMicrophoneDeviceSelectError = useCallback(
    (error: Error) => {
      onDeviceError?.({ source: Track.Source.Microphone, error });
    },
    [onDeviceError],
  );
  const onCameraDeviceSelectError = useCallback(
    (error: Error) => {
      onDeviceError?.({ source: Track.Source.Camera, error });
    },
    [onDeviceError],
  );

  return (
    <div
      aria-label={t("VOICE_ASSISTANT_CONTROLS")}
      className={cn(
        "bg-background border-bg2 dark:border-separator1 flex flex-col rounded-[31px] border p-3 drop-shadow-md/3",
        // Force LTR layout for consistent toolbar structure
        "toolbar-ltr-layout",
        className,
      )}
      style={{ direction: 'ltr' }}
      {...props}
    >
      <div className={cn(
        "flex items-center justify-between gap-2",
        // Force consistent layout order regardless of RTL
        "flex-row"
      )}>
        {/* Left side controls - always on the left */}
        <div className={cn(
          "flex gap-1",
          // Ensure consistent ordering within this group
          "flex-row"
        )}>
          {visibleControls.microphone && (
            <Tooltip content={t("MICROPHONE")} side="top">
              <div className="flex items-center gap-0">
                <TrackToggle
                  variant="primary"
                  source={Track.Source.Microphone}
                  pressed={microphoneToggle.enabled}
                  disabled={microphoneToggle.pending}
                  onPressedChange={microphoneToggle.toggle}
                  className="peer/track group/track relative w-auto pr-3 pl-3 md:rounded-r-none md:border-r-0 md:pr-2"
                >
                  <BarVisualizer
                    barCount={3}
                    trackRef={micTrackRef}
                    options={{ minHeight: 5 }}
                    className="flex h-full w-auto items-center justify-center gap-0.5"
                  >
                    <span
                      className={cn([
                        "h-full w-0.5 origin-center rounded-2xl",
                        "group-data-[state=on]/track:bg-fg1 group-data-[state=off]/track:bg-destructive-foreground",
                        "data-lk-muted:bg-muted",
                      ])}
                    ></span>
                  </BarVisualizer>
                </TrackToggle>
                <hr className="bg-separator1 peer-data-[state=off]/track:bg-separatorSerious relative z-10 -mr-px hidden h-4 w-px md:block" />
                <DeviceSelect
                  size="sm"
                  kind="audioinput"
                  requestPermissions={false}
                  onMediaDeviceError={onMicrophoneDeviceSelectError}
                  onActiveDeviceChange={handleAudioDeviceChange}
                  className={cn([
                    "pl-2",
                    "peer-data-[state=off]/track:text-destructive-foreground",
                    "hover:text-fg1 focus:text-fg1",
                    "hover:peer-data-[state=off]/track:text-destructive-foreground focus:peer-data-[state=off]/track:text-destructive-foreground",
                    "hidden rounded-l-none md:block",
                  ])}
                />
              </div>
            </Tooltip>
          )}

          {visibleControls.chat && (
            <Tooltip content={t("CHAT_HISTORY")} side="top">
              <Toggle
                variant="secondary"
                aria-label={t("TOGGLE_CHAT")}
                pressed={chatOpen}
                onPressedChange={setChatOpen}
                disabled={!isAgentAvailable}
                className="aspect-square h-full"
              >
                <ChatTextIcon weight="bold" />
              </Toggle>
            </Tooltip>
          )}
        </div>

        {/* Message Input - Center */}
        {showMessageInput && onSendMessage && (
          <MessageInput
            inline
            onSend={onSendMessage}
            disabled={messageInputDisabled}
            placeholder={messageInputPlaceholder || t("MESSAGE_PLACEHOLDER")}
            showInputField={true}
            className="flex-1"
          />
        )}

        {/* Right side controls - always on the right */}
        <div className={cn(
          "flex items-center gap-2",
          // Ensure consistent ordering within this group
          "flex-row"
        )}>
          <LanguageBadge />
          {visibleControls.leave && (
            <Button
              variant="destructive"
              onClick={onLeave}
              disabled={isDisconnecting}
              className={cn("font-mono", isRTL && "font-sans")}
              dir={isRTL ? "rtl" : "ltr"}
            >
              <PhoneDisconnectIcon weight="bold" />
              <span className="hidden md:inline">{t("END_CALL")}</span>
              <span className="inline md:hidden">{t("END_CALL_SHORT")}</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
