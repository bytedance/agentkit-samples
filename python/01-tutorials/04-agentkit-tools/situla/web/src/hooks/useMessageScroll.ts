import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "../types";

export function useMessageScroll(messages: ChatMessage[]) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToLatestRef = useRef(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  useEffect(() => {
    const scroller = scrollRef.current;
    if (scroller && stickToLatestRef.current) scroller.scrollTop = scroller.scrollHeight;
  }, [messages]);

  const onScroll = () => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const atLatest = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 72;
    stickToLatestRef.current = atLatest;
    setShowJumpToLatest(!atLatest);
  };

  const jumpToLatest = () => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    stickToLatestRef.current = true;
    setShowJumpToLatest(false);
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
  };

  const pinToLatest = () => {
    stickToLatestRef.current = true;
    setShowJumpToLatest(false);
  };

  return { scrollRef, showJumpToLatest, onScroll, jumpToLatest, pinToLatest };
}
