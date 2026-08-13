import { useEffect, useState } from "react";

const COARSE_POINTER_QUERY = "(hover: none), (pointer: coarse)";

function readCoarsePointer(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(COARSE_POINTER_QUERY).matches;
}

export function useCoarsePointer(): boolean {
  const [coarsePointer, setCoarsePointer] = useState(readCoarsePointer);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mediaQuery = window.matchMedia(COARSE_POINTER_QUERY);
    const update = () => setCoarsePointer(mediaQuery.matches);
    update();
    mediaQuery.addEventListener?.("change", update);
    return () => mediaQuery.removeEventListener?.("change", update);
  }, []);

  return coarsePointer;
}
