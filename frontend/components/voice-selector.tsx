"use client";

import React from "react";
import { SpeakerHighIcon } from "@phosphor-icons/react/dist/ssr";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { TTSVoice } from "@/lib/types";
import { cn } from "@/lib/utils";

interface VoiceSelectorProps {
  voices: TTSVoice[];
  selectedVoice: string;
  onVoiceChange: (voiceId: string) => void;
  disabled?: boolean;
  className?: string;
}

export function VoiceSelector({
  voices,
  selectedVoice,
  onVoiceChange,
  disabled = false,
  className,
}: VoiceSelectorProps) {
  const selectedVoiceData = voices.find((voice) => voice.id === selectedVoice);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <SpeakerHighIcon className="size-4 text-muted-foreground" />
      <Select
        value={selectedVoice}
        onValueChange={onVoiceChange}
        disabled={disabled}
      >
        <SelectTrigger className="w-fit min-w-[120px]">
          <SelectValue>
            <span className="flex items-center gap-2">
              <span>{selectedVoiceData?.name || "Select Voice"}</span>
            </span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {voices.map((voice) => (
            <SelectItem key={voice.id} value={voice.id}>
              <div className="flex flex-col items-start">
                <span className="font-medium">{voice.name}</span>
                {voice.description && (
                  <span className="text-xs text-muted-foreground">
                    {voice.description}
                  </span>
                )}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
