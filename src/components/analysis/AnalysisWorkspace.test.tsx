import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  EngineLine,
  GameAnalysisSnapshot,
  GameMoveAnalysis,
  ImportedGameMetadata,
} from "../../types/api";
import { AnalysisWorkspace } from "./AnalysisWorkspace";

const apiMocks = vi.hoisted(() => ({
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
    window.localStorage.clear();
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(min-width: 1280px)",
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
    apiMocks.startImportedGameAnalysis.mockReset();
    apiMocks.pollGameAnalysis.mockReset();
    stockfishMocks.analyze.mockReset();
    stockfishMocks.preAnalyze.mockReset();
  });

  afterEach(() => {
    cleanup();
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
          url: "https://www.chess.com/game/168193636078",
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
  });
});

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
  return {
    snapshot_version: "game_analysis_snapshot.v1",
    analysis_id: "analysis-1",
    status: "succeeded",
    total_plies: 1,
    context_completed: 1,
    explanation_required: 1,
    explanation_completed: 1,
    explanation_failed: 0,
    explain_significance: ["critical"],
    created_at: "2026-05-04T10:00:00Z",
    updated_at: "2026-05-04T10:00:01Z",
    started_at: "2026-05-04T10:00:00Z",
    completed_at: "2026-05-04T10:00:01Z",
    error: null,
    moves: [moveAnalysis()],
  };
}

function moveAnalysis(): GameMoveAnalysis {
  return {
    ply: 1,
    san: "a4",
    uci: "a2a4",
    player_color: "white",
    state: "explained",
    requires_explanation: true,
    quality: "excellent",
    significance: { label: "critical", score: 1 },
    beauty: { label: "ordinary", score: 0 },
    context_latency_seconds: 0.01,
    explanation: "a4 gains space without weakening the center.",
    explanation_latency_seconds: 0.02,
    explanation_attempts: 1,
    explanation_model: "test-model",
    explanation_error: null,
    context: {
      evidence: {
        context_version: "context.v1",
        request: {
          player_color: "white",
          player_level: { kind: "rating", value: 1500, system: "test" },
          played_move: "a2a4",
          fen_before: "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1",
          pgn: null,
          ply: 1,
          time_control: "rapid",
          clock_before_seconds: null,
          increment_seconds: null,
          opponent_level: null,
        },
        position: {
          fen_before: "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1",
          fen_after: "rn1qkbnr/pppbpppp/8/3p4/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1",
          side_to_move: "white",
          move_number: 1,
          ply: 1,
          phase: "opening",
          legal_moves_uci: ["a2a4"],
        },
        played: {
          uci: "a2a4",
          san: "a4",
          legal: true,
          is_check: false,
          is_capture: false,
          promotion: null,
        },
        engine: {
          engine_version: "test-stockfish",
          analysis_budget: { kind: "static", value: 1, multipv: 1 },
          engine_options: {},
          top_lines: [engineLine()],
          played_line: engineLine(),
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
        significance: { label: "critical", score: 1 },
        beauty: { label: "ordinary", score: 0 },
        candidates: [],
        main_point: {
          concept: "space",
          claim: "a4 gains useful queenside space.",
        },
        allowed_claims: ["space"],
      },
      llm_context: {
        played: "a4",
        quality: "excellent",
        significance: { label: "critical", score: 1 },
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

function engineLine(): EngineLine {
  return {
    move_uci: "a2a4",
    move_san: "a4",
    score: { kind: "cp", value: 35, mate_in: null, mate_for: null },
    rank: 1,
    wdl: null,
    pv_uci: ["a2a4"],
    pv_san: ["a4"],
    depth: 18,
    seldepth: 24,
    nodes: 10,
    nps: 1000,
    tbhits: 0,
  };
}
