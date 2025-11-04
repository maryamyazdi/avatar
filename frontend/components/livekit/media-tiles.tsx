import { cn } from "@/lib/utils";
import {
  type TrackReference,
  useLocalParticipant,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { AnimatePresence, motion } from "motion/react";
import { useMemo } from "react";
import { AgentTile } from "./agent-tile";
import { AvatarTile } from "./avatar-tile";
import { StaticAvatar } from "./static-avatar";
import { VideoTile } from "./video-tile";

const MotionVideoTile = motion.create(VideoTile);
const MotionAgentTile = motion.create(AgentTile);
const MotionAvatarTile = motion.create(AvatarTile);
const MotionStaticAvatar = motion.create(StaticAvatar);

const animationProps = {
  initial: {
    opacity: 0,
    scale: 0,
  },
  animate: {
    opacity: 1,
    scale: 1,
  },
  exit: {
    opacity: 0,
    scale: 0,
  },
  transition: {
    type: "spring",
    stiffness: 675,
    damping: 75,
    mass: 1,
  },
};

const classNames = {
  // GRID
  // 2 Columns x 3 Rows
  grid: [
    "h-full w-full",
    "grid gap-x-2 place-content-center",
    "grid-cols-[1fr_1fr] grid-rows-[90px_1fr_90px]",
  ],
  // Agent
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 1 / Row 1
  // align: x-end y-center
  agentChatOpenWithSecondTile: [
    "col-start-1 row-start-1",
    "self-center justify-self-end",
  ],
  // Agent
  // chatOpen: true,
  // hasSecondTile: false
  // layout: Column 1 / Row 1 / Column-Span 2
  // align: x-center y-center
  agentChatOpenWithoutSecondTile: [
    "col-start-1 row-start-1",
    "col-span-2",
    "place-content-center",
  ],
  // Agent
  // chatOpen: false
  // layout: Column 1 / Row 1 / Column-Span 2 / Row-Span 3
  // align: x-center y-center
  agentChatClosed: [
    "col-start-1 row-start-1",
    "col-span-2 row-span-3",
    "place-content-center",
  ],
  // Second tile
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 2 / Row 1
  // align: x-start y-center
  secondTileChatOpen: [
    "col-start-2 row-start-1",
    "self-center justify-self-start",
  ],
  // Second tile
  // chatOpen: false,
  // hasSecondTile: false
  // layout: Column 2 / Row 2
  // align: x-end y-end
  secondTileChatClosed: ["col-start-2 row-start-3", "place-content-end"],
};

export function useLocalTrackRef(source: Track.Source) {
  const { localParticipant } = useLocalParticipant();
  const publication = localParticipant.getTrackPublication(source);
  const trackRef = useMemo<TrackReference | undefined>(
    () =>
      publication
        ? { source, participant: localParticipant, publication }
        : undefined,
    [source, publication, localParticipant],
  );
  return trackRef;
}

interface MediaTilesProps {
  chatOpen: boolean;
  isPopupMode?: boolean;
  onAvatarClick?: () => void;
}

export function MediaTiles({
  chatOpen,
  isPopupMode = false,
  onAvatarClick,
}: MediaTilesProps) {
  const {
    state: agentState,
    audioTrack: agentAudioTrack,
    videoTrack: agentVideoTrack,
  } = useVoiceAssistant();
  const cameraTrack: TrackReference | undefined = useLocalTrackRef(
    Track.Source.Camera,
  );

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const hasSecondTile = isCameraEnabled;

  const transition = {
    ...animationProps.transition,
    delay: chatOpen ? 0 : 0.15, // delay on close
  };
  const agentAnimate = {
    ...animationProps.animate,
    scale: chatOpen ? 1 : 4.5,
    transition,
  };
  const avatarAnimate = {
    ...animationProps.animate,
    transition,
  };
  const agentLayoutTransition = transition;
  const avatarLayoutTransition = transition;

  const isAvatar = agentVideoTrack !== undefined;

  // Popup Mode Rendering
  if (isPopupMode) {
    return (
      <AnimatePresence mode="wait">
        {!isAvatar && (
          // Static avatar for audio-only agent in popup mode
          <MotionStaticAvatar
            key="avatar-popup"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{
              opacity: { duration: 0.3 },
              scale: { duration: 0.3, ease: "easeOut" },
            }}
            state={agentState}
            onClick={onAvatarClick}
            className={cn(
              "overflow-hidden rounded-full",
              chatOpen
                ? "h-48 w-48"
                : "h-[240px] w-[240px] md:h-[400px] md:w-[400px]",
            )}
            style={{
              willChange: "transform",
              maxWidth: chatOpen ? undefined : "min(240px, 65vw)",
              maxHeight: chatOpen ? undefined : "min(240px, 65vw)",
            }}
          />
        )}
        {isAvatar && (
          // avatar agent
          <MotionAvatarTile
            key="avatar-popup"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{
              opacity: { duration: 0.3 },
              scale: { duration: 0.3, ease: "easeOut" },
            }}
            videoTrack={agentVideoTrack}
            onClick={onAvatarClick}
            className={cn(
              "overflow-hidden rounded-full",
              chatOpen
                ? "h-48 w-48 [&>video]:h-48 [&>video]:w-48 [&>video]:object-cover"
                : "h-[240px] w-[240px] md:h-[400px] md:w-[400px] [&>video]:h-full [&>video]:w-full [&>video]:object-cover",
            )}
            style={{
              willChange: "transform",
              maxWidth: chatOpen ? undefined : "min(240px, 65vw)",
              maxHeight: chatOpen ? undefined : "min(240px, 65vw)",
            }}
          />
        )}
        {/* Camera in popup mode - show as small circle when chat is closed */}
        {cameraTrack && isCameraEnabled && !chatOpen && (
          <MotionVideoTile
            key="camera-popup"
            layout="position"
            layoutId="camera-popup"
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0 }}
            trackRef={cameraTrack}
            transition={{
              type: "spring",
              stiffness: 400,
              damping: 35,
            }}
            className="absolute left-4 bottom-4 h-16 w-16 overflow-hidden rounded-full"
          />
        )}
      </AnimatePresence>
    );
  }

  // Full Page Mode Rendering
  return (
    <div className="pointer-events-none fixed inset-x-0 top-8 bottom-32 z-50 md:top-12 md:bottom-40">
      <div className="relative mx-auto h-full max-w-2xl px-4 md:px-0">
        <div className={cn(classNames.grid)}>
          {/* agent */}
          <div
            className={cn([
              "grid",
              // 'bg-[hotpink]', // for debugging
              !chatOpen && classNames.agentChatClosed,
              chatOpen &&
                hasSecondTile &&
                classNames.agentChatOpenWithSecondTile,
              chatOpen &&
                !hasSecondTile &&
                classNames.agentChatOpenWithoutSecondTile,
            ])}
          >
            <AnimatePresence mode="popLayout">
              {!isAvatar && (
                // audio-only agent
                <MotionAgentTile
                  key="agent"
                  layoutId="agent"
                  {...animationProps}
                  animate={agentAnimate}
                  transition={agentLayoutTransition}
                  state={agentState}
                  audioTrack={agentAudioTrack}
                  className={cn(chatOpen ? "h-[90px]" : "h-auto w-full")}
                />
              )}
              {isAvatar && (
                // avatar agent
                <MotionAvatarTile
                  key="avatar"
                  layoutId="avatar"
                  {...animationProps}
                  animate={avatarAnimate}
                  transition={avatarLayoutTransition}
                  videoTrack={agentVideoTrack}
                  onClick={onAvatarClick}
                  className={cn(
                    chatOpen
                      ? "h-[90px] [&>video]:h-[90px] [&>video]:w-auto"
                      : "h-auto w-full",
                  )}
                />
              )}
            </AnimatePresence>
          </div>

          <div
            className={cn([
              "grid",
              chatOpen && classNames.secondTileChatOpen,
              !chatOpen && classNames.secondTileChatClosed,
            ])}
          >
            {/* camera */}
            <AnimatePresence>
              {cameraTrack && isCameraEnabled && (
                <MotionVideoTile
                  key="camera"
                  layout="position"
                  layoutId="camera"
                  {...animationProps}
                  trackRef={cameraTrack}
                  transition={{
                    ...animationProps.transition,
                    delay: chatOpen ? 0 : 0.15,
                  }}
                  className="h-[90px]"
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
