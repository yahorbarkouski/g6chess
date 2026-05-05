import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/api";
import type {
  EngineLine,
  GameAnalysisGame,
  GameAnalysisSnapshot,
  GameMoveAnalysis,
  ImportedGameMetadata,
} from "../../types/api";
import { AnalysisWorkspace } from "./AnalysisWorkspace";

const apiMocks = vi.hoisted(() => ({
  getCachedChessComLiveGameAnalysis: vi.fn(),
  startImportedGameAnalysis: vi.fn(),
  pollGameAnalysis: vi.fn(),
}));

const stockfishMocks = vi.hoisted(() => ({
  analyze: vi.fn(),
  preAnalyze: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    getCachedChessComLiveGameAnalysis: apiMocks.getCachedChessComLiveGameAnalysis,
    startImportedGameAnalysis: apiMocks.startImportedGameAnalysis,
    pollGameAnalysis: apiMocks.pollGameAnalysis,
  };
});

vi.mock("../../hooks/useStockfish", () => ({
  useStockfish: () => ({
    fen: null,
    lines: [],
    evalCp: null,
    depth: 0,
    isAnalyzing: false,
    analyze: stockfishMocks.analyze,
    preAnalyze: stockfishMocks.preAnalyze,
  }),
}));

vi.mock("../../lib/use-chesscom-move-sound", () => ({
  useChessComMoveSound: vi.fn(),
}));

vi.mock("./UltraAnalysisBoard", () => ({
  UltraAnalysisBoard: ({ fen }: { fen: string | null }) => (
    <div data-testid="analysis-board">{fen}</div>
  ),
}));

