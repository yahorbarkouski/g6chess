import { Activity, ArrowLeft, ArrowUpDown, LayoutGrid, ListOrdered, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type DiscoveryState,
  type PreviewState,
  useAnalysisBoard,
} from "../../hooks/useAnalysisBoard";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import {
  type AnalysisRouteState,
  analysisStatusUrl,
  canonicalPathForRoute,
  chessComLiveGameUrl,
  currentBrowserPath,
  extractChessComLiveGameId,
  pushWithPath,
  readAnalysisRoute,
  replaceAnalysisUrl,
  replaceWithPath,
  type SharedAnalysisTarget,
} from "../../lib/analysis-routing";
import {
  ApiError,
  getCachedChessComLiveGameAnalysis,
  pollGameAnalysis,
  startImportedGameAnalysis,
} from "../../lib/api";
import {
  computeCapturedMaterial,
  ENGINE_ARROW_COLORS,
  formatEval,
  MAIA_ARROW_COLOR,
  sideToMoveFromFen,
  uciToSquares,
} from "../../lib/chess";
import { buildDocumentTitle } from "../../lib/document-title";
import {
  isTerminalGameAnalysisStatus,
  mapGameAnalysisImportResponse,
  mapGameAnalysisSnapshot,
} from "../../lib/game-analysis-mapping";
import { cn } from "../../lib/utils";
import type {
  AnalysisMoveMarker,
  AnalysisResponse,
  BestLine,
  BoardSide,
  BookLine,
  GameMove,
} from "../../types/analysis";
import type {
  GameAnalysisGame,
  GameAnalysisImportRequest,
  GameAnalysisSnapshot,
  ImportedGameMetadata,
} from "../../types/api";
import {
  AnalysisImportPanel,
  type ImportPanelStatus,
  isTurnstileEnabled,
} from "./AnalysisImportPanel";
import { AnalysisNavigationBar } from "./AnalysisNavigationBar";
import { AnalysisSettingsPopover } from "./AnalysisSettingsPopover";
import { BoardSidebar } from "./BoardSidebar";
import { DiscoveryLineBar, DiscoveryLineSidebar } from "./DiscoveryLine";
import { BookLinesView, EngineLinesView } from "./EngineLinesView";
import { type MarkerDisplayMode, MoveList } from "./MoveList";
import { PlayerBar } from "./PlayerBar";
import { PositionInfo } from "./PositionInfo";
import {
  StockfishAnalysisRuntime,
  type StockfishAnalysisSnapshot,
  useStockfishAnalysisSelector,
} from "./StockfishAnalysisRuntime";
import {
  type BoardArrow,
  type BoardTransitionMove,
  UltraAnalysisBoard,
} from "./UltraAnalysisBoard";
import { WorkspaceFooter } from "./WorkspaceFooter";

const EMPTY_BOARD_ARROWS: BoardArrow[] = [];
const DESKTOP_MEDIA_QUERY = "(min-width: 1100px)";
const MIN_BROWSER_EVAL_BAR_DEPTH = 13;
const MAX_PRE_ANALYZE_FENS = 12;
const PRE_ANALYZE_NEIGHBOR_PLIES = 4;
const EMPTY_PRE_ANALYZE_FENS: string[] = [];
const GAME_ANALYSIS_STORAGE_KEY = "g6explanation.currentGameAnalysis";
const ANALYSIS_LOADING_EMPTY_MESSAGE = "Crunching the analysis. The board is yours to explore";
type MobileTab = "board" | "moves" | "analysis";

const MOBILE_TAB_ITEMS: Array<{
  id: MobileTab;
  label: string;
  icon: typeof LayoutGrid;
}> = [
  { id: "board", label: "Board", icon: LayoutGrid },
  { id: "moves", label: "Moves", icon: ListOrdered },
  { id: "analysis", label: "Analysis", icon: Sparkles },
];

interface StoredGameAnalysisJob {
  analysis_id: string;
  status_url: string;
  source: ImportedGameMetadata | null;
  game: GameAnalysisGame | null;
}

interface AnalysisImportHomeProps {
  status: ImportPanelStatus;
  error: string | null;
  initialUrl: string | null;
  onImport: (request: GameAnalysisImportRequest) => Promise<void>;
  onClearError: () => void;
  turnstileToken: string | null;
  turnstileResetKey: number;
  onTurnstileToken: (token: string | null) => void;
  onTurnstileReset: () => void;
}

interface AnalysisGameWorkspaceProps {
  analysis: AnalysisResponse;
  initialPly: number | null;
  moveLoadingIndicator: MoveLoadingIndicatorState;
  onOpenImport: () => void;
  shareTarget: SharedAnalysisTarget | null;
}

export interface EngineLineSet {
  fen: string;
  lines: BestLine[];
}

interface BookLineSet {
  fen: string;
  lines: BookLine[];
}

type BrowserAnalysisReason = "discovery" | "preview" | "loading" | "missing-server-lines";

interface MoveLoadingIndicatorState {
  show: boolean;
  progress: number | null;
}

