import { describe, expect, it } from "vitest";
import type {
  CandidateMove,
  ContextResult,
  EngineLine,
  GameAnalysisSnapshot,
  GameMoveAnalysis,
  ImportedGameMetadata,
  MoveQualityLabel,
  Score,
} from "../types/api";
import { mapGameAnalysisSnapshot, scoreToWhitePovCp } from "./game-analysis-mapping";

describe("mapGameAnalysisSnapshot", () => {
  it("preserves move context, classifications, explanations, and white-POV evals", () => {
    const source: ImportedGameMetadata = {
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
    const snapshot: GameAnalysisSnapshot = {
      snapshot_version: "game_analysis_snapshot.v1",
      analysis_id: "analysis-1",
      status: "succeeded",
      total_plies: 2,
      context_completed: 2,
      explanation_required: 1,
      explanation_completed: 1,
      explanation_failed: 0,
      explain_significance: ["critical"],
      created_at: "2026-05-04T10:00:00Z",
      updated_at: "2026-05-04T10:00:01Z",
      started_at: "2026-05-04T10:00:00Z",
      completed_at: "2026-05-04T10:00:01Z",
      error: null,
      moves: [
        moveAnalysis({
          ply: 1,
          moveNumber: 1,
          playerColor: "white",
          san: "e4",
          uci: "e2e4",
          fenBefore: "startpos w",
          fenAfter: "after e4 b",
          quality: "excellent",
          topScore: cp(50),
          playedScore: cp(40),
          explanation: "e4 was strong.",
          explanationSegments: [
            {
              text: "e4 was strong.",
              line_card_id: "central-line",
              line_card_anchor: "e4",
            },
          ],
          explanationLineCards: [
            {
              id: "central-line",
              moves: ["e4", "Nf3", "d4"],
              title: "Central rollout",
              why: "White gets both central pawns moving with easy development.",
            },
          ],
        }),
        moveAnalysis({
          ply: 2,
          moveNumber: 1,
          playerColor: "black",
          san: "e5",
          uci: "e7e5",
          fenBefore: "after e4 b",
          fenAfter: "after e5 w",
          quality: "missed_win",
          topScore: cp(80),
          playedScore: cp(-120),
          explanation: "e5 missed the stronger central resource.",
        }),
      ],
    };

    const mapped = mapGameAnalysisSnapshot(snapshot, source);

    expect(mapped.title).toBe("Alpha vs Beta");
    expect(mapped.headers).toMatchObject({
      White: "Alpha",
      Black: "Beta",
      WhiteElo: "1600",
      BlackElo: "1500",
      TimeControl: "180+2",
    });
    expect(mapped.moves[0]).toMatchObject({
      ply: 1,
      san: "e4",
      uci: "e2e4",
      fen_before: "startpos w",
      fen_after: "after e4 b",
    });
    expect(mapped.timeline[0]?.eval_cp).toBe(40);
    expect(mapped.timeline[1]?.eval_cp).toBe(120);
    expect(mapped.timeline[1]?.best_lines[0]?.eval_cp).toBe(-80);
    expect(mapped.move_markers[0]?.primary_class).toBe("excellent");
    expect(mapped.move_markers[0]?.explanation).toBe("e4 was strong.");
    expect(mapped.move_markers[0]?.explanation_segments).toEqual([
      { text: "e4 was strong.", line_card_id: "central-line", line_card_anchor: "e4" },
    ]);
    expect(mapped.move_markers[0]?.explanation_line_cards).toEqual([
      {
        id: "central-line",
        moves: ["e4", "Nf3", "d4"],
        title: "Central rollout",
        why: "White gets both central pawns moving with easy development.",
      },
    ]);
    expect(mapped.move_markers[1]?.primary_class).toBe("miss");
    expect(mapped.move_markers[1]?.explanation_segments).toEqual([
      {
        text: "e5 missed the stronger central resource.",
        line_card_id: null,
        line_card_anchor: null,
      },
    ]);
    expect(mapped.move_markers[1]?.best_lines[0]?.pv_uci).toEqual(["e7e5", "g1f3"]);
    expect(mapped.summary).toMatchObject({
      engine_version: "test-stockfish",
      context_version: "context.v1",
      verifier_version: "verifier.v1",
    });
  });
});

describe("scoreToWhitePovCp", () => {
  it("converts mate scores from player POV to white POV", () => {
    expect(
      scoreToWhitePovCp({ kind: "mate", value: null, mate_in: 3, mate_for: "player" }, "black"),
    ).toBe(-99_997);
    expect(
      scoreToWhitePovCp({ kind: "mate", value: null, mate_in: 2, mate_for: "opponent" }, "black"),
    ).toBe(99_998);
  });
});

function moveAnalysis({
  ply,
  moveNumber,
  playerColor,
  san,
  uci,
  fenBefore,
  fenAfter,
  quality,
  topScore,
  playedScore,
  explanation,
  explanationSegments,
  explanationLineCards,
}: {
  ply: number;
  moveNumber: number;
  playerColor: "white" | "black";
  san: string;
  uci: string;
  fenBefore: string;
  fenAfter: string;
  quality: MoveQualityLabel;
  topScore: Score;
  playedScore: Score;
  explanation: string;
  explanationSegments?: NonNullable<GameMoveAnalysis["explanation_segments"]>;
  explanationLineCards?: NonNullable<GameMoveAnalysis["explanation_line_cards"]>;
}): GameMoveAnalysis {
  return {
    ply,
    san,
    uci,
    player_color: playerColor,
    state: "explained",
    requires_explanation: true,
    quality,
    significance: { label: "critical", score: 1 },
    beauty: { label: "ordinary", score: 0 },
    context_latency_seconds: 0.01,
    explanation,
    ...(explanationSegments === undefined ? {} : { explanation_segments: explanationSegments }),
    ...(explanationLineCards === undefined ? {} : { explanation_line_cards: explanationLineCards }),
    explanation_latency_seconds: 0.02,
    explanation_attempts: 1,
    explanation_model: "test-model",
    explanation_error: null,
    context: context({
      ply,
      moveNumber,
      playerColor,
      san,
      uci,
      fenBefore,
      fenAfter,
      quality,
      topScore,
      playedScore,
    }),
  };
}

function context({
  ply,
  moveNumber,
  playerColor,
  san,
  uci,
  fenBefore,
  fenAfter,
  quality,
  topScore,
  playedScore,
}: {
  ply: number;
  moveNumber: number;
  playerColor: "white" | "black";
  san: string;
  uci: string;
  fenBefore: string;
  fenAfter: string;
  quality: MoveQualityLabel;
  topScore: Score;
  playedScore: Score;
}): ContextResult {
  return {
    evidence: {
      context_version: "context.v1",
      request: {
        player_color: playerColor,
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
        side_to_move: playerColor,
        move_number: moveNumber,
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
        top_lines: [line(san, uci, topScore)],
        played_line: line(san, uci, playedScore),
        after_line: line("Nf3", "g1f3", playedScore),
      },
      quality: {
        label: quality,
        score_delta_cp_player_pov: null,
        score_loss_vs_best_cp: 40,
        wdl_delta_player_pov: null,
        wdl_expected_score_loss: null,
        severity_text: quality,
      },
      significance: { label: "critical", score: 1 },
      beauty: { label: "ordinary", score: 0 },
      candidates: [
        candidate(san, uci, "played_move"),
        candidate("Nf3", "g1f3", "human_common_move"),
      ],
      main_point: {
        concept: "central control",
        claim: `${san} changes the center.`,
      },
      allowed_claims: ["center"],
    },
    llm_context: {
      played: san,
      quality,
      significance: { label: "critical", score: 1 },
      beauty: { label: "ordinary", score: 0 },
      player_level: "1500",
      time_situation: "normal",
      severity: quality,
      main_point: `${san} changes the center.`,
      best_or_key_move: null,
      human_note: null,
      allowed_claims: ["center"],
    },
    verification: {
      verifier_version: "verifier.v1",
      passed: true,
      failures: [],
      warnings: [],
    },
  };
}

function line(san: string, uci: string, score: Score): EngineLine {
  return {
    move_uci: uci,
    move_san: san,
    score,
    rank: 1,
    wdl: { win: 500, draw: 300, loss: 200 },
    pv_uci: [uci, "g1f3"],
    pv_san: [san, "Nf3"],
    depth: 18,
    seldepth: 24,
    nodes: 10,
    nps: 1000,
    tbhits: 0,
  };
}

function candidate(san: string, uci: string, role: CandidateMove["roles"][number]): CandidateMove {
  return {
    san,
    uci,
    roles: [role],
    engine_rank: null,
    human_rank: null,
    score: cp(20),
    score_loss_vs_best_cp: null,
    wdl: null,
    pv_short_san: [san],
    player_level_probability: null,
    plus_400_probability: null,
    time_adjusted_findability: "unknown",
    findability_source: "test",
    findability_confidence: "unknown",
    teachable_skill_gap: false,
    practicality: "unknown_practicality",
    recommendation_policy: "do_not_recommend",
  };
}

function cp(value: number): Score {
  return { kind: "cp", value, mate_in: null, mate_for: null };
}