vi.mock("../ui/morph-text", () => ({
  MorphText: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

describe("AnalysisWorkspace imports", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    window.localStorage.clear();
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(min-width: 1100px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    Element.prototype.scrollIntoView = vi.fn();
    Element.prototype.getAnimations = vi.fn().mockReturnValue([]);
    Element.prototype.animate = vi.fn().mockReturnValue({ cancel: vi.fn() });
    delete window.turnstile;
    delete window.__g6TurnstileScriptLoading;
    apiMocks.getCachedChessComLiveGameAnalysis.mockReset();
    apiMocks.getCachedChessComLiveGameAnalysis.mockRejectedValue(
      new ApiError(404, "Cached game analysis not found."),
    );
    apiMocks.startImportedGameAnalysis.mockReset();
    apiMocks.pollGameAnalysis.mockReset();
    stockfishMocks.analyze.mockReset();
    stockfishMocks.preAnalyze.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllEnvs();
    delete window.turnstile;
    delete window.__g6TurnstileScriptLoading;
  });

  it("starts URL import, polls, maps the completed snapshot, and renders the real move", async () => {
    const user = userEvent.setup();
    const source = importedSource();
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    expect(screen.queryByTestId("analysis-board")).toBeNull();

    await user.type(
      screen.getByLabelText("Chess.com URL"),
      "https://www.chess.com/game/168193636078",
    );
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() =>
      expect(apiMocks.startImportedGameAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({
          source: "chess_com_live_url",
          url: "https://www.chess.com/game/live/168193636078",
          include_context: true,
        }),
      ),
    );
    await waitFor(() =>
      expect(apiMocks.pollGameAnalysis).toHaveBeenCalledWith(
        "/api/game-analysis/analysis-1",
        expect.any(AbortSignal),
      ),
    );

    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(screen.getByText("Alpha")).toBeTruthy();
    expect(screen.queryByLabelText("Chess.com URL")).toBeNull();
    expect(screen.getAllByTestId("analysis-board")).toHaveLength(1);
    expect(window.localStorage.getItem("g6explanation.currentGameAnalysis")).toContain(
      "analysis-1",
    );
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");
    await waitForNoBrowserEngineTick();
    expect(stockfishMocks.analyze).not.toHaveBeenCalled();
    expect(stockfishMocks.preAnalyze).not.toHaveBeenCalled();
  });

  it("renders the imported game board before the first analysis snapshot resolves", async () => {
    const user = userEvent.setup();
    const source = importedSource();
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
      game: gameSkeleton(2),
    });
    apiMocks.pollGameAnalysis.mockReturnValue(new Promise(() => {}));

    render(<AnalysisWorkspace />);

    await user.type(
      screen.getByLabelText("Chess.com URL"),
      "https://www.chess.com/game/168193636078",
    );
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(screen.queryByLabelText("Chess.com URL")).toBeNull();
    expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 1");
    await waitFor(() =>
      expect(apiMocks.pollGameAnalysis).toHaveBeenCalledWith(
        "/api/game-analysis/analysis-1",
        expect.any(AbortSignal),
      ),
    );
    await waitForNoBrowserEngineTick();
    expect(stockfishMocks.analyze).toHaveBeenCalledWith(mainlineMove(1).fen_after);
    expect(stockfishMocks.preAnalyze).not.toHaveBeenCalled();
  });

  it("does not restore a previous analysis from the homepage", async () => {
    window.localStorage.setItem(
      "g6explanation.currentGameAnalysis",
      JSON.stringify({
        analysis_id: "analysis-1",
        status_url: "/api/game-analysis/analysis-1",
        source: importedSource(),
      }),
    );

    render(<AnalysisWorkspace />);

    expect(screen.getByLabelText("Chess.com URL")).toBeTruthy();
    expect(screen.queryByTestId("analysis-board")).toBeNull();
    expect(apiMocks.pollGameAnalysis).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/");
    expect(window.location.search).toBe("");
  });

  it("starts a Chess.com route import from a production-domain game path", async () => {
    window.history.replaceState(null, "", "/game/live/168193636078");
    const source = importedSource();
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    expect(screen.getByLabelText("Chess.com URL")).toHaveValue(
      "https://www.chess.com/game/live/168193636078",
    );
    await waitFor(() =>
      expect(apiMocks.getCachedChessComLiveGameAnalysis).toHaveBeenCalledWith(
        "168193636078",
        expect.any(AbortSignal),
      ),
    );
    await waitFor(() =>
      expect(apiMocks.startImportedGameAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({
          source: "chess_com_live_url",
          url: "https://www.chess.com/game/live/168193636078",
        }),
      ),
    );
    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");
  });

  it("waits for Turnstile before starting an uncached Chess.com route import", async () => {
    vi.stubEnv("VITE_G6_TURNSTILE_SITE_KEY", "site-key");
    window.history.replaceState(null, "", "/game/live/168193636078");
    const source = importedSource();
    let verifyTurnstile: ((token: string) => void) | undefined;
    window.turnstile = {
      render: vi.fn((container, options) => {
        container.dataset.testid = "turnstile-widget";
        container.textContent = "Turnstile challenge";
        verifyTurnstile = options.callback;
        return "widget-id";
      }),
      remove: vi.fn(),
    };
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    await waitFor(() =>
      expect(apiMocks.getCachedChessComLiveGameAnalysis).toHaveBeenCalledWith(
        "168193636078",
        expect.any(AbortSignal),
      ),
    );
    expect(await screen.findByTestId("turnstile-widget")).toBeTruthy();
    expect(apiMocks.startImportedGameAnalysis).not.toHaveBeenCalled();

    act(() => {
      verifyTurnstile?.("route-turnstile-token");
    });

    await waitFor(() =>
      expect(apiMocks.startImportedGameAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({
          source: "chess_com_live_url",
          url: "https://www.chess.com/game/live/168193636078",
          turnstile_token: "route-turnstile-token",
        }),
      ),
    );
    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");
  });

  it("reuses a cached Chess.com route analysis without starting a new import", async () => {
    window.history.replaceState(null, "", "/game/live/168193636078");
    const source = importedSource();
    apiMocks.getCachedChessComLiveGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "succeeded",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    expect(screen.getByLabelText("Chess.com URL")).toHaveValue(
      "https://www.chess.com/game/live/168193636078",
    );
    await waitFor(() =>
      expect(apiMocks.getCachedChessComLiveGameAnalysis).toHaveBeenCalledWith(
        "168193636078",
        expect.any(AbortSignal),
      ),
    );
    expect(apiMocks.startImportedGameAnalysis).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(apiMocks.pollGameAnalysis).toHaveBeenCalledWith(
        "/api/game-analysis/analysis-1",
        expect.any(AbortSignal),
      ),
    );
    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");
  });

  it("polls a shared Chess.com analysis link without starting a new import", async () => {
    window.history.replaceState(null, "", "/game/live/168193636078?analysis=analysis-1&ply=1");
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    await waitFor(() =>
      expect(apiMocks.pollGameAnalysis).toHaveBeenCalledWith(
        "/api/game-analysis/analysis-1",
        expect.any(AbortSignal),
      ),
    );
    expect(apiMocks.startImportedGameAnalysis).not.toHaveBeenCalled();
    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");
  });

  it("polls a direct analysis link without starting a new import", async () => {
    window.history.replaceState(null, "", "/analysis/analysis-1?ply=1");
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    await waitFor(() =>
      expect(apiMocks.pollGameAnalysis).toHaveBeenCalledWith(
        "/api/game-analysis/analysis-1",
        expect.any(AbortSignal),
      ),
    );
    expect(apiMocks.startImportedGameAnalysis).not.toHaveBeenCalled();
    expect(await screen.findByText("1. a4")).toBeTruthy();
    expect(window.location.pathname).toBe("/analysis/analysis-1");
    expect(window.location.search).toBe("");
  });

  it("restores and updates the selected ply in the share URL", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/game/live/168193636078?analysis=analysis-1&ply=2");
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMoves(2));

    render(<AnalysisWorkspace />);

    await waitFor(() => expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 2"));
    expect(window.location.search).toBe("?analysis=analysis-1&ply=2");

    await user.click(screen.getByRole("button", { name: "Previous move" }));

    await waitFor(() => expect(window.location.search).toBe("?analysis=analysis-1"));
  });

  it("does not chase a shared ply while a partial analysis grows", async () => {
    vi.useFakeTimers();
    window.history.replaceState(null, "", "/game/live/168193636078?analysis=analysis-1&ply=2");
    apiMocks.pollGameAnalysis
      .mockResolvedValueOnce(snapshotWithMoves(1, { status: "running", totalPlies: 2 }))
      .mockResolvedValueOnce(snapshotWithMoves(2));

    render(<AnalysisWorkspace />);

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 1");
    expect(window.location.search).toBe("?analysis=analysis-1");

    await act(async () => {
      vi.advanceTimersByTime(1200);
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.pollGameAnalysis).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 1");
    expect(window.location.search).toBe("?analysis=analysis-1");
  });

  it("returns from an imported game to the centered import flow", async () => {
    const user = userEvent.setup();
    const source = importedSource();
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    await user.type(
      screen.getByLabelText("Chess.com URL"),
      "https://www.chess.com/game/168193636078",
    );
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByTestId("analysis-board")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Back to import" }));

    expect(screen.queryByTestId("analysis-board")).toBeNull();
    expect(screen.getByLabelText("Chess.com URL")).toBeTruthy();
    expect(window.localStorage.getItem("g6explanation.currentGameAnalysis")).toBeNull();
    expect(window.location.pathname).toBe("/");
    expect(window.location.search).toBe("");
  });

  it("keeps the previous analysis reachable after returning to import", async () => {
    const user = userEvent.setup();
    const source = importedSource();
    apiMocks.startImportedGameAnalysis.mockResolvedValue({
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source,
    });
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMove());

    render(<AnalysisWorkspace />);

    await user.type(
      screen.getByLabelText("Chess.com URL"),
      "https://www.chess.com/game/168193636078",
    );
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByTestId("analysis-board")).toBeTruthy();
    expect(window.location.pathname).toBe("/game/live/168193636078");
    expect(window.location.search).toBe("?analysis=analysis-1");

    await user.click(screen.getByRole("button", { name: "Back to import" }));
    expect(screen.queryByTestId("analysis-board")).toBeNull();
    expect(window.location.pathname).toBe("/");

    await act(async () => {
      window.history.back();
      await Promise.resolve();
    });

    await waitFor(() => expect(window.location.pathname).toBe("/game/live/168193636078"));
    expect(window.location.search).toBe("?analysis=analysis-1");
    expect(await screen.findByTestId("analysis-board")).toBeTruthy();
  });

  it("applies browser history ply changes to the current board", async () => {
    window.history.replaceState(null, "", "/game/live/168193636078?analysis=analysis-1");
    window.history.pushState(null, "", "/game/live/168193636078?analysis=analysis-1&ply=2");
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithMoves(2));

    render(<AnalysisWorkspace />);

    await waitFor(() => expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 2"));

    await act(async () => {
      window.history.back();
      await Promise.resolve();
    });

    await waitFor(() => expect(window.location.search).toBe("?analysis=analysis-1"));
    await waitFor(() => expect(screen.getByTestId("analysis-board")).toHaveTextContent("0 1"));
  });

  it("renders backend opening book lines instead of engine lines for book moves", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/game/live/168193636078?analysis=analysis-1&ply=1");
    apiMocks.pollGameAnalysis.mockResolvedValue(snapshotWithBookMove());

    render(<AnalysisWorkspace />);

    expect((await screen.findAllByText("King's Pawn Game")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /1\. a4 Book/i })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Preview e5 Nf3" }));

    expect(screen.getByRole("button", { name: "Preview e5 Nf3" })).toBeTruthy();
    expect(screen.queryByText("Engine lines")).toBeNull();
    await waitForNoBrowserEngineTick();
    expect(stockfishMocks.analyze).not.toHaveBeenCalled();
    expect(stockfishMocks.preAnalyze).not.toHaveBeenCalled();
  });
});