export function AnalysisWorkspace() {
  const initialRoute = useMemo(() => readAnalysisRoute(), []);
  const [route, setRoute] = useState(initialRoute);
  const storedJob = useMemo(() => readStoredGameAnalysisJob(), []);
  const initialJob = useMemo(
    () => selectInitialJob(initialRoute, storedJob),
    [initialRoute, storedJob],
  );
  const routeImportUrl =
    route.kind === "chess_com_live" && route.externalGameId !== null
      ? chessComLiveGameUrl(route.externalGameId)
      : null;
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [activeJob, setActiveJob] = useState<StoredGameAnalysisJob | null>(initialJob);
  const [importStatus, setImportStatus] = useState<ImportPanelStatus>(
    initialJob ? "polling" : initialRoute.kind === "chess_com_live" ? "submitting" : "idle",
  );
  const [importSnapshot, setImportSnapshot] = useState<GameAnalysisSnapshot | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [pendingRouteImportId, setPendingRouteImportId] = useState<string | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const currentRouteJobIdRef = useRef(initialJob?.analysis_id ?? null);
  const routeImportStartedRef = useRef<string | null>(null);

  const resetTurnstile = useCallback(() => {
    setTurnstileToken(null);
    setTurnstileResetKey((current) => current + 1);
  }, []);

  const updateRouteFromLocation = useCallback(() => {
    setRoute(readAnalysisRoute());
  }, []);

  const pushPath = useCallback(
    (path: string) => {
      pushWithPath(path);
      updateRouteFromLocation();
    },
    [updateRouteFromLocation],
  );

  const replacePath = useCallback(
    (path: string) => {
      replaceWithPath(path);
      updateRouteFromLocation();
    },
    [updateRouteFromLocation],
  );

  useEffect(() => {
    window.addEventListener("popstate", updateRouteFromLocation);
    return () => window.removeEventListener("popstate", updateRouteFromLocation);
  }, [updateRouteFromLocation]);

  useEffect(() => {
    if (route.canonicalPath !== null && route.canonicalPath !== currentBrowserPath()) {
      replacePath(route.canonicalPath);
    }
  }, [replacePath, route.canonicalPath]);

  useEffect(() => {
    if (route.kind === "home") {
      currentRouteJobIdRef.current = null;
      routeImportStartedRef.current = null;
      setActiveJob(null);
      setAnalysis(null);
      setImportSnapshot(null);
      setImportError(null);
      setImportStatus("idle");
      setPendingRouteImportId(null);
      return;
    }

    const nextJob = selectInitialJob(route, readStoredGameAnalysisJob());
    if (nextJob !== null) {
      const jobChanged = currentRouteJobIdRef.current !== nextJob.analysis_id;
      currentRouteJobIdRef.current = nextJob.analysis_id;
      routeImportStartedRef.current = null;
      setPendingRouteImportId(null);
      if (jobChanged) {
        setAnalysis(null);
        setImportSnapshot(null);
        setImportError(null);
        setImportStatus("polling");
      }
      setActiveJob((current) => (areStoredJobsEqual(current, nextJob) ? current : nextJob));
      return;
    }

    currentRouteJobIdRef.current = null;
    setActiveJob(null);
    setAnalysis(null);
    setImportSnapshot(null);
    setImportError(null);
    setPendingRouteImportId(null);
    setImportStatus(route.kind === "chess_com_live" ? "submitting" : "idle");
  }, [route]);

  useEffect(() => {
    if (activeJob === null) {
      return;
    }
    const job = activeJob;

    let cancelled = false;
    let timer: number | undefined;
    const abortController = new AbortController();
    const pollStartedAt = Date.now();

    async function poll() {
      try {
        const snapshot = await pollGameAnalysis(job.status_url, abortController.signal);
        if (cancelled) {
          return;
        }
        setImportSnapshot(snapshot);
        setImportError(snapshot.status === "failed" ? snapshot.error : null);
        const nextAnalysis = analysisFromSnapshot(snapshot, job.source, job.game);
        if (nextAnalysis !== null) {
          setAnalysis(nextAnalysis);
        }
        setImportStatus(
          isTerminalGameAnalysisStatus(snapshot.status)
            ? snapshot.status === "failed"
              ? "failed"
              : "succeeded"
            : "polling",
        );
        if (!isTerminalGameAnalysisStatus(snapshot.status)) {
          timer = window.setTimeout(poll, nextPollDelayMs(pollStartedAt));
        }
      } catch (error) {
        if (cancelled || isAbortError(error)) {
          return;
        }
        if (error instanceof ApiError && error.status === 429) {
          setImportStatus("polling");
          setImportError(importErrorMessage(error));
          timer = window.setTimeout(poll, retryAfterDelayMs(error));
          return;
        }
        setImportStatus("failed");
        setImportError(importErrorMessage(error));
        if (error instanceof ApiError && error.status === 404) {
          clearStoredGameAnalysisJob();
          setActiveJob(null);
        }
      }
    }

    void poll();

    return () => {
      cancelled = true;
      abortController.abort();
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, [activeJob]);

  const navigateToImportedGamePath = useCallback(
    (
      analysisId: string,
      externalGameId: string | null,
      ply: number | null,
      mode: "push" | "replace",
    ) => {
      const nextPath = canonicalPathForRoute({ analysisId, externalGameId, ply });
      if (nextPath === null) {
        return;
      }
      if (mode === "push") {
        pushPath(nextPath);
      } else {
        replacePath(nextPath);
      }
    },
    [pushPath, replacePath],
  );

  const handleImportedGameAnalysis = useCallback(
    async (request: GameAnalysisImportRequest) => {
      setImportStatus("submitting");
      setImportError(null);
      setImportSnapshot(null);
      setActiveJob(null);
      setAnalysis(null);
      try {
        const response = await startImportedGameAnalysis(request);
        const nextJob = activateImportedGameResponse(response, {
          setActiveJob,
          writeStorage: true,
        });
        currentRouteJobIdRef.current = nextJob.analysis_id;
        const importedAnalysis = mapGameAnalysisImportResponse(response);
        if (importedAnalysis !== null) {
          setAnalysis(importedAnalysis);
        }
        if (request.turnstile_token) {
          setTurnstileToken(null);
        }
        setImportStatus("polling");

        const externalGameId =
          nextJob.source?.external_game_id ??
          (request.url === undefined || request.url === null
            ? null
            : extractChessComLiveGameId(request.url));
        navigateToImportedGamePath(
          nextJob.analysis_id,
          externalGameId,
          route.ply,
          route.kind === "home" ? "push" : "replace",
        );
      } catch (error) {
        setImportStatus("failed");
        setImportError(importErrorMessage(error));
        throw error;
      }
    },
    [navigateToImportedGamePath, route.kind, route.ply],
  );

  useEffect(() => {
    if (route.kind !== "chess_com_live" || route.analysisId !== null || activeJob !== null) {
      return;
    }
    if (route.externalGameId === null) {
      return;
    }
    if (routeImportStartedRef.current === route.externalGameId) {
      return;
    }

    const externalGameId = route.externalGameId;
    routeImportStartedRef.current = externalGameId;
    let cancelled = false;
    const abortController = new AbortController();

    async function startRouteImport() {
      setImportStatus("submitting");
      setImportError(null);
      setImportSnapshot(null);
      setAnalysis(null);
      try {
        const response = await getCachedChessComLiveGameAnalysis(
          externalGameId,
          abortController.signal,
        );
        if (cancelled) {
          return;
        }
        const nextJob = activateImportedGameResponse(response, {
          setActiveJob,
          writeStorage: true,
        });
        currentRouteJobIdRef.current = nextJob.analysis_id;
        const importedAnalysis = mapGameAnalysisImportResponse(response);
        if (importedAnalysis !== null) {
          setAnalysis(importedAnalysis);
        }
        setTurnstileToken(null);
        setImportStatus("polling");
        navigateToImportedGamePath(
          nextJob.analysis_id,
          nextJob.source?.external_game_id ?? externalGameId,
          route.ply,
          "replace",
        );
      } catch (error) {
        if (cancelled || isAbortError(error)) {
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setPendingRouteImportId(externalGameId);
          setImportStatus("submitting");
          setImportError(null);
          return;
        }
        setImportStatus("failed");
        setImportError(importErrorMessage(error));
      }
    }

    void startRouteImport();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [
    activeJob,
    navigateToImportedGamePath,
    route.analysisId,
    route.externalGameId,
    route.kind,
    route.ply,
  ]);

  useEffect(() => {
    if (pendingRouteImportId === null) {
      return;
    }
    if (
      route.kind !== "chess_com_live" ||
      route.externalGameId !== pendingRouteImportId ||
      route.analysisId !== null ||
      activeJob !== null
    ) {
      return;
    }
    const needsTurnstile = isTurnstileEnabled();
    if (needsTurnstile && turnstileToken === null) {
      return;
    }

    const externalGameId = pendingRouteImportId;
    const token = turnstileToken;
    let cancelled = false;

    async function startPendingRouteImport() {
      try {
        await handleImportedGameAnalysis(buildChessComRouteImportRequest(externalGameId, token));
        if (!cancelled) {
          setPendingRouteImportId(null);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (needsTurnstile) {
          resetTurnstile();
        }
        if (!(error instanceof ApiError && error.code === "turnstile_failed")) {
          setPendingRouteImportId(null);
        }
      }
    }

    void startPendingRouteImport();

    return () => {
      cancelled = true;
    };
  }, [
    activeJob,
    handleImportedGameAnalysis,
    pendingRouteImportId,
    resetTurnstile,
    route.analysisId,
    route.externalGameId,
    route.kind,
    turnstileToken,
  ]);

  const handleOpenImport = useCallback(() => {
    clearStoredGameAnalysisJob();
    setActiveJob(null);
    setAnalysis(null);
    setImportSnapshot(null);
    setImportError(null);
    setImportStatus("idle");
    pushPath("/");
  }, [pushPath]);

  const handleClearImportError = useCallback(() => {
    setImportError(null);
    setImportStatus((current) => (current === "failed" ? "idle" : current));
  }, []);
  const shareTarget = useMemo(() => buildShareTarget(activeJob, route), [activeJob, route]);

  useDocumentTitle(
    useMemo(
      () => buildDocumentTitle({ source: activeJob?.source ?? null, importStatus }),
      [activeJob, importStatus],
    ),
  );

  if (analysis === null) {
    return (
      <AnalysisImportHome
        error={importError}
        initialUrl={importStatus === "idle" ? null : routeImportUrl}
        onClearError={handleClearImportError}
        onImport={handleImportedGameAnalysis}
        onTurnstileReset={resetTurnstile}
        onTurnstileToken={setTurnstileToken}
        status={importStatus}
        turnstileResetKey={turnstileResetKey}
        turnstileToken={turnstileToken}
      />
    );
  }

  return (
    <AnalysisGameWorkspace
      analysis={analysis}
      initialPly={route.ply}
      moveLoadingIndicator={buildMoveLoadingIndicator(importStatus, importSnapshot)}
      onOpenImport={handleOpenImport}
      shareTarget={shareTarget}
    />
  );
}

function AnalysisImportHome({
  error,
  initialUrl,
  onClearError,
  onImport,
  onTurnstileReset,
  onTurnstileToken,
  status,
  turnstileResetKey,
  turnstileToken,
}: AnalysisImportHomeProps) {
  return (
    <div className="min-h-dvh bg-white text-stone-600 dark:bg-stone-950 dark:text-stone-400">
      <main className="mx-auto flex min-h-dvh w-full max-w-[640px] flex-col justify-center px-4 pb-[10dvh] sm:px-6">
        <AnalysisImportPanel
          error={error}
          initialUrl={initialUrl}
          onClearError={onClearError}
          onImport={onImport}
          onTurnstileReset={onTurnstileReset}
          onTurnstileToken={onTurnstileToken}
          status={status}
          turnstileResetKey={turnstileResetKey}
          turnstileToken={turnstileToken}
        />
      </main>
      <WorkspaceFooter />
    </div>
  );
}

function AnalysisGameWorkspace({
  analysis,
  initialPly,
  moveLoadingIndicator,
  onOpenImport,
  shareTarget,
}: AnalysisGameWorkspaceProps) {
  const [currentPly, setCurrentPly] = useState(() =>
    clampPly(initialPly ?? 1, analysis.moves.length),
  );
  const [flippedBoard, setFlippedBoard] = useState(false);
  const [arrowCount, setArrowCount] = useState(1);
  const [showMaiaArrow, setShowMaiaArrow] = useState(false);
  const [markerDisplayMode, setMarkerDisplayMode] = useState<MarkerDisplayMode>("critical");
  const [mobileTab, setMobileTab] = useState<MobileTab>("board");
  const isDesktopLayout = useMediaQuery(DESKTOP_MEDIA_QUERY);

  const indexes = useMemo(() => buildAnalysisIndexes(analysis), [analysis]);
  const currentMove = indexes.moveByPly.get(currentPly) ?? null;
  const currentMarker = indexes.markerByPly.get(currentPly) ?? null;
  const currentTimelinePoint = indexes.timelineByPly.get(currentPly) ?? null;
  const currentFen = currentMove?.fen_after ?? analysis.moves[0]?.fen_before ?? "";
  const previousPlyRef = useRef(currentPly);
  const routePlyRef = useRef(initialPly);

  const board = useAnalysisBoard({
    baseFen: currentFen,
    currentPly,
    playerSide: analysis.player_side,
    baseHighlightedMove: currentMove?.uci ?? null,
    baseSoundKey: currentMove ? `ply:${currentMove.ply}` : null,
    baseSan: currentMove?.san ?? null,
    baseMovedByPlayer: currentMove?.side === analysis.player_side,
    onExitDiscovery: (ply) => {
      setCurrentPly(ply);
    },
  });

  const displayFen = board.displayFen ?? currentFen;
  const analysisFen = board.discovery || board.preview ? displayFen : currentFen;
  const serverEngineLines = useMemo<EngineLineSet | null>(() => {
    if (currentMarker?.best_lines.length) {
      return { fen: currentMove?.fen_before ?? currentFen, lines: currentMarker.best_lines };
    }
    if (currentTimelinePoint?.best_lines.length) {
      return { fen: currentTimelinePoint.fen_before, lines: currentTimelinePoint.best_lines };
    }
    return null;
  }, [currentFen, currentMarker, currentMove?.fen_before, currentTimelinePoint]);
  const currentBookLineSet = useMemo<BookLineSet | null>(() => {
    if (currentMarker?.primary_class !== "book") {
      return null;
    }
    const lines = currentMarker.book_lines ?? currentTimelinePoint?.book_lines ?? [];
    if (lines.length === 0) {
      return null;
    }
    return {
      fen: currentMove?.fen_after ?? currentMove?.fen_before ?? currentFen,
      lines,
    };
  }, [
    currentFen,
    currentMarker?.book_lines,
    currentMarker?.primary_class,
    currentMove?.fen_after,
    currentMove?.fen_before,
    currentTimelinePoint?.book_lines,
  ]);
  const currentOpeningName =
    currentMarker?.opening_name ?? currentTimelinePoint?.opening_name ?? null;
  const previewNeedsBrowserAnalysis = board.preview !== null && board.preview.source !== "book";
  const bookLinesVisible = !board.discovery && currentBookLineSet !== null;
  const browserAnalysisReason = browserAnalysisReasonForPosition({
    analysisFen,
    discoveryActive: Boolean(board.discovery),
    loadingActive: moveLoadingIndicator.show,
    previewActive: previewNeedsBrowserAnalysis,
    serverEngineLines,
    suppressMissingServerLines: bookLinesVisible,
  });
  const shouldAnalyzeBrowserLines = browserAnalysisReason !== null;
  const handleBookPreview = useCallback(
    (rootFen: string, lineMoves: string[], step: number) => {
      board.handlePreview(rootFen, lineMoves, step, "book");
    },
    [board.handlePreview],
  );
  const material = useMemo(() => computeCapturedMaterial(currentFen), [currentFen]);
  const boardOrientation = flippedBoard ? oppositeSide(analysis.player_side) : analysis.player_side;
  const boardTransitionMove = useMemo<BoardTransitionMove | null>(() => {
    const previousPly = previousPlyRef.current;
    if (previousPly === currentPly || Math.abs(previousPly - currentPly) !== 1) {
      return null;
    }
    const transitionPly = currentPly > previousPly ? currentPly : previousPly;
    const transitionMove = indexes.moveByPly.get(transitionPly);
    if (!transitionMove) {
      return null;
    }
    return {
      uci: transitionMove.uci,
      direction: currentPly > previousPly ? "forward" : "backward",
      key: `${previousPly}:${currentPly}:${transitionMove.uci}`,
    };
  }, [currentPly, indexes.moveByPly]);
  const topSide = boardOrientation === "white" ? "black" : "white";
  const bottomSide = boardOrientation === "white" ? "white" : "black";
  const playerMeta = buildPlayerMeta(analysis, indexes, currentPly, material);
  const fallbackEvalCp = currentTimelinePoint?.eval_cp ?? currentMarker?.eval_after_cp ?? null;

  const preAnalyzeFens = useMemo(
    () =>
      browserAnalysisReason === "missing-server-lines"
        ? buildPreAnalysisFens(analysis, indexes, currentPly, currentFen)
        : EMPTY_PRE_ANALYZE_FENS,
    [analysis, browserAnalysisReason, currentFen, currentPly, indexes],
  );

  useEffect(() => {
    setCurrentPly((ply) => clampPly(ply, analysis.moves.length));
  }, [analysis.moves.length]);

  useEffect(() => {
    if (routePlyRef.current === initialPly) {
      return;
    }
    routePlyRef.current = initialPly;
    board.clearPreview();
    board.clearDiscovery();
    setCurrentPly(clampPly(initialPly ?? 1, analysis.moves.length));
    setMobileTab("board");
  }, [analysis.moves.length, board.clearDiscovery, board.clearPreview, initialPly]);

  useEffect(() => {
    previousPlyRef.current = currentPly;
  }, [currentPly]);

  useEffect(() => {
    if (shareTarget === null) {
      return;
    }
    replaceAnalysisUrl(shareTarget, currentPly);
  }, [currentPly, shareTarget]);

  const handleSelectPly = useCallback(
    (ply: number) => {
      board.clearPreview();
      board.clearDiscovery();
      setCurrentPly(ply);
      setMobileTab("board");
    },
    [board.clearDiscovery, board.clearPreview],
  );

  const stepPly = useCallback(
    (delta: number) => {
      if (board.stepInDiscovery(delta)) {
        return;
      }
      board.clearPreview();
      setCurrentPly((ply) => Math.max(1, Math.min(analysis.moves.length, ply + delta)));
    },
    [analysis.moves.length, board.clearPreview, board.stepInDiscovery],
  );

  const goToBoundary = useCallback(
    (direction: "start" | "end") => {
      board.clearPreview();
      board.clearDiscovery();
      setCurrentPly(direction === "start" ? 1 : analysis.moves.length);
    },
    [analysis.moves.length, board.clearDiscovery, board.clearPreview],
  );

  const exitPreviewOrDiscovery = useCallback(() => {
    if (board.discovery) {
      board.exitDiscovery();
      return;
    }
    board.clearPreview();
  }, [board.clearPreview, board.discovery, board.exitDiscovery]);

  const handleFlipBoard = useCallback(() => {
    setFlippedBoard((value) => !value);
  }, []);

  return (
    <>
      <StockfishAnalysisRuntime
        analysisFen={analysisFen}
        enabled={shouldAnalyzeBrowserLines || preAnalyzeFens.length > 0}
        multiPv={3}
        preAnalyzeFens={preAnalyzeFens}
        shouldAnalyze={shouldAnalyzeBrowserLines}
        targetDepth={24}
      />
      <div className="relative min-h-dvh bg-white text-stone-600 dark:bg-stone-950 dark:text-stone-400">
        {moveLoadingIndicator.show ? (
          <WorkspaceMoveLoadingIndicator progress={moveLoadingIndicator.progress} />
        ) : null}
        <main className="mx-auto max-w-[1320px] px-3 pt-12 pb-7 sm:px-6 min-[1100px]:pt-5 min-[1100px]:pb-7">
          {isDesktopLayout ? (
            <DesktopLayout
              analysis={analysis}
              analysisFen={analysisFen}
              arrowCount={arrowCount}
              boardOrientation={boardOrientation}
              boardTransitionMove={boardTransitionMove}
              bottomSide={bottomSide}
              currentFen={currentFen}
              currentMarker={currentMarker}
              currentMove={currentMove}
              currentBookLineSet={currentBookLineSet}
              currentPly={currentPly}
              currentOpeningName={currentOpeningName}
              displayFen={displayFen}
              fallbackEvalCp={fallbackEvalCp}
              flippedBoard={flippedBoard}
              discovery={board.discovery}
              dimmed={board.dimmed}
              handleDiscoveryStepClick={board.handleDiscoveryStepClick}
              handlePieceDrop={board.handlePieceDrop}
              highlightedMove={board.highlightedMove}
              materialAdvantage={material.advantage}
              onArrowCountChange={setArrowCount}
              onMarkerDisplayModeChange={setMarkerDisplayMode}
              onExitPreview={exitPreviewOrDiscovery}
              onFlipBoard={handleFlipBoard}
              onGoToBoundary={goToBoundary}
              onOpenImport={onOpenImport}
              onBookPreview={handleBookPreview}
              onPreview={board.handlePreview}
              onSelectPly={handleSelectPly}
              onShowMaiaArrowChange={setShowMaiaArrow}
              onStepPly={stepPly}
              playerMeta={playerMeta}
              preview={board.preview}
              markerDisplayMode={markerDisplayMode}
              serverEngineLines={serverEngineLines}
              showMaiaArrow={showMaiaArrow}
              topSide={topSide}
            />
          ) : (
            <MobileLayout
              analysis={analysis}
              analysisFen={analysisFen}
              arrowCount={arrowCount}
              boardOrientation={boardOrientation}
              boardTransitionMove={boardTransitionMove}
              bottomSide={bottomSide}
              currentFen={currentFen}
              currentMarker={currentMarker}
              currentMove={currentMove}
              currentBookLineSet={currentBookLineSet}
              currentPly={currentPly}
              currentOpeningName={currentOpeningName}
              displayFen={displayFen}
              fallbackEvalCp={fallbackEvalCp}
              flippedBoard={flippedBoard}
              discovery={board.discovery}
              dimmed={board.dimmed}
              handleDiscoveryStepClick={board.handleDiscoveryStepClick}
              handlePieceDrop={board.handlePieceDrop}
              highlightedMove={board.highlightedMove}
              materialAdvantage={material.advantage}
              mobileTab={mobileTab}
              onArrowCountChange={setArrowCount}
              onMarkerDisplayModeChange={setMarkerDisplayMode}
              onExitPreview={exitPreviewOrDiscovery}
              onFlipBoard={handleFlipBoard}
              onGoToBoundary={goToBoundary}
              onOpenImport={onOpenImport}
              onBookPreview={handleBookPreview}
              onPreview={board.handlePreview}
              onSelectPly={handleSelectPly}
              onSetMobileTab={setMobileTab}
              onShowMaiaArrowChange={setShowMaiaArrow}
              onStepPly={stepPly}
              playerMeta={playerMeta}
              preview={board.preview}
              markerDisplayMode={markerDisplayMode}
              serverEngineLines={serverEngineLines}
              showMaiaArrow={showMaiaArrow}
              topSide={topSide}
            />
          )}
        </main>
        <WorkspaceFooter />
      </div>
    </>
  );
}

function WorkspaceMoveLoadingIndicator({ progress }: { progress: number | null }) {
  const width = progress === null ? 38 : Math.max(6, Math.min(100, Math.round(progress * 100)));

  return (
    <div
      aria-label="Moves are still loading"
      className="pointer-events-none absolute inset-x-0 top-0 z-50 h-px overflow-hidden bg-emerald-900/10 dark:bg-emerald-400/10"
      role="status"
    >
      <div
        className="h-full rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.55)] transition-[width] duration-500 ease-out dark:bg-emerald-400"
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function BackToImportButton({ className, onClick }: { className?: string; onClick: () => void }) {
  return (
    <button
      aria-label="Back to import"
      className={cn(
        "z-40 flex size-6 cursor-pointer items-center justify-center rounded-full text-stone-300 transition-colors hover:bg-stone-100/70 hover:text-stone-500 dark:text-stone-600 dark:hover:bg-stone-900/70 dark:hover:text-stone-400",
        className,
      )}
      onClick={onClick}
      title="Back to import"
      type="button"
    >
      <ArrowLeft className="size-3.5" />
    </button>
  );
}

function DesktopLayout({
  analysis,
  analysisFen,
  currentPly,
  currentMove,
  currentMarker,
  currentBookLineSet,
  currentOpeningName,
  currentFen,
  displayFen,
  highlightedMove,
  boardOrientation,
  boardTransitionMove,
  topSide,
  bottomSide,
  playerMeta,
  materialAdvantage,
  fallbackEvalCp,
  arrowCount,
  onArrowCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  flippedBoard,
  onFlipBoard,
  serverEngineLines,
  discovery,
  preview,
  dimmed,
  onPreview,
  onBookPreview,
  handleDiscoveryStepClick,
  handlePieceDrop,
  onSelectPly,
  onStepPly,
  onGoToBoundary,
  onOpenImport,
  onExitPreview,
}: WorkspaceLayoutProps) {
  return (
    <div className="grid gap-0 min-[1100px]:grid-cols-[minmax(0,832px)_420px]">
      <section className="flex min-h-0 min-w-0 flex-col">
        <div className="flex min-h-0 max-w-[822px] flex-col items-center px-2 pt-1">
          <div className="relative flex w-full items-stretch gap-3">
            <BackToImportButton className="-left-7 top-0.5 absolute" onClick={onOpenImport} />
            <EngineBoardSidebar
              analysisFen={analysisFen}
              arrowCount={arrowCount}
              className="flex flex-col items-center gap-2.5 py-0.5"
              fallbackEvalCp={fallbackEvalCp}
              flippedBoard={flippedBoard}
              preferBrowserEval={Boolean(discovery || preview)}
              onArrowCountChange={onArrowCountChange}
              onFlipBoard={onFlipBoard}
              onMarkerDisplayModeChange={onMarkerDisplayModeChange}
              onShowMaiaArrowChange={onShowMaiaArrowChange}
              orientation={boardOrientation}
              markerDisplayMode={markerDisplayMode}
              showMaiaArrow={showMaiaArrow}
            />
            <div className="relative flex min-w-0 flex-1 flex-col gap-2">
              <PlayerBar
                captured={playerMeta[topSide].captured}
                clockSeconds={playerMeta[topSide].clock}
                materialAdvantage={materialAdvantage}
                name={playerMeta[topSide].name}
                rating={playerMeta[topSide].rating}
                side={topSide}
              />
              <EngineAwareUltraAnalysisBoard
                allowDragging
                analysisFen={analysisFen}
                arrowCount={arrowCount}
                currentMarker={currentMarker}
                dimmed={dimmed}
                discoveryActive={Boolean(discovery)}
                fen={displayFen}
                highlightedMove={highlightedMove}
                onPieceDrop={handlePieceDrop}
                orientation={boardOrientation}
                previewActive={Boolean(preview)}
                serverEngineLines={serverEngineLines}
                shadowed={false}
                showMaiaArrow={showMaiaArrow}
                transitionMove={boardTransitionMove}
              />
              <PlayerBar
                captured={playerMeta[bottomSide].captured}
                clockSeconds={playerMeta[bottomSide].clock}
                materialAdvantage={materialAdvantage}
                name={playerMeta[bottomSide].name}
                rating={playerMeta[bottomSide].rating}
                side={bottomSide}
              />
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 px-2 pt-1 pb-2">
          <AnalysisNavigationBar
            canGoBack={currentPly > 1 || Boolean(discovery)}
            canGoForward={currentPly < analysis.moves.length || Boolean(discovery)}
            exitLabel={discovery ? "Exit analysis" : "Exit preview"}
            onExitPreview={onExitPreview}
            onGoToEnd={() => onGoToBoundary("end")}
            onGoToStart={() => onGoToBoundary("start")}
            onStepBack={() => onStepPly(-1)}
            onStepForward={() => onStepPly(1)}
            showExitPreview={Boolean(preview || discovery)}
          />
        </div>
      </section>

      <div className="flex max-h-[85vh] min-w-0 flex-col pl-5">
        <aside className="shrink-0 space-y-4 pr-1">
          <PositionInfo
            boardOrientation={boardOrientation}
            currentMove={currentMove}
            emptyMessage={ANALYSIS_LOADING_EMPTY_MESSAGE}
            emptyMessageVariant="shimmer"
            onMoveClick={onPreview}
            openingName={currentOpeningName}
            rootFen={currentMove?.fen_before ?? currentFen}
            selectedMarker={currentMarker}
          />
          {discovery && discovery.moves.length > 0 ? (
            <EngineDiscoveryLineSidebar
              analysisFen={analysisFen}
              discovery={discovery}
              fallbackEvalCp={fallbackEvalCp}
              onStepClick={handleDiscoveryStepClick}
            />
          ) : null}
          <EngineLinesSlot
            activePreview={preview}
            analysisFen={analysisFen}
            analysisPlayerSide={analysis.player_side}
            discoveryActive={Boolean(discovery)}
            displayFen={displayFen}
            bookLineSet={currentBookLineSet}
            onBookPreview={onBookPreview}
            onPreview={onPreview}
            previewActive={Boolean(preview)}
            serverEngineLines={serverEngineLines}
          />
        </aside>
        <MoveList
          className="min-h-0 flex-1 rounded-none border-0 bg-transparent"
          currentPly={currentPly}
          markerDisplayMode={markerDisplayMode}
          moveMarkers={analysis.move_markers}
          moves={analysis.moves}
          onSelectPly={onSelectPly}
        />
      </div>
    </div>
  );
}

function MobileLayout({
  analysis,
  analysisFen,
  currentPly,
  currentMove,
  currentMarker,
  currentBookLineSet,
  currentOpeningName,
  displayFen,
  highlightedMove,
  boardOrientation,
  boardTransitionMove,
  topSide,
  bottomSide,
  playerMeta,
  materialAdvantage,
  arrowCount,
  fallbackEvalCp,
  serverEngineLines,
  showMaiaArrow,
  flippedBoard,
  discovery,
  preview,
  dimmed,
  markerDisplayMode,
  onArrowCountChange,
  onMarkerDisplayModeChange,
  onFlipBoard,
  onShowMaiaArrowChange,
  onPreview,
  onBookPreview,
  handleDiscoveryStepClick,
  handlePieceDrop,
  onSelectPly,
  onStepPly,
  onGoToBoundary,
  onOpenImport,
  onExitPreview,
  mobileTab,
  onSetMobileTab,
}: MobileLayoutProps) {
  return (
    <div className="relative mx-auto max-w-[760px]">
      <BackToImportButton className="-top-11 left-0 absolute" onClick={onOpenImport} />
      <MobileViewSwitcher activeTab={mobileTab} onChange={onSetMobileTab} />
      {mobileTab === "board" ? (
        <div className="mx-auto w-full max-w-[min(720px,max(360px,calc(100dvh-16rem)))] space-y-2.5">
          <MobileBoardControls
            analysisFen={analysisFen}
            arrowCount={arrowCount}
            fallbackEvalCp={fallbackEvalCp}
            flippedBoard={flippedBoard}
            markerDisplayMode={markerDisplayMode}
            onArrowCountChange={onArrowCountChange}
            onFlipBoard={onFlipBoard}
            onMarkerDisplayModeChange={onMarkerDisplayModeChange}
            onShowMaiaArrowChange={onShowMaiaArrowChange}
            preferBrowserEval={Boolean(discovery || preview)}
            showMaiaArrow={showMaiaArrow}
          />
          <div className="space-y-2.5 border-stone-200 border-y py-3 dark:border-stone-800">
            <PlayerBar
              captured={playerMeta[topSide].captured}
              clockSeconds={playerMeta[topSide].clock}
              materialAdvantage={materialAdvantage}
              name={playerMeta[topSide].name}
              rating={playerMeta[topSide].rating}
              side={topSide}
            />
            <EngineAwareUltraAnalysisBoard
              allowDragging
              analysisFen={analysisFen}
              arrowCount={arrowCount}
              currentMarker={currentMarker}
              dimmed={dimmed}
              discoveryActive={Boolean(discovery)}
              fen={displayFen}
              highlightedMove={highlightedMove}
              onPieceDrop={handlePieceDrop}
              orientation={boardOrientation}
              previewActive={Boolean(preview)}
              serverEngineLines={serverEngineLines}
              shadowed={false}
              showMaiaArrow={showMaiaArrow}
              transitionMove={boardTransitionMove}
            />
            <PlayerBar
              captured={playerMeta[bottomSide].captured}
              clockSeconds={playerMeta[bottomSide].clock}
              materialAdvantage={materialAdvantage}
              name={playerMeta[bottomSide].name}
              rating={playerMeta[bottomSide].rating}
              side={bottomSide}
            />
          </div>
          {discovery ? (
            <DiscoveryLineBar
              discovery={discovery}
              onExit={onExitPreview}
              onStepClick={handleDiscoveryStepClick}
            />
          ) : null}
          <AnalysisNavigationBar
            canGoBack={currentPly > 1 || Boolean(discovery)}
            canGoForward={currentPly < analysis.moves.length || Boolean(discovery)}
            exitLabel={discovery ? "Exit analysis" : "Exit preview"}
            onExitPreview={onExitPreview}
            onGoToEnd={() => onGoToBoundary("end")}
            onGoToStart={() => onGoToBoundary("start")}
            onStepBack={() => onStepPly(-1)}
            onStepForward={() => onStepPly(1)}
            showExitPreview={Boolean(preview || discovery)}
          />
        </div>
      ) : null}
      {mobileTab === "moves" ? (
        <MoveList
          className="h-[calc(100dvh-8rem)] min-h-[360px]"
          currentPly={currentPly}
          markerDisplayMode={markerDisplayMode}
          moveMarkers={analysis.move_markers}
          moves={analysis.moves}
          onSelectPly={onSelectPly}
        />
      ) : null}
      {mobileTab === "analysis" ? (
        <div className="grid gap-4">
          <PositionInfo
            boardOrientation={boardOrientation}
            currentMove={currentMove}
            emptyMessage={ANALYSIS_LOADING_EMPTY_MESSAGE}
            emptyMessageVariant="shimmer"
            onMoveClick={onPreview}
            openingName={currentOpeningName}
            rootFen={currentMove?.fen_before ?? null}
            selectedMarker={currentMarker}
          />
          {discovery && discovery.moves.length > 0 ? (
            <EngineDiscoveryLineSidebar
              analysisFen={analysisFen}
              discovery={discovery}
              fallbackEvalCp={fallbackEvalCp}
              onStepClick={handleDiscoveryStepClick}
            />
          ) : null}
          <EngineLinesSlot
            activePreview={preview}
            analysisFen={analysisFen}
            analysisPlayerSide={analysis.player_side}
            discoveryActive={Boolean(discovery)}
            displayFen={displayFen}
            bookLineSet={currentBookLineSet}
            onBookPreview={onBookPreview}
            onPreview={onPreview}
            previewActive={Boolean(preview)}
            serverEngineLines={serverEngineLines}
          />
        </div>
      ) : null}
    </div>
  );
}

function MobileViewSwitcher({
  activeTab,
  onChange,
}: {
  activeTab: MobileTab;
  onChange: (tab: MobileTab) => void;
}) {
  return (
    <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg bg-stone-100/80 p-1 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)] backdrop-blur-sm dark:bg-stone-900/80 dark:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]">
      {MOBILE_TAB_ITEMS.map((tab) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;
        return (
          <button
            aria-pressed={active}
            className={cn(
              "flex h-11 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-md px-2 text-sm font-medium transition-[background-color,box-shadow,color,transform] active:scale-[0.96]",
              active
                ? "bg-white text-stone-950 shadow-sm shadow-stone-950/5 dark:bg-stone-800 dark:text-stone-100 dark:shadow-black/20"
                : "text-stone-500 hover:bg-white/50 hover:text-stone-800 dark:text-stone-400 dark:hover:bg-stone-800/50 dark:hover:text-stone-200",
            )}
            key={tab.id}
            onClick={() => onChange(tab.id)}
            type="button"
          >
            <Icon className="size-4 shrink-0" />
            <span className="truncate">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function MobileBoardControls({
  analysisFen,
  fallbackEvalCp,
  preferBrowserEval,
  arrowCount,
  onArrowCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  flippedBoard,
  onFlipBoard,
}: {
  analysisFen: string;
  fallbackEvalCp: number | null;
  preferBrowserEval: boolean;
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  flippedBoard: boolean;
  onFlipBoard: () => void;
}) {
  const evalCp = useDisplayEvalCp(analysisFen, fallbackEvalCp, preferBrowserEval);

  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-stone-100/75 p-1 shadow-[inset_0_0_0_1px_rgba(68,64,60,0.06)] dark:bg-stone-900/75 dark:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]">
      <div className="flex items-center gap-1">
        <AnalysisSettingsPopover
          arrowCount={arrowCount}
          buttonClassName="size-10 rounded-md"
          markerDisplayMode={markerDisplayMode}
          onArrowCountChange={onArrowCountChange}
          onMarkerDisplayModeChange={onMarkerDisplayModeChange}
          onShowMaiaArrowChange={onShowMaiaArrowChange}
          placement="bottom-start"
          showMaiaArrow={showMaiaArrow}
        />
        <button
          aria-label="Flip board"
          className="flex size-10 cursor-pointer items-center justify-center rounded-md text-stone-500 transition-[background-color,color,transform] hover:bg-white/70 hover:text-stone-950 active:scale-[0.96] dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-50"
          onClick={onFlipBoard}
          title="Flip board"
          type="button"
        >
          <ArrowUpDown
            className={cn(
              "size-4 transition-transform duration-300 ease-out",
              flippedBoard && "rotate-180",
            )}
          />
        </button>
      </div>
      <output
        aria-label={`Evaluation ${formatEval(evalCp)}`}
        className="flex h-10 min-w-0 items-center gap-2 rounded-md bg-white px-3 text-stone-700 shadow-sm shadow-stone-950/5 dark:bg-stone-800 dark:text-stone-200 dark:shadow-black/20"
      >
        <Activity className="size-4 shrink-0 text-stone-400 dark:text-stone-500" />
        <span className="min-w-[3.25rem] text-right font-mono text-sm font-semibold tabular-nums">
          {formatEval(evalCp)}
        </span>
      </output>
    </div>
  );
}

function EngineBoardSidebar({
  analysisFen,
  fallbackEvalCp,
  preferBrowserEval,
  ...props
}: {
  analysisFen: string;
  fallbackEvalCp: number | null;
  preferBrowserEval: boolean;
  orientation: BoardSide;
  flippedBoard: boolean;
  onFlipBoard: () => void;
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  className?: string;
}) {
  const evalCp = useDisplayEvalCp(analysisFen, fallbackEvalCp, preferBrowserEval);

  return <BoardSidebar {...props} evalCp={evalCp} />;
}

function EngineAwareUltraAnalysisBoard({
  analysisFen,
  arrowCount,
  currentMarker,
  discoveryActive,
  previewActive,
  serverEngineLines,
  showMaiaArrow,
  ...props
}: {
  analysisFen: string;
  arrowCount: number;
  currentMarker: AnalysisMoveMarker | null;
  discoveryActive: boolean;
  previewActive: boolean;
  serverEngineLines: EngineLineSet | null;
  showMaiaArrow: boolean;
  allowDragging?: boolean;
  dimmed?: boolean;
  fen: string;
  highlightedMove: string | null;
  onPieceDrop: (args: {
    sourceSquare: string;
    targetSquare: string | null;
    piece: string;
  }) => boolean;
  orientation: BoardSide;
  shadowed?: boolean;
  transitionMove: BoardTransitionMove | null;
}) {
  const usesBrowserArrows =
    !previewActive && (discoveryActive || (!currentMarker && serverEngineLines === null));
  const browserArrows = useBrowserEngineArrows(usesBrowserArrows ? analysisFen : null, arrowCount);
  const arrows = useMemo(() => {
    if (previewActive) {
      return EMPTY_BOARD_ARROWS;
    }
    if (discoveryActive) {
      return browserArrows;
    }
    if (currentMarker) {
      return buildMarkerArrows(currentMarker, arrowCount, showMaiaArrow);
    }
    if (serverEngineLines) {
      return buildEngineArrows(serverEngineLines.lines, arrowCount);
    }
    return browserArrows;
  }, [
    arrowCount,
    browserArrows,
    currentMarker,
    discoveryActive,
    previewActive,
    serverEngineLines,
    showMaiaArrow,
  ]);

  return <UltraAnalysisBoard {...props} arrows={arrows} />;
}

function EngineDiscoveryLineSidebar({
  analysisFen,
  discovery,
  fallbackEvalCp,
  onStepClick,
}: {
  analysisFen: string;
  discovery: DiscoveryState;
  fallbackEvalCp: number | null;
  onStepClick: (step: number) => void;
}) {
  const evalCp = useDisplayEvalCp(analysisFen, fallbackEvalCp, true);

  return <DiscoveryLineSidebar discovery={discovery} evalCp={evalCp} onStepClick={onStepClick} />;
}

function EngineLinesSlot({
  activePreview,
  analysisFen,
  analysisPlayerSide,
  bookLineSet,
  discoveryActive,
  displayFen,
  onBookPreview,
  onPreview,
  previewActive,
  serverEngineLines,
}: {
  activePreview: PreviewState | null;
  analysisFen: string;
  analysisPlayerSide: BoardSide;
  bookLineSet: BookLineSet | null;
  discoveryActive: boolean;
  displayFen: string;
  onBookPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  onPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  previewActive: boolean;
  serverEngineLines: EngineLineSet | null;
}) {
  const browserEngineLines = useBrowserEngineLines(analysisFen);

  if (!discoveryActive && bookLineSet?.lines.length) {
    return (
      <BookLinesView
        activePreview={activePreview}
        bookLines={bookLineSet.lines}
        onPreview={onBookPreview}
        rootFen={bookLineSet.fen}
      />
    );
  }

  const engineLines = selectDisplayedEngineLines({
    browserEngineLines,
    discoveryActive,
    serverEngineLines,
  });

  if (!engineLines) {
    return null;
  }

  const playerSideForLines =
    discoveryActive || previewActive
      ? sideToMoveFromFen(engineLines.fen || displayFen)
      : analysisPlayerSide;

  return (
    <EngineLinesView
      activePreview={activePreview}
      lines={engineLines.lines}
      onPreview={onPreview}
      playerSide={playerSideForLines}
      rootFen={engineLines.fen}
    />
  );
}

export function selectDisplayedEngineLines({
  browserEngineLines,
  discoveryActive,
  serverEngineLines,
}: {
  browserEngineLines: EngineLineSet | null;
  discoveryActive: boolean;
  serverEngineLines: EngineLineSet | null;
}): EngineLineSet | null {
  if (discoveryActive) {
    return browserEngineLines;
  }
  return serverEngineLines ?? browserEngineLines;
}

function useDisplayEvalCp(
  analysisFen: string,
  fallbackEvalCp: number | null,
  preferBrowserEval: boolean,
): number | null {
  const selectBrowserEval = useCallback(
    (snapshot: StockfishAnalysisSnapshot): BrowserEvalSnapshot => {
      const matchesPosition = snapshot.fen === analysisFen;
      const evalCp =
        matchesPosition && snapshot.evalCp !== null && snapshot.depth >= MIN_BROWSER_EVAL_BAR_DEPTH
          ? snapshot.evalCp
          : null;
      return { evalCp, matchesPosition };
    },
    [analysisFen],
  );
  const browserEval = useStockfishAnalysisSelector(selectBrowserEval, areBrowserEvalSnapshotsEqual);
  const nextEvalCp = preferBrowserEval
    ? (browserEval.evalCp ?? fallbackEvalCp)
    : browserEval.matchesPosition
      ? (browserEval.evalCp ?? fallbackEvalCp)
      : (fallbackEvalCp ?? browserEval.evalCp);

  return useRetainedEvalCp(nextEvalCp, analysisFen);
}

function useBrowserEngineLines(analysisFen: string): EngineLineSet | null {
  const selectBrowserEngineLines = useCallback(
    (snapshot: StockfishAnalysisSnapshot): EngineLineSet | null => {
      if (snapshot.fen !== analysisFen || snapshot.lines.length === 0) {
        return null;
      }
      return { fen: analysisFen, lines: snapshot.lines };
    },
    [analysisFen],
  );

  return useStockfishAnalysisSelector(selectBrowserEngineLines, areEngineLineSetsEqual);
}

function useBrowserEngineArrows(analysisFen: string | null, arrowCount: number): BoardArrow[] {
  const selectBrowserEngineArrows = useCallback(
    (snapshot: StockfishAnalysisSnapshot): BoardArrow[] => {
      if (!analysisFen || snapshot.fen !== analysisFen || snapshot.lines.length === 0) {
        return EMPTY_BOARD_ARROWS;
      }
      return buildEngineArrows(snapshot.lines, arrowCount);
    },
    [analysisFen, arrowCount],
  );

  return useStockfishAnalysisSelector(selectBrowserEngineArrows, areBoardArrowsEqual);
}

interface BrowserEvalSnapshot {
  evalCp: number | null;
  matchesPosition: boolean;
}

function areBrowserEvalSnapshotsEqual(
  previous: BrowserEvalSnapshot,
  next: BrowserEvalSnapshot,
): boolean {
  return (
    previous.matchesPosition === next.matchesPosition && Object.is(previous.evalCp, next.evalCp)
  );
}

function areEngineLineSetsEqual(
  previous: EngineLineSet | null,
  next: EngineLineSet | null,
): boolean {
  if (previous === next) {
    return true;
  }
  if (!previous || !next) {
    return false;
  }
  return previous.fen === next.fen && previous.lines === next.lines;
}

function areBoardArrowsEqual(previous: BoardArrow[], next: BoardArrow[]): boolean {
  if (previous === next) {
    return true;
  }
  if (previous.length !== next.length) {
    return false;
  }
  return previous.every((arrow, index) => {
    const nextArrow = next[index];
    return (
      nextArrow !== undefined &&
      arrow[0] === nextArrow[0] &&
      arrow[1] === nextArrow[1] &&
      arrow[2] === nextArrow[2]
    );
  });
}

interface WorkspaceLayoutProps {
  analysis: AnalysisResponse;
  analysisFen: string;
  currentPly: number;
  currentMove: GameMove | null;
  currentMarker: AnalysisMoveMarker | null;
  currentBookLineSet: BookLineSet | null;
  currentOpeningName: string | null;
  currentFen: string;
  displayFen: string;
  highlightedMove: string | null;
  boardOrientation: BoardSide;
  boardTransitionMove: BoardTransitionMove | null;
  topSide: BoardSide;
  bottomSide: BoardSide;
  playerMeta: PlayerMeta;
  materialAdvantage: number;
  fallbackEvalCp: number | null;
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  flippedBoard: boolean;
  onFlipBoard: () => void;
  serverEngineLines: EngineLineSet | null;
  discovery: DiscoveryState | null;
  preview: PreviewState | null;
  dimmed: boolean;
  onPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  onBookPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  handleDiscoveryStepClick: (step: number) => void;
  handlePieceDrop: (args: {
    sourceSquare: string;
    targetSquare: string | null;
    piece: string;
  }) => boolean;
  onSelectPly: (ply: number) => void;
  onStepPly: (delta: number) => void;
  onGoToBoundary: (direction: "start" | "end") => void;
  onOpenImport: () => void;
  onExitPreview: () => void;
}

interface MobileLayoutProps extends WorkspaceLayoutProps {
  mobileTab: MobileTab;
  onSetMobileTab: (tab: MobileTab) => void;
}

interface PlayerMeta {
  white: PlayerMetaSide;
  black: PlayerMetaSide;
}

interface PlayerMetaSide {
  name: string;
  rating: number | null;
  captured: ReturnType<typeof computeCapturedMaterial>["white"];
  clock: number | undefined;
}

function selectInitialJob(
  route: AnalysisRouteState,
  storedJob: StoredGameAnalysisJob | null,
): StoredGameAnalysisJob | null {
  if (route.analysisId !== null) {
    return {
      analysis_id: route.analysisId,
      status_url:
        storedJob?.analysis_id === route.analysisId
          ? storedJob.status_url
          : analysisStatusUrl(route.analysisId),
      source: sourceForRoute(route, storedJob),
      game: storedJob?.analysis_id === route.analysisId ? storedJob.game : null,
    };
  }

  if (route.kind === "chess_com_live") {
    return storedJob?.source?.external_game_id === route.externalGameId ? storedJob : null;
  }

  return null;
}

function sourceForRoute(
  route: AnalysisRouteState,
  storedJob: StoredGameAnalysisJob | null,
): ImportedGameMetadata | null {
  if (route.externalGameId === null) {
    return storedJob?.analysis_id === route.analysisId ? storedJob.source : null;
  }
  if (storedJob?.source?.external_game_id === route.externalGameId) {
    return storedJob.source;
  }
  return sourceFromExternalGameId(route.externalGameId);
}

function sourceFromExternalGameId(externalGameId: string): ImportedGameMetadata {
  return {
    source: "chess_com_live_url",
    source_url: chessComLiveGameUrl(externalGameId),
    external_game_id: externalGameId,
    title: `Chess.com game ${externalGameId}`,
    white_username: null,
    black_username: null,
    white_rating: null,
    black_rating: null,
    time_control: null,
    result: null,
    allows_global_training: false,
    rights_basis: "Public Chess.com game link.",
  };
}

function buildChessComRouteImportRequest(
  externalGameId: string,
  turnstileToken: string | null,
): GameAnalysisImportRequest {
  const request: GameAnalysisImportRequest = {
    source: "chess_com_live_url",
    url: chessComLiveGameUrl(externalGameId),
    explain_significance: ["critical"],
    include_context: true,
    use_baseline_fallback: false,
  };
  if (turnstileToken !== null) {
    request.turnstile_token = turnstileToken;
  }
  return request;
}

function activateImportedGameResponse(
  response: {
    analysis_id: string;
    status_url: string;
    source: ImportedGameMetadata;
    game?: GameAnalysisGame | null;
  },
  {
    setActiveJob,
    writeStorage,
  }: {
    setActiveJob: (job: StoredGameAnalysisJob) => void;
    writeStorage: boolean;
  },
): StoredGameAnalysisJob {
  const nextJob: StoredGameAnalysisJob = {
    analysis_id: response.analysis_id,
    status_url: response.status_url,
    source: response.source,
    game: response.game ?? null,
  };
  if (writeStorage) {
    writeStoredGameAnalysisJob(nextJob);
  }
  setActiveJob(nextJob);
  return nextJob;
}

function areStoredJobsEqual(
  current: StoredGameAnalysisJob | null,
  next: StoredGameAnalysisJob,
): boolean {
  return (
    current !== null &&
    current.analysis_id === next.analysis_id &&
    current.status_url === next.status_url &&
    current.source?.external_game_id === next.source?.external_game_id &&
    current.game?.total_plies === next.game?.total_plies
  );
}

function buildShareTarget(
  job: StoredGameAnalysisJob | null,
  route: AnalysisRouteState,
): SharedAnalysisTarget | null {
  if (job === null) {
    return null;
  }
  return {
    analysisId: job.analysis_id,
    externalGameId: job.source?.external_game_id ?? route.externalGameId,
  };
}

function clampPly(ply: number, moveCount: number): number {
  return Math.max(1, Math.min(Math.max(moveCount, 1), ply));
}

function readStoredGameAnalysisJob(): StoredGameAnalysisJob | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(GAME_ANALYSIS_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<StoredGameAnalysisJob>;
    if (typeof parsed.analysis_id !== "string" || typeof parsed.status_url !== "string") {
      return null;
    }
    return {
      analysis_id: parsed.analysis_id,
      status_url: parsed.status_url,
      source: parsed.source ?? null,
      game: parsed.game ?? null,
    };
  } catch {
    return null;
  }
}

function analysisFromSnapshot(
  snapshot: GameAnalysisSnapshot,
  source: ImportedGameMetadata | null,
  fallbackGame: GameAnalysisGame | null,
): AnalysisResponse | null {
  const game = snapshot.game ?? fallbackGame;
  if (game?.moves.length || snapshot.moves.some((move) => move.context !== null)) {
    return mapGameAnalysisSnapshot(snapshot, source, game ?? null);
  }
  return null;
}

function writeStoredGameAnalysisJob(job: StoredGameAnalysisJob): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(GAME_ANALYSIS_STORAGE_KEY, JSON.stringify(job));
  } catch {
    // Browser storage can be unavailable in private or locked-down sessions.
  }
}

function clearStoredGameAnalysisJob(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(GAME_ANALYSIS_STORAGE_KEY);
  } catch {
    // Browser storage can be unavailable in private or locked-down sessions.
  }
}

function importErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429 && error.retryAfterSeconds !== null) {
      return `Too many requests. Try again in ${formatRetryAfter(error.retryAfterSeconds)}.`;
    }
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Import failed.";
}

