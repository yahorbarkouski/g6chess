import { useEffect } from "react";

export function useDocumentTitle(title: string): void {
  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    if (document.title !== title) {
      document.title = title;
    }
  }, [title]);
}