async function waitForNoBrowserEngineTick(): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, 120));
}

function importedSource(): ImportedGameMetadata {
  return {
    source: "chess_com_live_url",
    source_url: "https://www.chess.com/game/live/168193636078",
    external_game_id: "168193636078",
    title: "Alpha vs Beta",
    white_username: "Alpha",
    black_username: "Beta",
    white_rating: 1600,
    black_rating: 1500,
    time_control: "180+2",
    result: "1-0",
    allows_global_training: false,
    rights_basis: "User-requested analysis input only.",
  };
}

function snapshotWithMove(): GameAnalysisSnapshot {
  return snapshotWithMoves(1);
}

function gameSkeleton(count: 1 | 2 = 1): GameAnalysisGame {
  const moves = count === 1 ? [mainlineMove(1)] : [mainlineMove(1), mainlineMove(2)];
  return {
    total_plies: count,
    moves,
  };
}

function mainlineMove(ply: 1 | 2): GameAnalysisGame["moves"][number] {
  const isBlackMove = ply === 2;
  return {
    ply,
    move_number: 1,
    player_color: isBlackMove ? "black" : "white",
    san: isBlackMove ? "a5" : "a4",
    uci: isBlackMove ? "a7a5" : "a2a4",
    fen_before: isBlackMove
      ? "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1"
      : "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1",
    fen_after: isBlackMove
      ? "rn1qkbnr/1ppbpppp/8/p2p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq a6 0 2"
      : "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1",
  };
}

