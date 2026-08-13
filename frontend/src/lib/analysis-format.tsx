import { ArrowRight, BookOpen, Star, ThumbsUp } from "lucide-react";
import type { ReactNode } from "react";
import type { AnalysisMoveMarker, MovePrimaryClass } from "../types/analysis";

export function primaryClassLabel(
  pc: AnalysisMoveMarker["primary_class"] | null | undefined,
): string {
  if (!pc) {
    return "";
  }
  const labels: Record<MovePrimaryClass, string> = {
    blunder: "Blunder",
    mistake: "Mistake",
    inaccuracy: "Inaccuracy",
    good: "Good",
    neutral: "Neutral",
    excellent: "Excellent",
    best: "Best",
    miss: "Miss",
    great: "Great",
    brilliant: "Brilliant",
    book: "Book",
  };
  return labels[pc] ?? pc;
}

export function primaryClassClass(
  pc: AnalysisMoveMarker["primary_class"] | null | undefined,
): string {
  if (!pc) {
    return "border-stone-200 bg-stone-50 text-stone-700 dark:border-stone-700 dark:bg-stone-900/50 dark:text-stone-200";
  }
  if (pc === "blunder") {
    return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300";
  }
  if (pc === "mistake" || pc === "miss") {
    return "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/60 dark:bg-orange-950/40 dark:text-orange-300";
  }
  if (pc === "inaccuracy") {
    return "border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-900/60 dark:bg-yellow-950/40 dark:text-yellow-300";
  }
  if (pc === "brilliant") {
    return "border-purple-200 bg-purple-100 text-purple-800 dark:border-purple-800/70 dark:bg-purple-950/55 dark:text-purple-200";
  }
  if (pc === "great") {
    return "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-200";
  }
  if (pc === "best" || pc === "excellent") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200";
  }
  if (pc === "book") {
    return "border-amber-700/30 bg-amber-900/10 text-amber-800 dark:border-amber-700/40 dark:bg-amber-950/40 dark:text-amber-300";
  }
  return "border-[#7a8a72]/30 bg-[#7a8a72]/10 text-[#5a6a52] dark:border-[#7a8a72]/40 dark:bg-[#7a8a72]/10 dark:text-[#a8b8a0]";
}

export function analysisTagLabel(tag: string): string {
  return tag
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function isCriticalMarker(marker: AnalysisMoveMarker): boolean {
  return (
    marker.label_metadata.requires_explanation === true ||
    marker.tags.includes("critical_significance")
  );
}

export interface QualityTokenOptions {
  size?: "sm" | "lg";
}

export function qualityToken(
  marker: AnalysisMoveMarker | undefined | null,
  options?: QualityTokenOptions,
): { content: ReactNode; className: string } | null {
  if (!marker) {
    return null;
  }
  const pc = marker.primary_class;
  const isLg = options?.size === "lg";

  if (pc === "blunder") {
    return { content: "??", className: "bg-rose-500/80 text-white" };
  }
  if (pc === "mistake" || pc === "miss") {
    return { content: "?", className: "bg-orange-400 text-white" };
  }
  if (pc === "inaccuracy") {
    return { content: "?!", className: "bg-yellow-400 text-stone-900" };
  }
  if (pc === "brilliant") {
    return { content: "!!", className: "bg-purple-600 text-white" };
  }
  if (pc === "great") {
    return { content: "!", className: "bg-blue-500 text-white" };
  }
  if (pc === "best") {
    return {
      content: <Star className={isLg ? "h-4 w-4 fill-current" : "size-2 fill-current"} />,
      className: "bg-emerald-500 text-white",
    };
  }
  if (pc === "excellent") {
    return {
      content: <ThumbsUp className={isLg ? "h-3.5 w-3.5 fill-current" : "size-2 fill-current"} />,
      className: "bg-emerald-500 text-white",
    };
  }
  if (pc === "book") {
    return {
      content: <BookOpen className={isLg ? "h-3.5 w-3.5 fill-current" : "size-2 fill-current"} />,
      className: "bg-amber-800/80 text-amber-100 dark:bg-amber-700/80",
    };
  }
  if (marker.tags.includes("forced")) {
    return {
      content: <ArrowRight className={isLg ? "h-4 w-4" : "size-2"} />,
      className: "bg-stone-400 text-white dark:bg-stone-500",
    };
  }
  return { content: "✓", className: "bg-[#7a8a72] text-white" };
}
