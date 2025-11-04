import { type TrackReference, VideoTrack } from "@livekit/components-react";
import { cn } from "@/lib/utils";

interface AgentAudioTileProps {
  videoTrack: TrackReference;
  className?: string;
  onClick?: () => void;
}

export const AvatarTile = ({
  videoTrack,
  className,
  onClick,
  ref,
}: React.ComponentProps<"div"> & AgentAudioTileProps) => {
  return (
    <div
      ref={ref}
      onClick={onClick}
      className={cn(
        "flex items-center justify-center aspect-square",
        onClick &&
          "cursor-pointer hover:scale-105 transition-transform duration-200",
        className,
      )}
      style={{
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
      }}
    >
      <VideoTrack
        trackRef={videoTrack}
        width={videoTrack?.publication.dimensions?.width ?? 0}
        height={videoTrack?.publication.dimensions?.height ?? 0}
        className="rounded-full object-cover"
      />
    </div>
  );
};