function snapshotWithBookMove(): GameAnalysisSnapshot {
  return {
    ...snapshotWithMoves(1),
    moves: [
      moveAnalysis({
        openingBook: {
          is_book_move: true,
          is_novelty: false,
          book_lines: [
            {
              moves: [
                { san: "e5", uci: "e7e5" },
                { san: "Nf3", uci: "g1f3" },
              ],
              weight: 4,
              opening_name: "King's Pawn Game: Open Game",
              eco: "C20",
            },
          ],
          opening_name: "King's Pawn Game",
          eco: "C20",
        },
        engineTopLines: [],
        requiresExplanation: false,
        significance: { label: "low", score: 0 },
      }),
    ],
  };
}

function snapshotWithMoves(
  count: 1 | 2,
  {
    status = "succeeded",
    totalPlies = count,
  }: { status?: GameAnalysisSnapshot["status"]; totalPlies?: number } = {},
): GameAnalysisSnapshot {
  return {
    snapshot_version: "game_analysis_snapshot.v1",
    analysis_id: "analysis-1",
    status,
    total_plies: totalPlies,
    context_completed: count,
    explanation_required: count,
    explanation_completed: count,
    explanation_failed: 0,
    explain_significance: ["critical"],
    created_at: "2026-05-04T10:00:00Z",
    updated_at: "2026-05-04T10:00:01Z",
    started_at: "2026-05-04T10:00:00Z",
    completed_at: status === "succeeded" || status === "failed" ? "2026-05-04T10:00:01Z" : null,
    error: status === "failed" ? "Analysis failed." : null,
    moves: count === 1 ? [moveAnalysis()] : [moveAnalysis(), moveAnalysis({ ply: 2 })],
  };
}

