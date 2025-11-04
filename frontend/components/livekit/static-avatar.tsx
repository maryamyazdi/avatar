import { cn } from "@/lib/utils";
import { type AgentState } from "@livekit/components-react";
import { Robot } from "@phosphor-icons/react/dist/ssr";

interface StaticAvatarProps {
  state: AgentState;
  className?: string;
  onClick?: () => void;
}

export const StaticAvatar = ({
  state,
  className,
  onClick,
  ref,
}: React.ComponentProps<"div"> & StaticAvatarProps) => {
  const isActive =
    state === "listening" || state === "speaking" || state === "thinking";
  const isSpeaking = state === "speaking";

  return (
    <div
      ref={ref}
      onClick={onClick}
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg",
        "aspect-square", // Ensure perfect circle
        onClick &&
          "cursor-pointer hover:scale-105 transition-transform duration-200",
        className,
      )}
      style={{
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
      }}
    >
      {/* Subtle shine effect */}
      <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/10 to-transparent" />

      {/* Main content container */}
      <div className="relative z-10 flex h-full w-full items-center justify-center">
        {/* Robot Icon */}
        <Robot
          weight="duotone"
          className="text-white drop-shadow-lg"
          style={{ fontSize: "55%" }}
        />

        {/* Audio waveform indicator when speaking */}
        {isSpeaking && (
          <div className="absolute bottom-2 flex items-end gap-0.5">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="w-1 rounded-full bg-white/90"
                style={{
                  height: "4px",
                  animation: `pulse 0.8s ease-in-out ${i * 0.1}s infinite`,
                }}
              />
            ))}
          </div>
        )}

        {/* Listening indicator */}
        {state === "listening" && (
          <div className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex h-3 w-3 rounded-full bg-green-500"></span>
          </div>
        )}

        {/* Thinking indicator */}
        {state === "thinking" && (
          <div className="absolute -bottom-1 flex items-center gap-1">
            <div
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-white"
              style={{ animationDelay: "0ms" }}
            />
            <div
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-white"
              style={{ animationDelay: "150ms" }}
            />
            <div
              className="h-1.5 w-1.5 animate-bounce rounded-full bg-white"
              style={{ animationDelay: "300ms" }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
