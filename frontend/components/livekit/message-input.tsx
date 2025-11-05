"use client";

import { cn } from "@/lib/utils";
import { useRoomContext } from "@livekit/components-react";
import { PaperPlaneRight } from "@phosphor-icons/react/dist/ssr";
import { motion } from "motion/react";
import React, { useEffect, useRef, useState } from "react";

interface MessageInputProps
  extends Omit<React.HTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSend?: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  showInputField?: boolean;
  inline?: boolean; // New prop for toolbar integration
}

export function MessageInput({
  onSend,
  className,
  disabled = false,
  placeholder = "Type your message ...",
  showInputField = true,
  inline = false,
  ...props
}: MessageInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string>("");
  const [isFocused, setIsFocused] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const room = useRoomContext();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (message.trim().length === 0 || isSending || disabled) {
      return;
    }

    setIsSending(true);

    try {
      // Send text via LiveKit protocol
      if (room?.localParticipant) {
        await room.localParticipant.publishData(
          new TextEncoder().encode(
            JSON.stringify({
              message: message.trim(),
              timestamp: Date.now(),
            })
          ),
          { topic: "lk.chat" }
        );
      }

      // Call the optional callback
      onSend?.(message.trim());

      // Clear input after successful send
      setMessage("");
      inputRef.current?.focus();
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsSending(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(e.target.value);
  };

  const isDisabled = disabled || isSending;
  const canSend = message.trim().length > 0 && !isDisabled;

  useEffect(() => {
    if (disabled || !showInputField) return;
    // Autofocus when enabled
    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
    return () => clearTimeout(timer);
  }, [disabled, showInputField]);

  if (!showInputField) {
    return null;
  }

  // Inline mode: render as a simple form without motion animations (for toolbar integration)
  if (inline) {
    return (
      <form
        {...props}
        onSubmit={handleSubmit}
        className={cn(
          // Base container - compact for toolbar
          "relative flex flex-1 items-center gap-2 px-3 py-2",
          // Rounded corners to match control bar
          "rounded-[24px]",
          // Background with dark theme support
          "bg-background/50 backdrop-blur-sm",
          // Border styling - subtle like control bar
          "border transition-all duration-300",
          "border-bg2 dark:border-separator1",
          // Focus state
          isFocused && "border-[#669bd1]",
          // Disabled state
          isDisabled && "opacity-60 cursor-not-allowed",
          // Responsive sizing
          "min-w-[220px] max-w-[480px]",
          className
        )}
      >
        {/* Text Input */}
        <input
          ref={inputRef}
          type="text"
          value={message}
          disabled={isDisabled}
          placeholder={placeholder}
          onChange={handleChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          className={cn(
            "flex-1 bg-transparent text-[#F9F8EB] placeholder:text-muted-foreground",
            "text-sm font-normal leading-relaxed",
            "focus:outline-none",
            "disabled:cursor-not-allowed",
            "tracking-wide"
          )}
        />

        {/* Send Button - Compact */}
        <button
          type="submit"
          disabled={!canSend}
          className={cn(
            // Compact button styling
            "flex h-8 w-8 items-center justify-center rounded-full",
            "transition-all duration-300",
            "focus:outline-none focus:ring-2 focus:ring-offset-2",
            // Active state
            canSend
              ? [
                  "bg-[#ef3b56] hover:bg-[#d32944]",
                  "text-white",
                  "shadow-md hover:shadow-lg",
                  "focus:ring-[#ef3b56]",
                ]
              : [
                  "bg-muted text-muted-foreground cursor-not-allowed",
                  "shadow-none",
                ]
          )}
          aria-label="Send message"
        >
          {isSending ? (
            <div
              className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
            />
          ) : (
            <PaperPlaneRight
              weight="bold"
              className="h-4 w-4"
            />
          )}
        </button>
      </form>
    );
  }

  // Standard mode: render with motion animations (for standalone use)
  return (
    <motion.form
      {...props}
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{
        duration: 0.3,
        ease: [0.4, 0, 0.2, 1],
      }}
      className={cn(
        // Base container
        "relative flex items-center gap-3 px-5 py-3",
        // Rounded corners to match control bar
        "rounded-[31px]",
        // Background with dark theme support
        "bg-background backdrop-blur-md",
        // Border styling - subtle like control bar
        "border transition-all duration-300",
        "border-bg2 dark:border-separator1",
        "drop-shadow-md/3",
        // Disabled state
        isDisabled && "opacity-60 cursor-not-allowed",
        className
      )}
      style={{
        willChange: "opacity",
      }}
    >
      {/* Text Input */}
      <input
        ref={inputRef}
        type="text"
        value={message}
        disabled={isDisabled}
        placeholder={placeholder}
        onChange={handleChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        className={cn(
          "flex-1 bg-transparent text-[#F9F8EB] placeholder:text-muted-foreground",
          "text-base font-normal leading-relaxed",
          "focus:outline-none",
          "disabled:cursor-not-allowed",
          // Material Design typography
          "tracking-wide"
        )}
      />

      {/* Send Button */}
      <motion.button
        type="submit"
        disabled={!canSend}
        whileHover={canSend ? { scale: 1.05 } : {}}
        whileTap={canSend ? { scale: 0.95 } : {}}
        transition={{
          type: "spring",
          stiffness: 400,
          damping: 17,
        }}
        className={cn(
          // Base button styling
          "flex h-10 w-10 items-center justify-center rounded-full",
          "transition-all duration-300",
          "focus:outline-none focus:ring-2 focus:ring-offset-2",
          // Active state - Material Design primary action
          canSend
            ? [
                "bg-[#ef3b56] hover:bg-[#d32944]",
                "text-white",
                "shadow-md hover:shadow-lg",
                "focus:ring-[#ef3b56]",
              ]
            : [
                "bg-muted text-muted-foreground cursor-not-allowed",
                "shadow-none",
              ]
        )}
        aria-label="Send message"
      >
        {isSending ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{
              duration: 1,
              repeat: Infinity,
              ease: "linear",
            }}
            className="h-5 w-5 rounded-full border-2 border-white border-t-transparent"
          />
        ) : (
          <PaperPlaneRight
            weight="bold"
            className={cn(
              "h-5 w-5 transition-transform",
              canSend && "group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
            )}
          />
        )}
      </motion.button>

      {/* Character counter (optional - only shows when typing) */}
      {message.length > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          className="absolute -top-8 right-0 text-xs text-muted-foreground"
        >
          {message.length}
        </motion.div>
      )}
    </motion.form>
  );
}