function moveAnalysis({
  engineTopLines: providedEngineTopLines = null,
  openingBook = null,
  ply = 1,
  requiresExplanation = true,
  significance = { label: "critical", score: 1 },
}: {
  engineTopLines?: EngineLine[] | null;
  openingBook?: NonNullable<GameMoveAnalysis["opening_book"]> | null;
  ply?: 1 | 2;
  requiresExplanation?: boolean;
  significance?: GameMoveAnalysis["significance"];
} = {}): GameMoveAnalysis {
  const isBlackMove = ply === 2;
  const san = isBlackMove ? "a5" : "a4";
  const uci = isBlackMove ? "a7a5" : "a2a4";
  const fenBefore = isBlackMove
    ? "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1"
    : "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1";
  const fenAfter = isBlackMove
    ? "rn1qkbnr/1ppbpppp/8/p2p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq a6 0 2"
    : "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1";
  const engineTopLines = providedEngineTopLines ?? [engineLine(uci, san)];
  return {
    ply,
    san,
    uci,
    player_color: isBlackMove ? "black" : "white",
    state: "explained",
    requires_explanation: requiresExplanation,
    quality: "excellent",
    significance,
    beauty: { label: "ordinary", score: 0 },
    context_latency_seconds: 0.01,
    opening_book: openingBook,
    explanation: "a4 gains space without weakening the center.",
    explanation_latency_seconds: 0.02,
    explanation_attempts: 1,
    explanation_model: "test-model",
    explanation_error: null,
    context: {
      evidence: {
        context_version: "context.v1",
        request: {
          player_color: isBlackMove ? "black" : "white",
          player_level: { kind: "rating", value: 1500, system: "test" },
          played_move: uci,
          fen_before: fenBefore,
          pgn: null,
          ply,
          time_control: "rapid",
          clock_before_seconds: null,
          increment_seconds: null,
          opponent_level: null,
        },
        position: {
          fen_before: fenBefore,
          fen_after: fenAfter,
          side_to_move: isBlackMove ? "black" : "white",
          move_number: 1,
          ply,
          phase: "opening",
          legal_moves_uci: [uci],
        },
        played: {
          uci,
          san,
          legal: true,
          is_check: false,
          is_capture: false,
          promotion: null,
        },
        engine: {
          engine_version: "test-stockfish",
          analysis_budget: { kind: "static", value: 1, multipv: 1 },
          engine_options: {},
          top_lines: engineTopLines,
          played_line: engineLine(uci, san),
          after_line: null,
        },
        quality: {
          label: "excellent",
          score_delta_cp_player_pov: null,
          score_loss_vs_best_cp: 0,
          wdl_delta_player_pov: null,
          wdl_expected_score_loss: null,
          severity_text: "excellent",
        },
        significance,
        beauty: { label: "ordinary", score: 0 },
        candidates: [],
        main_point: {
          concept: "space",
          claim: "a4 gains useful queenside space.",
        },
        allowed_claims: ["space"],
      },
      llm_context: {
        played: san,
        quality: "excellent",
        significance,
        beauty: { label: "ordinary", score: 0 },
        player_level: "1500",
        time_situation: "normal",
        severity: "excellent",
        main_point: "a4 gains useful queenside space.",
        best_or_key_move: null,
        human_note: null,
        allowed_claims: ["space"],
      },
      verification: {
        verifier_version: "verifier.v1",
        passed: true,
        failures: [],
        warnings: [],
      },
    },
  };
}

function engineLine(uci = "a2a4", san = "a4"): EngineLine {
  return {
    move_uci: uci,
    move_san: san,
    score: { kind: "cp", value: 35, mate_in: null, mate_for: null },
    rank: 1,
    wdl: null,
    pv_uci: [uci],
    pv_san: [san],
    depth: 18,
    seldepth: 24,
    nodes: 10,
    nps: 1000,
    tbhits: 0,
  };
}
