import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import { useStockfish } from "../../hooks/useStockfish";
import type { BestLine } from "../../types/analysis";

const EMPTY_LINES: BestLine[] = [];

export interface StockfishAnalysisSnapshot {
  fen: string | null;
  lines: BestLine[];
  evalCp: number | null;
  depth: number;
  isReady: boolean;
  isAnalyzing: boolean;
}

interface StockfishAnalysisStore {
  getSnapshot: () => StockfishAnalysisSnapshot;
  setSnapshot: (snapshot: StockfishAnalysisSnapshot) => void;
  subscribe: (listener: () => void) => () => void;
}

interface StockfishAnalysisRuntimeProps {
  analysisFen: string;
  preAnalyzeFens: string[];
  shouldAnalyze: boolean;
  multiPv?: number;
  targetDepth?: number;
}

const EMPTY_SNAPSHOT: StockfishAnalysisSnapshot = {
  fen: null,
  lines: EMPTY_LINES,
  evalCp: null,
  depth: 0,
  isReady: false,
  isAnalyzing: false,
};

const stockfishAnalysisStore = createStockfishAnalysisStore(EMPTY_SNAPSHOT);

export function StockfishAnalysisRuntime({
  analysisFen,
  preAnalyzeFens,
  shouldAnalyze,
  multiPv = 3,
  targetDepth = 24,
}: StockfishAnalysisRuntimeProps) {
  const stockfish = useStockfish({ multiPv, targetDepth });

  useEffect(() => {
    stockfishAnalysisStore.setSnapshot({
      fen: stockfish.fen,
      lines: stockfish.lines,
      evalCp: stockfish.evalCp,
      depth: stockfish.depth,
      isReady: stockfish.isReady,
      isAnalyzing: stockfish.isAnalyzing,
    });
  }, [
    stockfish.depth,
    stockfish.evalCp,
    stockfish.fen,
    stockfish.isAnalyzing,
    stockfish.isReady,
    stockfish.lines,
  ]);

  useEffect(() => {
    stockfish.preAnalyze(preAnalyzeFens);
  }, [preAnalyzeFens, stockfish.preAnalyze]);

  useEffect(() => {
    if (!shouldAnalyze || !analysisFen) {
      return;
    }
    const timer = window.setTimeout(() => stockfish.analyze(analysisFen), 80);
    return () => window.clearTimeout(timer);
  }, [analysisFen, shouldAnalyze, stockfish.analyze]);

  useEffect(() => {
    return () => stockfishAnalysisStore.setSnapshot(EMPTY_SNAPSHOT);
  }, []);

  return null;
}

export function useStockfishAnalysisSelector<T>(
  selector: (snapshot: StockfishAnalysisSnapshot) => T,
  isEqual: (previous: T, next: T) => boolean = Object.is,
): T {
  const selectedRef = useRef<{ snapshot: StockfishAnalysisSnapshot; value: T } | null>(null);

  const getSelectedSnapshot = useCallback(() => {
    const snapshot = stockfishAnalysisStore.getSnapshot();
    const cached = selectedRef.current;
    if (cached?.snapshot === snapshot) {
      return cached.value;
    }

    const nextValue = selector(snapshot);
    if (cached && isEqual(cached.value, nextValue)) {
      selectedRef.current = { snapshot, value: cached.value };
      return cached.value;
    }

    selectedRef.current = { snapshot, value: nextValue };
    return nextValue;
  }, [isEqual, selector]);

  return useSyncExternalStore(
    stockfishAnalysisStore.subscribe,
    getSelectedSnapshot,
    getSelectedSnapshot,
  );
}

function createStockfishAnalysisStore(
  initialSnapshot: StockfishAnalysisSnapshot,
): StockfishAnalysisStore {
  let snapshot = initialSnapshot;
  const listeners = new Set<() => void>();

  return {
    getSnapshot: () => snapshot,
    setSnapshot: (nextSnapshot) => {
      if (areStockfishAnalysisSnapshotsEqual(snapshot, nextSnapshot)) {
        return;
      }
      snapshot = nextSnapshot;
      for (const listener of listeners) {
        listener();
      }
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

function areStockfishAnalysisSnapshotsEqual(
  previous: StockfishAnalysisSnapshot,
  next: StockfishAnalysisSnapshot,
): boolean {
  return (
    previous.fen === next.fen &&
    previous.lines === next.lines &&
    Object.is(previous.evalCp, next.evalCp) &&
    previous.depth === next.depth &&
    previous.isReady === next.isReady &&
    previous.isAnalyzing === next.isAnalyzing
  );
}