function nextPollDelayMs(pollStartedAt: number): number {
  const elapsedMs = Date.now() - pollStartedAt;
  if (elapsedMs < 20_000) {
    return 1200;
  }
  if (elapsedMs < 120_000) {
    return 3000;
  }
  return 7000;
}

function retryAfterDelayMs(error: ApiError): number {
  return Math.max(1000, (error.retryAfterSeconds ?? 5) * 1000);
}

function formatRetryAfter(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} second${seconds === 1 ? "" : "s"}`;
  }
  const minutes = Math.ceil(seconds / 60);
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

function buildMoveLoadingIndicator(
  status: ImportPanelStatus,
  snapshot: GameAnalysisSnapshot | null,
): MoveLoadingIndicatorState {
  if (status !== "submitting" && status !== "polling") {
    return { show: false, progress: null };
  }
  if (snapshot === null || snapshot.total_plies <= 0) {
    return { show: true, progress: null };
  }
  return {
    show: snapshot.context_completed < snapshot.total_plies,
    progress: snapshot.context_completed / snapshot.total_plies,
  };
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => readMediaQuery(query));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const mediaQuery = window.matchMedia(query);
    const handleChange = () => setMatches(mediaQuery.matches);
    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [query]);

  return matches;
}

function readMediaQuery(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(query).matches;
}

export function buildAnalysisIndexes(analysis: AnalysisResponse) {
  return {
    moveByPly: new Map(analysis.moves.map((move) => [move.ply, move])),
    markerByPly: new Map(analysis.move_markers.map((marker) => [marker.ply, marker])),
    timelineByPly: new Map(analysis.timeline.map((point) => [point.ply, point])),
  };
}

export function browserAnalysisReasonForPosition({
  analysisFen,
  discoveryActive,
  loadingActive = false,
  previewActive,
  serverEngineLines,
  suppressMissingServerLines = false,
}: {
  analysisFen: string;
  discoveryActive: boolean;
  loadingActive?: boolean;
  previewActive: boolean;
  serverEngineLines: EngineLineSet | null;
  suppressMissingServerLines?: boolean;
}): BrowserAnalysisReason | null {
  if (!analysisFen) {
    return null;
  }
  if (discoveryActive) {
    return "discovery";
  }
  if (previewActive) {
    return "preview";
  }
  if (suppressMissingServerLines) {
    return null;
  }
  if (serverEngineLines !== null) {
    return null;
  }
  return loadingActive ? "loading" : "missing-server-lines";
}

export function buildPreAnalysisFens(
  analysis: AnalysisResponse,
  indexes: ReturnType<typeof buildAnalysisIndexes>,
  currentPly: number,
  currentFen: string,
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const addFen = (fen: string | null | undefined) => {
    if (!fen || seen.has(fen) || out.length >= MAX_PRE_ANALYZE_FENS) {
      return;
    }
    seen.add(fen);
    out.push(fen);
  };

  addFen(currentFen);
  for (let distance = 1; distance <= PRE_ANALYZE_NEIGHBOR_PLIES; distance += 1) {
    addFen(indexes.moveByPly.get(currentPly + distance)?.fen_after);
    addFen(indexes.moveByPly.get(currentPly - distance)?.fen_after);
    addFen(indexes.timelineByPly.get(currentPly + distance)?.fen_before);
    addFen(indexes.timelineByPly.get(currentPly - distance)?.fen_before);
  }

  const nearbyMarkers = [...analysis.move_markers].sort(
    (a, b) => Math.abs(a.ply - currentPly) - Math.abs(b.ply - currentPly),
  );
  for (const marker of nearbyMarkers) {
    addFen(indexes.moveByPly.get(marker.ply)?.fen_before);
    if (out.length >= MAX_PRE_ANALYZE_FENS) {
      break;
    }
  }

  return out;
}

function buildPlayerMeta(
  analysis: AnalysisResponse,
  indexes: ReturnType<typeof buildAnalysisIndexes>,
  currentPly: number,
  material: ReturnType<typeof computeCapturedMaterial>,
): PlayerMeta {
  let whiteClock: number | undefined;
  let blackClock: number | undefined;
  for (let ply = 1; ply <= currentPly; ply += 1) {
    const move = indexes.moveByPly.get(ply);
    if (move?.side === "white") {
      whiteClock = move.remaining_clock_seconds;
    }
    if (move?.side === "black") {
      blackClock = move.remaining_clock_seconds;
    }
  }
  return {
    white: {
      name: analysis.headers.White ?? "White",
      rating: toRating(analysis.headers.WhiteElo),
      captured: material.white,
      clock: whiteClock,
    },
    black: {
      name: analysis.headers.Black ?? "Black",
      rating: toRating(analysis.headers.BlackElo),
      captured: material.black,
      clock: blackClock,
    },
  };
}

function useRetainedEvalCp(nextEvalCp: number | null, positionKey: string): number | null {
  const retainedRef = useRef({ evalCp: nextEvalCp, positionKey });

  if (retainedRef.current.positionKey !== positionKey) {
    retainedRef.current = { evalCp: nextEvalCp, positionKey };
  } else if (nextEvalCp !== null) {
    retainedRef.current.evalCp = nextEvalCp;
  }

  return nextEvalCp ?? retainedRef.current.evalCp;
}

function buildEngineArrows(lines: BestLine[], arrowCount: number): BoardArrow[] {
  if (arrowCount <= 0 || lines.length === 0) {
    return EMPTY_BOARD_ARROWS;
  }

  const best = lines[0]?.eval_cp;
  if (best === undefined) {
    return EMPTY_BOARD_ARROWS;
  }
  const bestIsMate = Math.abs(best) >= 20_000;
  const nextArrows: BoardArrow[] = [];
  for (const [index, line] of lines.slice(0, arrowCount).entries()) {
    if (index > 0) {
      if (bestIsMate && Math.abs(line.eval_cp) < 20_000) {
        break;
      }
      if (Math.abs(best - line.eval_cp) > 50) {
        break;
      }
    }
    const squares = uciToSquares(line.uci);
    if (squares) {
      nextArrows.push([
        squares[0],
        squares[1],
        ENGINE_ARROW_COLORS[index] ?? ENGINE_ARROW_COLORS[0],
      ]);
    }
  }

  return nextArrows;
}

function buildMarkerArrows(
  currentMarker: AnalysisMoveMarker,
  arrowCount: number,
  showMaiaArrow: boolean,
): BoardArrow[] {
  if (arrowCount <= 0 && !showMaiaArrow) {
    return EMPTY_BOARD_ARROWS;
  }

  const skipEngineArrows =
    currentMarker.primary_class === "best" ||
    currentMarker.primary_class === "excellent" ||
    currentMarker.primary_class === "book";
  const nextArrows = skipEngineArrows
    ? []
    : buildEngineArrows(currentMarker.best_lines, arrowCount);

  if (
    showMaiaArrow &&
    currentMarker.natural_move_uci &&
    currentMarker.natural_move_uci !== currentMarker.uci
  ) {
    const squares = uciToSquares(currentMarker.natural_move_uci);
    const alreadyShown = squares
      ? nextArrows.some(([from, to]) => from === squares[0] && to === squares[1])
      : true;
    if (squares && !alreadyShown) {
      nextArrows.push([squares[0], squares[1], MAIA_ARROW_COLOR]);
    }
  }

  return nextArrows;
}

function oppositeSide(side: BoardSide): BoardSide {
  return side === "white" ? "black" : "white";
}

function toRating(value: string | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
