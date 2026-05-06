import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CornerUpLeft,
  FileText,
  ListOrdered,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  type ExternalGameOrientation,
  type ExternalGameSource,
  type ExternalGameTarget,
  extractGameImportTarget,
  lichessGameUrl,
  pushWithPath,
  readAnalysisRoute,
  replaceAnalysisUrl,
  replaceWithPath,
  type SharedAnalysisTarget,
} from "../../lib/analysis-routing";
import {
  ApiError,
  getCachedChessComLiveGameAnalysis,
  getCachedLichessGameAnalysis,
  pollGameAnalysis,
  startImportedGameAnalysis,
} from "../../lib/api";
import {
  computeCapturedMaterial,
  ENGINE_ARROW_COLORS,
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
import { triggerHaptic } from "../../lib/haptics";
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
import { BookLinesView, type EngineContinuationLine, EngineLinesView } from "./EngineLinesView";
import { HorizontalEvalBar } from "./EvalBar";
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
const EMPTY_BEST_LINES: BestLine[] = [];
const DESKTOP_MEDIA_QUERY = "(min-width: 1100px)";
const MIN_BROWSER_EVAL_BAR_DEPTH = 13;
const MAX_PRE_ANALYZE_FENS = 12;
const PRE_ANALYZE_NEIGHBOR_PLIES = 4;
const WHEEL_MOVE_NAVIGATION_COOLDOWN_MS = 45;
const WHEEL_MOVE_NAVIGATION_MIN_DELTA = 12;
const WHEEL_MOVE_NAVIGATION_DELTA_PER_PLY = 48;
const EMPTY_PRE_ANALYZE_FENS: string[] = [];
const GAME_ANALYSIS_STORAGE_KEY = "g6explanation.currentGameAnalysis";
const ANALYSIS_LOADING_EMPTY_MESSAGE = "Crunching the analysis. The board is yours to explore";
type MobileTab = "moves" | "analysis";

interface StoredGameAnalysisJob {
  analysis_id: string;
  status_url: string;
  source: ImportedGameMetadata | null;
  game: GameAnalysisGame | null;
  boardOrientation: ExternalGameOrientation | null;
}

interface AnalysisImportHomeProps {
  status: ImportPanelStatus;
  error: string | null;
  initialUrl: string | null;
  onImport: (
    request: GameAnalysisImportRequest,
    hintedTarget?: ExternalGameTarget | null,
  ) => Promise<void>;
  onClearError: () => void;
  turnstileToken: string | null;
  turnstileResetKey: number;
  turnstileRequired: boolean;
  onTurnstileToken: (token: string | null) => void;
  onTurnstileReset: () => void;
}

interface AnalysisGameWorkspaceProps {
  analysis: AnalysisResponse;
  initialPly: number | null;
  initialBoardOrientation: ExternalGameOrientation | null;
  activeBoardOrientation: ExternalGameOrientation | null;
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
    route.externalSource !== null && route.externalGameId !== null
      ? sourceUrlForTarget({
          source: route.externalSource,
          externalGameId: route.externalGameId,
          boardOrientation: route.boardOrientation,
        })
      : null;
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [activeJob, setActiveJob] = useState<StoredGameAnalysisJob | null>(initialJob);
  const activeBoardOrientation = route.boardOrientation ?? activeJob?.boardOrientation ?? null;
  const [importStatus, setImportStatus] = useState<ImportPanelStatus>(
    initialJob ? "polling" : isExternalGameRoute(initialRoute) ? "submitting" : "idle",
  );
  const [importSnapshot, setImportSnapshot] = useState<GameAnalysisSnapshot | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [pendingRouteImportTarget, setPendingRouteImportTarget] =
    useState<ExternalGameTarget | null>(null);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [turnstileRequired, setTurnstileRequired] = useState(false);
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
    const target = externalTargetFromRoute(route);
    if (target === null || target.boardOrientation !== null || activeBoardOrientation === null) {
      return;
    }
    const nextPath = canonicalPathForRoute({
      analysisId: route.analysisId,
      externalSource: target.source,
      externalGameId: target.externalGameId,
      boardOrientation: activeBoardOrientation,
      ply: route.ply,
    });
    if (nextPath !== null && nextPath !== currentBrowserPath()) {
      replacePath(nextPath);
    }
  }, [activeBoardOrientation, replacePath, route]);

  useEffect(() => {
    if (route.kind === "home") {
      currentRouteJobIdRef.current = null;
      routeImportStartedRef.current = null;
      setActiveJob(null);
      setAnalysis(null);
      setImportSnapshot(null);
      setImportError(null);
      setImportStatus("idle");
      setPendingRouteImportTarget(null);
      setTurnstileRequired(false);
      return;
    }

    const nextJob = selectInitialJob(route, readStoredGameAnalysisJob());
    if (nextJob !== null) {
      const jobChanged = currentRouteJobIdRef.current !== nextJob.analysis_id;
      currentRouteJobIdRef.current = nextJob.analysis_id;
      routeImportStartedRef.current = null;
      setPendingRouteImportTarget(null);
      setTurnstileRequired(false);
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
    setPendingRouteImportTarget(null);
    setTurnstileRequired(false);
    setImportStatus(isExternalGameRoute(route) ? "submitting" : "idle");
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
      target: ExternalGameTarget | null,
      ply: number | null,
      mode: "push" | "replace",
    ) => {
      const nextPath = canonicalPathForRoute({
        analysisId,
        externalSource: target?.source ?? null,
        externalGameId: target?.externalGameId ?? null,
        boardOrientation: target?.boardOrientation ?? null,
        ply,
      });
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
  const routeExternalTarget = useMemo(() => externalTargetFromRoute(route), [route]);

  const handleImportedGameAnalysis = useCallback(
    async (request: GameAnalysisImportRequest, hintedTarget: ExternalGameTarget | null = null) => {
      setImportStatus("submitting");
      setImportError(null);
      setImportSnapshot(null);
      setActiveJob(null);
      setAnalysis(null);
      try {
        const response = await startImportedGameAnalysis(request);
        const requestTarget =
          request.url === undefined || request.url === null
            ? null
            : extractGameImportTarget(request.url);
        const target = mergeExternalTargetHints(
          mergeExternalTargetHints(
            mergeExternalTargetHints(externalTargetFromSource(response.source), requestTarget),
            hintedTarget,
          ),
          routeExternalTarget,
        );
        const nextJob = activateImportedGameResponse(response, {
          boardOrientation: target?.boardOrientation ?? null,
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
          setTurnstileRequired(false);
        }
        setImportStatus("polling");

        navigateToImportedGamePath(
          nextJob.analysis_id,
          target,
          route.ply,
          route.kind === "home" ? "push" : "replace",
        );
      } catch (error) {
        setImportStatus("failed");
        setImportError(importErrorMessage(error));
        throw error;
      }
    },
    [navigateToImportedGamePath, route.kind, route.ply, routeExternalTarget],
  );

  useEffect(() => {
    const target = externalTargetFromRoute(route);
    if (target === null || route.analysisId !== null || activeJob !== null) {
      return;
    }
    const importTarget = target;
    const routeImportKey = externalTargetKey(importTarget);
    if (routeImportStartedRef.current === routeImportKey) {
      return;
    }

    routeImportStartedRef.current = routeImportKey;
    let cancelled = false;
    const abortController = new AbortController();

    async function startRouteImport() {
      setImportStatus("submitting");
      setImportError(null);
      setImportSnapshot(null);
      setAnalysis(null);
      try {
        const response = await getCachedImportedGameAnalysis(importTarget, abortController.signal);
        if (cancelled) {
          return;
        }
        const nextJob = activateImportedGameResponse(response, {
          boardOrientation: importTarget.boardOrientation,
          setActiveJob,
          writeStorage: true,
        });
        currentRouteJobIdRef.current = nextJob.analysis_id;
        const importedAnalysis = mapGameAnalysisImportResponse(response);
        if (importedAnalysis !== null) {
          setAnalysis(importedAnalysis);
        }
        setTurnstileToken(null);
        setTurnstileRequired(false);
        setImportStatus("polling");
        navigateToImportedGamePath(
          nextJob.analysis_id,
          mergeExternalTargetHints(externalTargetFromSource(nextJob.source), importTarget),
          route.ply,
          "replace",
        );
      } catch (error) {
        if (cancelled || isAbortError(error)) {
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setPendingRouteImportTarget(importTarget);
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
      if (routeImportStartedRef.current === routeImportKey) {
        routeImportStartedRef.current = null;
      }
    };
  }, [activeJob, navigateToImportedGamePath, route]);

  useEffect(() => {
    const target = externalTargetFromRoute(route);
    if (
      target === null ||
      route.analysisId === null ||
      activeJob === null ||
      activeJob.analysis_id !== route.analysisId ||
      hasPlayerIdentity(activeJob.source)
    ) {
      return;
    }
    const hydrateTarget = target;

    const analysisId = route.analysisId;
    let cancelled = false;
    const abortController = new AbortController();

    async function hydrateSharedRouteSource() {
      try {
        const response = await getCachedImportedGameAnalysis(hydrateTarget, abortController.signal);
        if (
          cancelled ||
          !externalTargetMatchesSource(hydrateTarget, response.source) ||
          !hasPlayerIdentity(response.source)
        ) {
          return;
        }
        setActiveJob((current) => {
          if (
            current === null ||
            current.analysis_id !== analysisId ||
            hasPlayerIdentity(current.source)
          ) {
            return current;
          }
          const nextJob: StoredGameAnalysisJob = {
            ...current,
            source: response.source,
            game: current.game ?? response.game ?? null,
            boardOrientation: current.boardOrientation ?? hydrateTarget.boardOrientation,
          };
          writeStoredGameAnalysisJob(nextJob);
          return nextJob;
        });
      } catch (error) {
        if (cancelled || isAbortError(error)) {
          return;
        }
      }
    }

    void hydrateSharedRouteSource();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, [activeJob, route]);

  useEffect(() => {
    if (pendingRouteImportTarget === null) {
      return;
    }
    const routeTarget = externalTargetFromRoute(route);
    if (
      routeTarget === null ||
      !externalTargetsEqual(routeTarget, pendingRouteImportTarget) ||
      route.analysisId !== null ||
      activeJob !== null
    ) {
      return;
    }
    const needsTurnstile = isTurnstileEnabled();
    if (needsTurnstile && turnstileToken === null) {
      if (!turnstileRequired) {
        setTurnstileRequired(true);
      }
      return;
    }

    const target = pendingRouteImportTarget;
    const token = turnstileToken;
    let cancelled = false;

    async function startPendingRouteImport() {
      try {
        await handleImportedGameAnalysis(buildRouteImportRequest(target, token));
        if (!cancelled) {
          setPendingRouteImportTarget(null);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (needsTurnstile) {
          resetTurnstile();
        }
        if (error instanceof ApiError && error.code === "turnstile_failed") {
          setTurnstileRequired(true);
        } else {
          setPendingRouteImportTarget(null);
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
    pendingRouteImportTarget,
    resetTurnstile,
    route,
    turnstileToken,
    turnstileRequired,
  ]);

  const handleOpenImport = useCallback(() => {
    clearStoredGameAnalysisJob();
    setActiveJob(null);
    setAnalysis(null);
    setImportSnapshot(null);
    setImportError(null);
    setImportStatus("idle");
    setPendingRouteImportTarget(null);
    setTurnstileRequired(false);
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
        turnstileRequired={turnstileRequired}
        turnstileResetKey={turnstileResetKey}
        turnstileToken={turnstileToken}
      />
    );
  }

  return (
    <AnalysisGameWorkspace
      activeBoardOrientation={activeBoardOrientation}
      analysis={analysis}
      initialBoardOrientation={route.boardOrientation}
      initialPly={route.ply}
      key={`${analysis.id}:${activeBoardOrientation ?? ""}`}
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
  turnstileRequired,
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
          turnstileRequired={turnstileRequired}
          turnstileResetKey={turnstileResetKey}
          turnstileToken={turnstileToken}
        />
      </main>
      <WorkspaceFooter />
    </div>
  );
}

function AnalysisGameWorkspace({
  activeBoardOrientation,
  analysis,
  initialBoardOrientation,
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
  const [engineLineCount, setEngineLineCount] = useState(2);
  const [showMaiaArrow, setShowMaiaArrow] = useState(false);
  const [markerDisplayMode, setMarkerDisplayMode] = useState<MarkerDisplayMode>("critical");
  const [mobileTab, setMobileTab] = useState<MobileTab>("analysis");
  const isDesktopLayout = useMediaQuery(DESKTOP_MEDIA_QUERY);

  const indexes = useMemo(() => buildAnalysisIndexes(analysis), [analysis]);
  const currentMove = indexes.moveByPly.get(currentPly) ?? null;
  const currentMarker = indexes.markerByPly.get(currentPly) ?? null;
  const currentTimelinePoint = indexes.timelineByPly.get(currentPly) ?? null;
  const nextMove = indexes.moveByPly.get(currentPly + 1) ?? null;
  const nextMarker = indexes.markerByPly.get(currentPly + 1) ?? null;
  const nextTimelinePoint = indexes.timelineByPly.get(currentPly + 1) ?? null;
  const currentFen = currentMove?.fen_after ?? analysis.moves[0]?.fen_before ?? "";
  const previousPlyRef = useRef(currentPly);
  const routePlyRef = useRef(initialPly);
  const lastWheelNavigationAtRef = useRef(0);

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
  const engineContinuationLine = useMemo<EngineContinuationLine | null>(() => {
    const nextMarkerLine = nextMarker?.best_lines[0];
    if (nextMove && nextMarkerLine) {
      return { fen: nextMove.fen_before, line: nextMarkerLine };
    }
    const nextTimelineLine = nextTimelinePoint?.best_lines[0];
    if (nextTimelineLine) {
      return { fen: nextTimelinePoint.fen_before, line: nextTimelineLine };
    }
    return null;
  }, [nextMarker, nextMove, nextTimelinePoint]);
  const bestMatchesContinuation =
    engineContinuationLine !== null &&
    serverEngineLines?.lines[0]?.san !== undefined &&
    currentTimelinePoint?.san === serverEngineLines.lines[0].san;
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
  const baseBoardOrientation =
    activeBoardOrientation ?? initialBoardOrientation ?? analysis.player_side;
  const boardOrientation = flippedBoard ? oppositeSide(baseBoardOrientation) : baseBoardOrientation;
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
      triggerHaptic("selection");
    },
    [board.clearDiscovery, board.clearPreview],
  );

  const stepPly = useCallback(
    (delta: number) => {
      if (board.stepInDiscovery(delta)) {
        triggerHaptic("selection");
        return;
      }
      board.clearPreview();
      setCurrentPly((ply) => Math.max(1, Math.min(analysis.moves.length, ply + delta)));
      triggerHaptic("selection");
    },
    [analysis.moves.length, board.clearPreview, board.stepInDiscovery],
  );

  const goToBoundary = useCallback(
    (direction: "start" | "end") => {
      board.clearPreview();
      board.clearDiscovery();
      setCurrentPly(direction === "start" ? 1 : analysis.moves.length);
      triggerHaptic("medium");
    },
    [analysis.moves.length, board.clearDiscovery, board.clearPreview],
  );

  const exitPreviewOrDiscovery = useCallback(() => {
    if (board.discovery) {
      board.exitDiscovery();
      triggerHaptic("nudge");
      return;
    }
    board.clearPreview();
    triggerHaptic("nudge");
  }, [board.clearPreview, board.discovery, board.exitDiscovery]);

  const handleBoardWheel = useCallback(
    (event: WheelEvent) => {
      if (
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        shouldIgnoreWheelMoveNavigationTarget(event.target)
      ) {
        return;
      }
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (Math.abs(event.deltaY) < WHEEL_MOVE_NAVIGATION_MIN_DELTA) {
        return;
      }

      const now = Date.now();
      if (now - lastWheelNavigationAtRef.current < WHEEL_MOVE_NAVIGATION_COOLDOWN_MS) {
        return;
      }

      lastWheelNavigationAtRef.current = now;
      const stepCount = Math.max(
        1,
        Math.min(4, Math.floor(Math.abs(event.deltaY) / WHEEL_MOVE_NAVIGATION_DELTA_PER_PLY)),
      );
      stepPly((event.deltaY > 0 ? 1 : -1) * stepCount);
    },
    [stepPly],
  );

  const handleFlipBoard = useCallback(() => {
    setFlippedBoard((value) => !value);
    triggerHaptic("medium");
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
        <main className="mx-auto max-w-[1320px] px-3 pt-3 pb-7 sm:px-6 min-[1100px]:pt-5 min-[1100px]:pb-7">
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
              engineContinuationLine={engineContinuationLine}
              engineLineCount={engineLineCount}
              fallbackEvalCp={fallbackEvalCp}
              flippedBoard={flippedBoard}
              discovery={board.discovery}
              dimmed={board.dimmed}
              handleDiscoveryStepClick={board.handleDiscoveryStepClick}
              handlePieceDrop={board.handlePieceDrop}
              highlightedMove={board.highlightedMove}
              materialAdvantage={material.advantage}
              onArrowCountChange={setArrowCount}
              onEngineLineCountChange={setEngineLineCount}
              onMarkerDisplayModeChange={setMarkerDisplayMode}
              onExitPreview={exitPreviewOrDiscovery}
              onFlipBoard={handleFlipBoard}
              onGoToBoundary={goToBoundary}
              onOpenImport={onOpenImport}
              onBookPreview={handleBookPreview}
              onBoardWheel={handleBoardWheel}
              onPreview={board.handlePreview}
              onSelectPly={handleSelectPly}
              onShowMaiaArrowChange={setShowMaiaArrow}
              onStepPly={stepPly}
              playerMeta={playerMeta}
              preview={board.preview}
              markerDisplayMode={markerDisplayMode}
              serverEngineLines={serverEngineLines}
              bestMatchesContinuation={bestMatchesContinuation}
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
              engineContinuationLine={engineContinuationLine}
              engineLineCount={engineLineCount}
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
              onEngineLineCountChange={setEngineLineCount}
              onMarkerDisplayModeChange={setMarkerDisplayMode}
              onExitPreview={exitPreviewOrDiscovery}
              onFlipBoard={handleFlipBoard}
              onGoToBoundary={goToBoundary}
              onOpenImport={onOpenImport}
              onBookPreview={handleBookPreview}
              onBoardWheel={handleBoardWheel}
              onPreview={board.handlePreview}
              onSelectPly={handleSelectPly}
              onSetMobileTab={setMobileTab}
              onShowMaiaArrowChange={setShowMaiaArrow}
              onStepPly={stepPly}
              playerMeta={playerMeta}
              preview={board.preview}
              markerDisplayMode={markerDisplayMode}
              serverEngineLines={serverEngineLines}
              bestMatchesContinuation={bestMatchesContinuation}
              showMaiaArrow={showMaiaArrow}
              topSide={topSide}
            />
          )}
        </main>
        <WorkspaceFooter hideOnMobile />
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

function shouldIgnoreWheelMoveNavigationTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false;
  }
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

function BackToImportButton({ className, onClick }: { className?: string; onClick: () => void }) {
  return (
    <button
      aria-label="Back to import"
      className={cn(
        "z-40 flex size-6 cursor-pointer items-center justify-center rounded-full text-stone-400 transition-colors hover:bg-stone-100/70 hover:text-stone-500 dark:text-stone-500 dark:hover:bg-stone-900/70 dark:hover:text-stone-400",
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
  engineContinuationLine,
  engineLineCount,
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
  onEngineLineCountChange,
  showMaiaArrow,
  onShowMaiaArrowChange,
  markerDisplayMode,
  onMarkerDisplayModeChange,
  flippedBoard,
  onFlipBoard,
  serverEngineLines,
  bestMatchesContinuation,
  discovery,
  preview,
  dimmed,
  onPreview,
  onBookPreview,
  onBoardWheel,
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
              engineLineCount={engineLineCount}
              fallbackEvalCp={fallbackEvalCp}
              flippedBoard={flippedBoard}
              preferBrowserEval={Boolean(discovery || preview)}
              onArrowCountChange={onArrowCountChange}
              onEngineLineCountChange={onEngineLineCountChange}
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
                onWheel={onBoardWheel}
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

      <div className="flex max-h-[87vh] min-w-0 flex-col pl-5">
        <aside className="shrink-0 space-y-4 pr-1">
          <PositionInfo
            boardOrientation={boardOrientation}
            currentMove={currentMove}
            emptyMessage={ANALYSIS_LOADING_EMPTY_MESSAGE}
            emptyMessageVariant="shimmer"
            currentPly={currentPly}
            moves={analysis.moves}
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
            continuationLine={engineContinuationLine}
            bestMatchesContinuation={bestMatchesContinuation}
            maxLines={engineLineCount}
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
  engineContinuationLine,
  highlightedMove,
  boardOrientation,
  boardTransitionMove,
  topSide,
  bottomSide,
  playerMeta,
  materialAdvantage,
  arrowCount,
  fallbackEvalCp,
  engineLineCount,
  serverEngineLines,
  bestMatchesContinuation,
  showMaiaArrow,
  flippedBoard,
  discovery,
  preview,
  dimmed,
  markerDisplayMode,
  onArrowCountChange,
  onEngineLineCountChange,
  onMarkerDisplayModeChange,
  onFlipBoard,
  onShowMaiaArrowChange,
  onPreview,
  onBookPreview,
  onBoardWheel,
  handleDiscoveryStepClick,
  handlePieceDrop,
  onSelectPly,
  onStepPly,
  onOpenImport,
  onExitPreview,
  mobileTab,
  onSetMobileTab,
}: MobileLayoutProps) {
  return (
    <div className="relative mx-auto max-w-[760px] space-y-2.5 pb-24">
      <div className="mx-auto w-full max-w-[min(720px,max(360px,calc(100dvh-22rem)))] space-y-2.5">
        <MobileBoardControls
          analysisFen={analysisFen}
          boardOrientation={boardOrientation}
          fallbackEvalCp={fallbackEvalCp}
          onOpenImport={onOpenImport}
          preferBrowserEval={Boolean(discovery || preview)}
        />
        <div className="space-y-2.5 border-stone-200  dark:border-stone-800">
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
            onWheel={onBoardWheel}
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
      </div>
      {mobileTab === "moves" ? (
        <MoveList
          className="block h-auto"
          currentPly={currentPly}
          markerDisplayMode={markerDisplayMode}
          moveMarkers={analysis.move_markers}
          moves={analysis.moves}
          onSelectPly={onSelectPly}
        />
      ) : (
        <div className="min-w-0 md:space-y-4 space-y-2">
          <PositionInfo
            boardOrientation={boardOrientation}
            currentMove={currentMove}
            emptyMessage={ANALYSIS_LOADING_EMPTY_MESSAGE}
            emptyMessageVariant="shimmer"
            currentPly={currentPly}
            moves={analysis.moves}
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
            continuationLine={engineContinuationLine}
            bestMatchesContinuation={bestMatchesContinuation}
            maxLines={engineLineCount}
          />
        </div>
      )}
      <MobileFloatingLeftControls
        arrowCount={arrowCount}
        engineLineCount={engineLineCount}
        flippedBoard={flippedBoard}
        markerDisplayMode={markerDisplayMode}
        mobileTab={mobileTab}
        onArrowCountChange={onArrowCountChange}
        onEngineLineCountChange={onEngineLineCountChange}
        onFlipBoard={onFlipBoard}
        onMarkerDisplayModeChange={onMarkerDisplayModeChange}
        onSetMobileTab={onSetMobileTab}
        onShowMaiaArrowChange={onShowMaiaArrowChange}
        showMaiaArrow={showMaiaArrow}
      />
      <MobileFloatingNav
        canGoBack={currentPly > 1 || Boolean(discovery)}
        canGoForward={currentPly < analysis.moves.length || Boolean(discovery)}
        exitLabel={discovery ? "Exit analysis" : "Exit preview"}
        onExitPreview={onExitPreview}
        onStepBack={() => onStepPly(-1)}
        onStepForward={() => onStepPly(1)}
        showExitPreview={Boolean(preview || discovery)}
      />
    </div>
  );
}

function MobileBoardControls({
  analysisFen,
  boardOrientation,
  fallbackEvalCp,
  preferBrowserEval,
  onOpenImport,
}: {
  analysisFen: string;
  boardOrientation: BoardSide;
  fallbackEvalCp: number | null;
  preferBrowserEval: boolean;
  onOpenImport: () => void;
}) {
  const evalCp = useDisplayEvalCp(analysisFen, fallbackEvalCp, preferBrowserEval);

  return (
    <div className="flex items-center gap-1.5">
      <BackToImportButton className="size-7 shrink-0 rounded-md" onClick={onOpenImport} />
      <HorizontalEvalBar className="h-4 flex-1" evalCp={evalCp} orientation={boardOrientation} />
    </div>
  );
}

function MobileFloatingLeftControls({
  arrowCount,
  engineLineCount,
  flippedBoard,
  markerDisplayMode,
  mobileTab,
  onArrowCountChange,
  onEngineLineCountChange,
  onFlipBoard,
  onMarkerDisplayModeChange,
  onSetMobileTab,
  onShowMaiaArrowChange,
  showMaiaArrow,
}: {
  arrowCount: number;
  engineLineCount: number;
  flippedBoard: boolean;
  markerDisplayMode: MarkerDisplayMode;
  mobileTab: MobileTab;
  onArrowCountChange: (value: number) => void;
  onEngineLineCountChange: (value: number) => void;
  onFlipBoard: () => void;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  onSetMobileTab: (tab: MobileTab) => void;
  onShowMaiaArrowChange: (value: boolean) => void;
  showMaiaArrow: boolean;
}) {
  return (
    <div className="pointer-events-auto fixed bottom-[1px] left-3 z-30 flex items-center gap-2">
      <AnalysisSettingsPopover
        arrowCount={arrowCount}
        buttonClassName={MOBILE_FLOATING_BUTTON_CLASS}
        engineLineCount={engineLineCount}
        flippedBoard={flippedBoard}
        iconClassName="size-5"
        markerDisplayMode={markerDisplayMode}
        onArrowCountChange={onArrowCountChange}
        onEngineLineCountChange={onEngineLineCountChange}
        onFlipBoard={onFlipBoard}
        onMarkerDisplayModeChange={onMarkerDisplayModeChange}
        onShowMaiaArrowChange={onShowMaiaArrowChange}
        placement="top-start"
        showMaiaArrow={showMaiaArrow}
      />
      <MobileTabToggleButton activeTab={mobileTab} onChange={onSetMobileTab} />
    </div>
  );
}

function MobileTabToggleButton({
  activeTab,
  onChange,
}: {
  activeTab: MobileTab;
  onChange: (tab: MobileTab) => void;
}) {
  const showingMoves = activeTab === "moves";
  const Icon = showingMoves ? FileText : ListOrdered;
  const label = showingMoves ? "Show analysis" : "Show moves";
  const nextTab: MobileTab = showingMoves ? "analysis" : "moves";

  return (
    <button
      aria-label={label}
      aria-pressed={!showingMoves}
      className={cn(
        "flex cursor-pointer items-center justify-center transition-[background-color,color,transform] active:scale-[0.96]",
        MOBILE_FLOATING_BUTTON_CLASS,
      )}
      onClick={() => {
        triggerHaptic("medium");
        onChange(nextTab);
      }}
      title={label}
      type="button"
    >
      <Icon className="size-5" />
    </button>
  );
}

function MobileFloatingNav({
  canGoBack,
  canGoForward,
  exitLabel,
  onExitPreview,
  onStepBack,
  onStepForward,
  showExitPreview,
}: {
  canGoBack: boolean;
  canGoForward: boolean;
  exitLabel: string;
  onExitPreview: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  showExitPreview: boolean;
}) {
  return (
    <div className="pointer-events-auto fixed right-3 bottom-3 z-30 flex items-center gap-1 rounded-full border border-stone-200 bg-white/85 p-1 shadow-lg shadow-stone-950/10 backdrop-blur-md dark:border-stone-800 dark:bg-stone-900/85 dark:shadow-black/30">
      <MobileFloatingNavButton disabled={!canGoBack} label="Previous move" onClick={onStepBack}>
        <ChevronLeft className="size-5" />
      </MobileFloatingNavButton>
      {showExitPreview ? (
        <MobileFloatingNavButton label={exitLabel} onClick={onExitPreview}>
          <CornerUpLeft className="size-5" />
        </MobileFloatingNavButton>
      ) : null}
      <MobileFloatingNavButton disabled={!canGoForward} label="Next move" onClick={onStepForward}>
        <ChevronRight className="size-5" />
      </MobileFloatingNavButton>
    </div>
  );
}

function MobileFloatingNavButton({
  children,
  disabled = false,
  label,
  onClick,
}: {
  children: ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      className="flex size-10 cursor-pointer items-center justify-center rounded-full text-stone-700 transition-[background-color,color,transform] hover:bg-stone-100 hover:text-stone-950 active:scale-[0.96] disabled:pointer-events-none disabled:text-stone-300 dark:text-stone-300 dark:hover:bg-stone-800 dark:hover:text-stone-50 dark:disabled:text-stone-700"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

const MOBILE_FLOATING_BUTTON_CLASS =
  "size-12 rounded-full border border-stone-200 bg-white/85 text-stone-700 shadow-lg shadow-stone-950/10 backdrop-blur-md hover:bg-stone-100 hover:text-stone-950 dark:border-stone-800 dark:bg-stone-900/85 dark:text-stone-300 dark:shadow-black/30 dark:hover:bg-stone-800 dark:hover:text-stone-50";

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
  engineLineCount: number;
  onEngineLineCountChange: (value: number) => void;
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
  onWheel: (event: WheelEvent) => void;
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
  bestMatchesContinuation,
  continuationLine,
  discoveryActive,
  displayFen,
  maxLines,
  onBookPreview,
  onPreview,
  previewActive,
  serverEngineLines,
}: {
  activePreview: PreviewState | null;
  analysisFen: string;
  analysisPlayerSide: BoardSide;
  bookLineSet: BookLineSet | null;
  bestMatchesContinuation: boolean;
  continuationLine: EngineContinuationLine | null;
  discoveryActive: boolean;
  displayFen: string;
  maxLines: number;
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

  const playerSideForLines =
    discoveryActive || previewActive
      ? sideToMoveFromFen(engineLines?.fen || displayFen)
      : analysisPlayerSide;

  return (
    <EngineLinesView
      activePreview={activePreview}
      lines={engineLines?.lines ?? EMPTY_BEST_LINES}
      bestMatchesContinuation={bestMatchesContinuation}
      continuationLine={continuationLine}
      onPreview={onPreview}
      maxLines={maxLines}
      playerSide={playerSideForLines}
      rootFen={engineLines?.fen ?? analysisFen}
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
  engineContinuationLine: EngineContinuationLine | null;
  highlightedMove: string | null;
  boardOrientation: BoardSide;
  boardTransitionMove: BoardTransitionMove | null;
  topSide: BoardSide;
  bottomSide: BoardSide;
  playerMeta: PlayerMeta;
  materialAdvantage: number;
  fallbackEvalCp: number | null;
  engineLineCount: number;
  arrowCount: number;
  onArrowCountChange: (value: number) => void;
  onEngineLineCountChange: (value: number) => void;
  showMaiaArrow: boolean;
  onShowMaiaArrowChange: (value: boolean) => void;
  markerDisplayMode: MarkerDisplayMode;
  onMarkerDisplayModeChange: (value: MarkerDisplayMode) => void;
  flippedBoard: boolean;
  onFlipBoard: () => void;
  serverEngineLines: EngineLineSet | null;
  bestMatchesContinuation: boolean;
  discovery: DiscoveryState | null;
  preview: PreviewState | null;
  dimmed: boolean;
  onPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  onBookPreview: (rootFen: string, lineMoves: string[], step: number) => void;
  onBoardWheel: (event: WheelEvent) => void;
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
      boardOrientation:
        route.boardOrientation ??
        (storedJob?.analysis_id === route.analysisId ? storedJob.boardOrientation : null),
    };
  }

  const target = externalTargetFromRoute(route);
  if (target !== null) {
    if (!externalTargetMatchesSource(target, storedJob?.source ?? null) || storedJob === null) {
      return null;
    }
    return {
      ...storedJob,
      boardOrientation: target.boardOrientation ?? storedJob.boardOrientation,
    };
  }

  return null;
}

function sourceForRoute(
  route: AnalysisRouteState,
  storedJob: StoredGameAnalysisJob | null,
): ImportedGameMetadata | null {
  const target = externalTargetFromRoute(route);
  if (target === null) {
    return storedJob?.analysis_id === route.analysisId ? storedJob.source : null;
  }
  if (storedJob !== null && externalTargetMatchesSource(target, storedJob.source)) {
    return storedJob.source;
  }
  return sourceFromExternalTarget(target);
}

function sourceFromExternalTarget(target: ExternalGameTarget): ImportedGameMetadata {
  const isLichess = target.source === "lichess_game_url";
  return {
    source: target.source,
    source_url: sourceUrlForTarget(target),
    external_game_id: target.externalGameId,
    title: `${isLichess ? "Lichess" : "Chess.com"} game ${target.externalGameId}`,
    white_username: null,
    black_username: null,
    white_rating: null,
    black_rating: null,
    time_control: null,
    result: null,
    allows_global_training: false,
    rights_basis: `Public ${isLichess ? "Lichess" : "Chess.com"} game link.`,
  };
}

function hasPlayerIdentity(source: ImportedGameMetadata | null): boolean {
  return (
    source !== null &&
    source.white_username !== null &&
    source.black_username !== null &&
    source.white_rating !== null &&
    source.black_rating !== null
  );
}

function buildRouteImportRequest(
  target: ExternalGameTarget,
  turnstileToken: string | null,
): GameAnalysisImportRequest {
  const request: GameAnalysisImportRequest = {
    source: target.source,
    url: sourceUrlForTarget(target),
    explain_significance: ["critical"],
    include_context: false,
    use_baseline_fallback: false,
  };
  if (turnstileToken !== null) {
    request.turnstile_token = turnstileToken;
  }
  return request;
}

function sourceUrlForTarget(target: ExternalGameTarget): string {
  return target.source === "lichess_game_url"
    ? lichessGameUrl(target.externalGameId)
    : chessComLiveGameUrl(target.externalGameId);
}

async function getCachedImportedGameAnalysis(target: ExternalGameTarget, signal: AbortSignal) {
  return target.source === "lichess_game_url"
    ? getCachedLichessGameAnalysis(target.externalGameId, signal)
    : getCachedChessComLiveGameAnalysis(target.externalGameId, signal);
}

function activateImportedGameResponse(
  response: {
    analysis_id: string;
    status_url: string;
    source: ImportedGameMetadata;
    game?: GameAnalysisGame | null;
  },
  {
    boardOrientation,
    setActiveJob,
    writeStorage,
  }: {
    boardOrientation?: ExternalGameOrientation | null;
    setActiveJob: (job: StoredGameAnalysisJob) => void;
    writeStorage: boolean;
  },
): StoredGameAnalysisJob {
  const nextJob: StoredGameAnalysisJob = {
    analysis_id: response.analysis_id,
    status_url: response.status_url,
    source: response.source,
    game: response.game ?? null,
    boardOrientation: boardOrientation ?? null,
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
    current.source?.source === next.source?.source &&
    current.source?.external_game_id === next.source?.external_game_id &&
    current.boardOrientation === next.boardOrientation &&
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
  const target = mergeExternalTargetHints(
    externalTargetFromJob(job),
    externalTargetFromRoute(route),
  );
  return {
    analysisId: job.analysis_id,
    externalSource: target?.source ?? null,
    externalGameId: target?.externalGameId ?? null,
    boardOrientation: target?.boardOrientation ?? null,
  };
}

function isExternalGameRoute(route: AnalysisRouteState): boolean {
  return externalTargetFromRoute(route) !== null;
}

function externalTargetFromRoute(route: AnalysisRouteState): ExternalGameTarget | null {
  if (route.externalSource === null || route.externalGameId === null) {
    return null;
  }
  return {
    source: route.externalSource,
    externalGameId: route.externalGameId,
    boardOrientation: route.boardOrientation,
  };
}

function externalTargetFromSource(source: ImportedGameMetadata | null): ExternalGameTarget | null {
  if (source === null || source.external_game_id === null || !isExternalGameSource(source.source)) {
    return null;
  }
  return {
    source: source.source,
    externalGameId: source.external_game_id,
    boardOrientation: null,
  };
}

function externalTargetFromJob(job: StoredGameAnalysisJob | null): ExternalGameTarget | null {
  const target = externalTargetFromSource(job?.source ?? null);
  if (target === null || job === null) {
    return target;
  }
  return {
    ...target,
    boardOrientation: job.boardOrientation,
  };
}

function externalTargetMatchesSource(
  target: ExternalGameTarget,
  source: ImportedGameMetadata | null,
): boolean {
  return (
    source !== null &&
    source.source === target.source &&
    source.external_game_id === target.externalGameId
  );
}

function externalTargetsEqual(left: ExternalGameTarget, right: ExternalGameTarget): boolean {
  return (
    left.source === right.source &&
    left.externalGameId === right.externalGameId &&
    left.boardOrientation === right.boardOrientation
  );
}

function externalTargetKey(target: ExternalGameTarget): string {
  return `${target.source}:${target.externalGameId}:${target.boardOrientation ?? ""}`;
}

function mergeExternalTargetHints(
  sourceTarget: ExternalGameTarget | null,
  hintedTarget: ExternalGameTarget | null,
): ExternalGameTarget | null {
  if (sourceTarget === null) {
    return hintedTarget;
  }
  if (
    hintedTarget === null ||
    sourceTarget.source !== hintedTarget.source ||
    sourceTarget.externalGameId !== hintedTarget.externalGameId
  ) {
    return sourceTarget;
  }
  return {
    ...sourceTarget,
    boardOrientation: hintedTarget.boardOrientation ?? sourceTarget.boardOrientation,
  };
}

function isExternalGameSource(
  source: ImportedGameMetadata["source"],
): source is ExternalGameSource {
  return source === "chess_com_live_url" || source === "lichess_game_url";
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
      boardOrientation:
        parsed.boardOrientation === "white" || parsed.boardOrientation === "black"
          ? parsed.boardOrientation
          : null,
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
  if (game?.moves.length || snapshot.moves.length > 0) {
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
