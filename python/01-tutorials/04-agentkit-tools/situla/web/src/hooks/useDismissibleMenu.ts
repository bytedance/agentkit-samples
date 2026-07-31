import { useEffect, useRef } from "react";

export function useDismissibleMenu<T extends HTMLElement>(open: boolean, setOpen: (open: boolean) => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!open) return;
    const pointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && !ref.current?.contains(target)) setOpen(false);
    };
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", pointerDown);
    window.addEventListener("keydown", keyDown);
    return () => {
      document.removeEventListener("pointerdown", pointerDown);
      window.removeEventListener("keydown", keyDown);
    };
  }, [open, setOpen]);
  return ref;
}
