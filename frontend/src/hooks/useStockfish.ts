import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import { sideToMoveFromFen } from "../lib/chess";
import {
  isReadyOk,
  isUciOk,
  parseUciInfo,
  type UciInfoLine,
  uciInfoLinesToBestLines,
} from "../lib/stockfish-uci";
import type { BestLine } from "../types/analysis";

const PRE_ANALYZE_DEPTH = 16;
const ENGINE_STATE_COMMIT_THROTTLE_MS = 80;
const EVAL_DISPLAY_BUCKET_CP = 10;
const DISPLAY_LINE_COUNT = 3;
const DISPLAY_PV_MOVE_COUNT = 8;

export interface CachedAnalysis {
  lines: BestLine[];
  depth: number;
  evalCp: number | null;
}

interface UseStockfishOptions {
  multiPv?: number;
  targetDepth?: number;
  enabled?: boolean;
}

interface UseStockfishResult {
  fen: string | null;
  isReady: boolean;
  isAnalyzing: boolean;
  lines: BestLine[];
  depth: number;
  evalCp: number | null;
  analyze: (fen: string) => void;
  stop: () => void;
  preAnalyze: (fens: string[]) => void;
}

export function useStockfish({
  multiPv = 3,
  targetDepth = 24,
  enabled = true,
}: UseStockfishOptions = {}): UseStockfishResult {
  const [isReady, setIsReady] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [engineState, setEngineState] = useState<{
    fen: string | null;
    lines: BestLine[];
    depth: number;
    evalCp: number | null;
  }>({
    fen: null,
    lines: [],
    depth: 0,
    evalCp: null,
  });

  const workerRef = useRef<Worker | null>(null);
  const isReadyRef = useRef(false);
  const searchingRef = useRef(false);
  const currentFenRef = useRef<string | null>(null);
  const queuedFenRef = useRef<string | null>(null);
  const pendingInfoRef = useRef<Map<number, UciInfoLine>>(new Map());
  const pendingCommitRef = useRef<CachedAnalysis | null>(null);
  const commitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastCommitAtRef = useRef(0);
  const displayGateRef = useRef(createStockfishDisplayGate());
  const cacheRef = useRef<Map<string, CachedAnalysis>>(new Map());
  const preQueueRef = useRef<string[]>([]);
  const preQueueKeyRef = useRef("");
  const isPreAnalysisRef = useRef(false);
  const userFenRef = useRef<string | null>(null);

  const clearPendingCommit = useCallback(() => {
    pendingCommitRef.current = null;
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
      commitTimerRef.current = null;
    }
  }, []);

  const commitEngineState = useCallback(
    (fen: string, analysis: CachedAnalysis, options: { force?: boolean } = {}) => {
      const displayKey = getStockfishDisplayKey(fen, analysis);
      if (!displayGateRef.current.shouldPublish(displayKey, options)) {
        return;
      }
      startTransition(() => {
        setEngineState({
          fen,
          lines: analysis.lines,
          depth: analysis.depth,
          evalCp: analysis.evalCp,
        });
      });
    },
    [],
  );

  const flushPendingCommit = useCallback(
    (nextAnalysis?: CachedAnalysis) => {
      const analysis = nextAnalysis ?? pendingCommitRef.current;
      const fen = currentFenRef.current;
      if (!analysis || !fen) {
        return;
      }
      clearPendingCommit();
      lastCommitAtRef.current = Date.now();
      commitEngineState(fen, analysis);
    },
    [clearPendingCommit, commitEngineState],
  );

  const scheduleEngineStateCommit = useCallback(
    (nextAnalysis: CachedAnalysis) => {
      pendingCommitRef.current = nextAnalysis;
      const elapsed = Date.now() - lastCommitAtRef.current;
      if (lastCommitAtRef.current === 0 || elapsed >= ENGINE_STATE_COMMIT_THROTTLE_MS) {
        flushPendingCommit(nextAnalysis);
        return;
      }
      if (commitTimerRef.current) {
        return;
      }
      commitTimerRef.current = setTimeout(() => {
        flushPendingCommit();
      }, ENGINE_STATE_COMMIT_THROTTLE_MS - elapsed);
    },
    [flushPendingCommit],
  );

  const updateCache = useCallback((fen: string, analysis: CachedAnalysis) => {
    const existing = cacheRef.current.get(fen);
    if (!existing || analysis.depth > existing.depth) {
      cacheRef.current.set(fen, analysis);
    }
  }, []);

  const applyCacheToState = useCallback(
    (fen: string) => {
      const cached = cacheRef.current.get(fen);
      if (!cached) {
        return;
      }
      commitEngineState(fen, cached, { force: true });
    },
    [commitEngineState],
  );

  const dispatchGoInternal = useCallback(
    (worker: Worker, fen: string, goDepth: number, isPreAnalysis: boolean) => {
      clearPendingCommit();
      currentFenRef.current = fen;
      pendingInfoRef.current.clear();
      searchingRef.current = true;
      isPreAnalysisRef.current = isPreAnalysis;
      if (!isPreAnalysis) {
        setIsAnalyzing(true);
      }
      worker.postMessage(`position fen ${fen}`);
      worker.postMessage(`go depth ${goDepth}`);
    },
    [clearPendingCommit],
  );

  const processNextPreQueue = useCallback(
    (worker: Worker) => {
      if (userFenRef.current || queuedFenRef.current) {
        return;
      }
      while (preQueueRef.current.length > 0) {
        const fen = preQueueRef.current.shift();
        if (!fen) {
          return;
        }
        const cached = cacheRef.current.get(fen);
        if (cached && cached.depth >= PRE_ANALYZE_DEPTH) {
          continue;
        }
        dispatchGoInternal(worker, fen, PRE_ANALYZE_DEPTH, true);
        return;
      }
    },
    [dispatchGoInternal],
  );

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let terminated = false;
    const worker = new Worker("/stockfish/stockfish-18-single.js");
    workerRef.current = worker;

    worker.onmessage = (event: MessageEvent) => {
      if (terminated) {
        return;
      }
      const line = typeof event.data === "string" ? event.data : String(event.data);

      if (isUciOk(line)) {
        worker.postMessage(`setoption name MultiPV value ${multiPv}`);
        worker.postMessage("isready");
        return;
      }

      if (isReadyOk(line)) {
        isReadyRef.current = true;
        setIsReady(true);
        if (queuedFenRef.current) {
          const fen = queuedFenRef.current;
          queuedFenRef.current = null;
          userFenRef.current = fen;
          applyCacheToState(fen);
          dispatchGoInternal(worker, fen, targetDepth, false);
          return;
        }
        processNextPreQueue(worker);
        return;
      }

      const info = parseUciInfo(line);
      if (info && currentFenRef.current) {
        pendingInfoRef.current.set(info.multipv, info);
        if (pendingInfoRef.current.size >= multiPv || info.multipv === multiPv) {
          const sorted = Array.from(pendingInfoRef.current.values()).sort(
            (a, b) => a.multipv - b.multipv,
          );
          const fen = currentFenRef.current;
          const side = sideToMoveFromFen(fen);
          const bestLines = uciInfoLinesToBestLines(fen, sorted, side);
          const evalCp = bestLines[0]?.eval_cp ?? null;
          const nextAnalysis = { lines: bestLines, depth: info.depth, evalCp };

          updateCache(fen, nextAnalysis);
          if (!isPreAnalysisRef.current) {
            scheduleEngineStateCommit(nextAnalysis);
          }
        }
      }

      if (line.startsWith("bestmove")) {
        searchingRef.current = false;
        const wasPre = isPreAnalysisRef.current;
        isPreAnalysisRef.current = false;

        if (queuedFenRef.current) {
          const fen = queuedFenRef.current;
          queuedFenRef.current = null;
          userFenRef.current = fen;
          applyCacheToState(fen);
          dispatchGoInternal(worker, fen, targetDepth, false);
          return;
        }

        if (wasPre) {
          processNextPreQueue(worker);
          return;
        }

        flushPendingCommit();
        userFenRef.current = null;
        setIsAnalyzing(false);
      }
    };

    worker.postMessage("uci");

    return () => {
      terminated = true;
      clearPendingCommit();
      isReadyRef.current = false;
      searchingRef.current = false;
      workerRef.current = null;
      worker.terminate();
    };
  }, [
    applyCacheToState,
    clearPendingCommit,
    dispatchGoInternal,
    enabled,
    flushPendingCommit,
    multiPv,
    processNextPreQueue,
    scheduleEngineStateCommit,
    targetDepth,
    updateCache,
  ]);

  const analyze = useCallback(
    (fen: string) => {
      if (!enabled) {
        return;
      }
      const worker = workerRef.current;
      if (!worker) {
        return;
      }

      userFenRef.current = fen;
      applyCacheToState(fen);

      if (!isReadyRef.current) {
        queuedFenRef.current = fen;
        return;
      }

      if (searchingRef.current) {
        queuedFenRef.current = fen;
        worker.postMessage("stop");
        return;
      }

      const cached = cacheRef.current.get(fen);
      if (cached && cached.depth >= targetDepth) {
        commitEngineState(fen, cached, { force: true });
        setIsAnalyzing(false);
        userFenRef.current = null;
        processNextPreQueue(worker);
        return;
      }

      dispatchGoInternal(worker, fen, targetDepth, false);
    },
    [
      applyCacheToState,
      commitEngineState,
      dispatchGoInternal,
      enabled,
      processNextPreQueue,
      targetDepth,
    ],
  );

  const stop = useCallback(() => {
    const worker = workerRef.current;
    if (!worker) {
      return;
    }
    clearPendingCommit();
    queuedFenRef.current = null;
    userFenRef.current = null;
    preQueueRef.current = [];
    preQueueKeyRef.current = "";
    if (searchingRef.current) {
      worker.postMessage("stop");
    }
    currentFenRef.current = null;
    displayGateRef.current.reset();
    setIsAnalyzing(false);
  }, [clearPendingCommit]);

  const preAnalyze = useCallback(
    (fens: string[]) => {
      const nextQueue = uniqueFens(fens);
      const nextKey = nextQueue.join("\n");
      if (nextKey === preQueueKeyRef.current) {
        return;
      }
      preQueueKeyRef.current = nextKey;
      preQueueRef.current = nextQueue;
      const worker = workerRef.current;
      if (!worker || !isReadyRef.current) {
        return;
      }
      if (!searchingRef.current && !userFenRef.current && !queuedFenRef.current) {
        processNextPreQueue(worker);
      }
    },
    [processNextPreQueue],
  );

  return {
    fen: engineState.fen,
    isReady,
    isAnalyzing,
    lines: engineState.lines,
    depth: engineState.depth,
    evalCp: engineState.evalCp,
    analyze,
    stop,
    preAnalyze,
  };
}

