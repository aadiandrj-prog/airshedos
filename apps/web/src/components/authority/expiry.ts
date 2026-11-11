"use client";
import { useEffect, useRef } from "react";
/** Clear displayed private/provider content on expiry, including 30/90-day deadlines. */
export function useDeadline(deadline: string | undefined, expired: () => void) {
  const callback = useRef(expired);
  useEffect(() => { callback.current = expired; }, [expired]);
  useEffect(() => {
    if (!deadline) return;
    let timer: ReturnType<typeof setTimeout>;
    const check = () => {
      const remaining = Date.parse(deadline) - Date.now();
      if (remaining <= 0) callback.current();
      else timer = setTimeout(check, Math.min(remaining, 86_400_000));
    };
    timer = setTimeout(check, Math.max(0, Math.min(Date.parse(deadline) - Date.now(), 86_400_000)));
    return () => clearTimeout(timer);
  }, [deadline]);
}
