"use client";

import { cn } from "@/lib/utils";
import { type RefObject, useEffect, useRef } from "react";

export function useAutoScroll(
  scrollContentContainerRef: RefObject<Element | null>,
) {
  useEffect(() => {
    function scrollToBottom() {
      if (scrollContentContainerRef.current) {
        // Find the scrollable parent container
        let scrollableParent = scrollContentContainerRef.current.parentElement;
        while (scrollableParent) {
          const overflowY = window.getComputedStyle(scrollableParent).overflowY;
          if (overflowY === "auto" || overflowY === "scroll") {
            scrollableParent.scrollTop = scrollableParent.scrollHeight;
            return;
          }
          scrollableParent = scrollableParent.parentElement;
        }

        // Fallback to document scrolling if no scrollable parent found
        const { scrollingElement } = document;
        if (scrollingElement) {
          scrollingElement.scrollTop = scrollingElement.scrollHeight;
        }
      }
    }

    if (scrollContentContainerRef.current) {
      const resizeObserver = new ResizeObserver(scrollToBottom);

      resizeObserver.observe(scrollContentContainerRef.current);
      scrollToBottom();

      return () => resizeObserver.disconnect();
    }
  }, [scrollContentContainerRef]);
}
interface ChatProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
  className?: string;
}

export const ChatMessageView = ({
  className,
  children,
  ...props
}: ChatProps) => {
  const scrollContentRef = useRef<HTMLDivElement>(null);

  useAutoScroll(scrollContentRef);

  return (
    <div
      ref={scrollContentRef}
      className={cn("flex flex-col", className)}
      {...props}
    >
      {children}
    </div>
  );
};