export function getStockfishDisplayKey(fen: string, analysis: CachedAnalysis): string {
  const linesKey = analysis.lines
    .slice(0, DISPLAY_LINE_COUNT)
    .map((line) =>
      [
        line.uci,
        evalDisplayKey(line.eval_cp),
        line.pv_uci.slice(0, DISPLAY_PV_MOVE_COUNT).join(","),
      ].join(":"),
    )
    .join("|");
  return `${fen}|d:${analysis.depth}|e:${evalDisplayKey(analysis.evalCp)}|${linesKey}`;
}

export function createStockfishDisplayGate(): {
  shouldPublish: (displayKey: string, options?: { force?: boolean }) => boolean;
  reset: () => void;
} {
  let lastDisplayKey: string | null = null;
  return {
    shouldPublish(displayKey, options = {}) {
      if (!options.force && displayKey === lastDisplayKey) {
        return false;
      }
      lastDisplayKey = displayKey;
      return true;
    },
    reset() {
      lastDisplayKey = null;
    },
  };
}

function evalDisplayKey(evalCp: number | null): string {
  if (evalCp === null) {
    return "none";
  }
  if (Math.abs(evalCp) >= 20_000) {
    return `mate:${evalCp}`;
  }
  return `cp:${Math.round(evalCp / EVAL_DISPLAY_BUCKET_CP)}`;
}

function uniqueFens(fens: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const fen of fens) {
    if (!fen || seen.has(fen)) {
      continue;
    }
    seen.add(fen);
    out.push(fen);
  }
  return out;
}
