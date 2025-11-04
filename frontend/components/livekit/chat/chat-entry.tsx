import { cn } from "@/lib/utils";
import type {
  MessageFormatter,
  ReceivedChatMessage,
} from "@livekit/components-react";
import * as React from "react";
import { useChatMessage } from "./hooks/utils";

export interface ChatEntryProps extends React.HTMLAttributes<HTMLLIElement> {
  /** The chat massage object to display. */
  entry: ReceivedChatMessage;
  /** Hide sender name. Useful when displaying multiple consecutive chat messages from the same person. */
  hideName?: boolean;
  /** Hide message timestamp. */
  hideTimestamp?: boolean;
  /** An optional formatter for the message body. */
  messageFormatter?: MessageFormatter;
}

export const ChatEntry = ({
  entry,
  messageFormatter,
  hideName,
  hideTimestamp,
  className,
  ...props
}: ChatEntryProps) => {
  const { message, hasBeenEdited, time, locale, name } = useChatMessage(
    entry,
    messageFormatter,
  );

  const isUser = entry.from?.isLocal ?? false;
  const messageOrigin = isUser ? "local" : "remote";

  return (
    <li
      data-lk-message-origin={messageOrigin}
      title={time.toLocaleTimeString(locale, { timeStyle: "full" })}
      className={cn(
        "group flex flex-col gap-0.5",
        isUser ? "items-end" : "items-start",
        className,
      )}
      {...props}
    >
      {(!hideTimestamp || !hideName || hasBeenEdited) && (
        <span className="text-muted-foreground flex text-sm">
          {!hideName && <strong className="mt-2">{name}</strong>}

          {!hideTimestamp && (
            <span className="align-self-end ml-auto font-mono text-xs opacity-0 transition-opacity ease-linear group-hover:opacity-100">
              {hasBeenEdited && "*"}
              {time.toLocaleTimeString(locale, { timeStyle: "short" })}
            </span>
          )}
        </span>
      )}

      <span
        className={cn(
          "max-w-[75%] rounded-[20px] px-4 py-2",
          isUser
            ? "bg-blue-500 dark:bg-blue-600 text-white text-sm"
            : "bg-gray-200 dark:bg-gray-700 text-foreground text-base",
        )}
      >
        {message}
      </span>
    </li>
  );
};
