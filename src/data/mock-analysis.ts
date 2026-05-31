import { Chess, Color, type VerboseMove } from "ultrachess/inline";
import { START_FEN } from "../lib/chess";
import type {
  AnalysisMoveMarker,
  AnalysisResponse,
  AnalysisTimelinePoint,
  BestLine,
  GameMove,
  MovePrimaryClass,
} from "../types/analysis";

const OPERA_SAN = [
  "e4",
  "e5",
  "Nf3",
  "d6",
  "d4",
  "Bg4",
  "dxe5",
  "Bxf3",
  "Qxf3",
  "dxe5",
  "Bc4",
  "Nf6",
  "Qb3",
  "Qe7",
  "Nc3",
  "c6",
  "Bg5",
  "h5",
  "h4",
  "Rh6",
  "a3",
  "Rh8",
  "a4",
  "b5",
  "Nxb5",
  "cxb5",
  "Bxb5+",
  "Nbd7",
  "O-O-O",
  "Rd8",
  "Rxd7",
  "Rxd7",
  "Rd1",
  "Qe6",
  "Bxd7+",
  "Nxd7",
  "Qb8+",
  "Nxb8",
  "Rd8#",
] as const;

const TIMELINE_EVALS = [
  24, 18, 29, 38, 52, 94, 88, 71, 112, 96, 130, 155, 178, 150, 194, 205, 248, 248, 240, 250, 245,
  255, 260, 420, 690, 610, 740, 705, 880, 820, 1330, 1190, 1640, 920, 2100, 1950, 99_998, 99_999,
  100_000,
] as const;

export const MOCK_ANALYSIS = buildMockAnalysis();

function buildMockAnalysis(): AnalysisResponse {
  const moves = buildMoves();
  const timeline = buildTimeline(moves);
  const move_markers = buildMarkers(moves);

  return {
    id: "morphy-opera-explanation-local",
    title: "Morphy Opera Game",
    player_side: "white",
    headers: {
      Event: "Casual Game",
      Site: "Paris FRA",
      White: "Paul Morphy",
      Black: "Duke Karl / Count Isouard",
      WhiteElo: "2400",
      BlackElo: "2200",
      TimeControl: "Classical",
      Result: "1-0",
    },
    moves,
    timeline,
    move_markers,
    summary: {
      engine_version: "Mock Stockfish 18 depth 18",
      context_version: "mock-context-v1",
      verifier_version: "mock-verifier-v1",
    },
  };
}

function buildMoves(): GameMove[] {
  const chess = Chess.createSync(START_FEN);
  try {
    return OPERA_SAN.map((san, index) => {
      const fenBefore = chess.fen();
      const packed = chess.parseSan(san);
      const verbose = chess.verboseMove(packed) as VerboseMove;
      const side = verbose.color === Color.White ? "white" : "black";
      chess.move(packed);
      return {
        ply: index + 1,
        move_number: Math.ceil((index + 1) / 2),
        side,
        san: verbose.san,
        uci: verbose.uci,
        fen_before: fenBefore,
        fen_after: chess.fen(),
        remaining_clock_seconds: Math.max(42, 1_800 - index * 43),
        think_time_seconds: 18 + ((index * 7) % 41),
      };
    });
  } finally {
    chess.dispose();
  }
}

function buildTimeline(moves: GameMove[]): AnalysisTimelinePoint[] {
  return moves.map((move, index) => ({
    ply: move.ply,
    san: move.san,
    side: move.side,
    eval_cp: TIMELINE_EVALS[index] ?? null,
    fen_before: move.fen_before,
    best_lines: [
      {
        san: move.san,
        uci: move.uci,
        eval_cp: TIMELINE_EVALS[index] ?? 0,
        pv_san: moves.slice(index, index + 4).map((lineMove) => lineMove.san),
        pv_uci: moves.slice(index, index + 4).map((lineMove) => lineMove.uci),
      },
    ],
  }));
}

function buildMarkers(moves: GameMove[]): AnalysisMoveMarker[] {
  const explicitList = [
    marker({
      moves,
      ply: 9,
      rank_order: 4,
      primary_class: "excellent",
      eval_before_cp: 71,
      eval_after_cp: 112,
      drop_cp: 0,
      explanation:
        "Qxf3 keeps the queen active and recaptures without slowing the attack. The important point is that White keeps pressure on f7 while the black king is still stuck in the center.",
      bestLine: line("Qxf3", "d1f3", 112, ["Qxf3", "dxe5", "Bc4", "Nf6"]),
      tags: ["developing_with_tempo", "king_in_center"],
    }),
    marker({
      moves,
      ply: 22,
      rank_order: 7,
      primary_class: "mistake",
      eval_before_cp: 250,
      eval_after_cp: 255,
      drop_cp: 0,
      explanation: "Rh8 retreats the rook to the corner, losing time.",
      bestLine: line("Rh8", "h6h8", 255, ["Rh8"]),
      tags: ["losing_tempo"],
    }),
    marker({
      moves,
      ply: 24,
      rank_order: 1,
      primary_class: "blunder",
      best_move_san: "Nbd7",
      best_move_uci: "b8d7",
      eval_before_cp: 248,
      eval_after_cp: 420,
      drop_cp: 172,
      explanation:
        "b5 grabs space but leaves the queenside too loose. After Nxb5, Black cannot keep the king safe and the open files become more important than the pawn.",
      bestLine: line("Nbd7", "b8d7", 210, ["Nbd7", "O-O-O", "h6", "Bh4"]),
      natural_move_san: "b5",
      natural_move_uci: "b7b5",
      tags: ["king_safety", "tactical_looseness"],
    }),
    marker({
      moves,
      ply: 25,
      rank_order: 3,
      primary_class: "brilliant",
      best_move_san: "Bxb5+",
      best_move_uci: "c4b5",
      eval_before_cp: 420,
      eval_after_cp: 690,
      drop_cp: 0,
      explanation:
        "Nxb5 is a concrete sacrifice to open lines. White is not winning because of material; White is winning because Black's king cannot survive the forced development race.",
      bestLine: line("Bxb5+", "c4b5", 760, ["Bxb5+", "Nbd7", "O-O-O", "Rd8"]),
      natural_move_san: "Nxb5",
      natural_move_uci: "c3b5",
      tags: ["sacrifice", "open_files", "initiative"],
    }),
    marker({
      moves,
      ply: 31,
      rank_order: 2,
      primary_class: "great",
      eval_before_cp: 820,
      eval_after_cp: 1330,
      drop_cp: 0,
      explanation:
        "Rxd7 removes the defender and forces Black's pieces onto awkward squares. The sacrifice works because every recapture improves White's rook access to the d-file.",
      bestLine: line("Rxd7", "d1d7", 1330, ["Rxd7", "Rxd7", "Rd1", "Qe6"]),
      tags: ["exchange_sacrifice", "open_file", "forcing_sequence"],
    }),
    marker({
      moves,
      ply: 34,
      rank_order: 5,
      primary_class: "mistake",
      best_move_san: "Qe6",
      best_move_uci: "e7e6",
      eval_before_cp: 1640,
      eval_after_cp: 920,
      drop_cp: 720,
      explanation:
        "Qe6 blocks one threat but lets White simplify into the final attack. The problem is not the queen move by itself; it is that Black has no time to solve the back rank and the pinned knight together.",
      bestLine: line("Qe6", "e7e6", 920, ["Qe6", "Bxd7+", "Nxd7", "Qb8+"]),
      tags: ["defensive_overload", "back_rank"],
    }),
    marker({
      moves,
      ply: 37,
      rank_order: 8,
      primary_class: "brilliant",
      eval_before_cp: 920,
      eval_after_cp: 1950,
      drop_cp: 0,
      explanation: "Qb8+ is a brilliant queen sacrifice leading to forced checkmate.",
      bestLine: line("Qb8+", "b3b8+", 1950, ["Qb8+", "Nxb8", "Rd8#"]),
      tags: ["sacrifice", "forcing_sequence"],
    }),
    marker({
      moves,
      ply: 39,
      rank_order: 6,
      primary_class: "best",
      eval_before_cp: 99_999,
      eval_after_cp: 100_000,
      drop_cp: 0,
      explanation:
        "Rd8# is the whole attack arriving at once. The rook reaches the back rank, the queen covers b8, and Black has no legal capture, block, or king move.",
      bestLine: line("Rd8#", "d1d8", 100_000, ["Rd8#"]),
      tags: ["checkmate", "back_rank", "coordination"],
    }),
  ];

  const explicitMap = new Map(explicitList.map((m) => [m.ply, m]));
  const allMarkers: AnalysisMoveMarker[] = [];

  for (let index = 0; index < moves.length; index++) {
    const ply = index + 1;
    const move = moves[index];
    if (move === undefined) {
      continue;
    }
    const explicitMarker = explicitMap.get(ply);
    if (explicitMarker !== undefined) {
      allMarkers.push(explicitMarker);
    } else {
      const isBook = ply <= 8;
      const primary_class = isBook ? "book" : ply % 2 === 0 ? "good" : "best";
      const evalCp = TIMELINE_EVALS[index] ?? 0;
      allMarkers.push(
        marker({
          moves,
          ply,
          rank_order: ply,
          primary_class,
          eval_before_cp: evalCp,
          eval_after_cp: evalCp,
          drop_cp: 0,
          explanation: isBook
            ? `${move.san} is a standard book move.`
            : `${move.san} is a solid move maintaining the evaluation.`,
          bestLine: line(move.san, move.uci, evalCp, [move.san]),
          tags: isBook ? ["opening"] : ["developing_move"],
          requires_explanation: false,
        }),
      );
    }
  }

  return allMarkers;
}

function marker({
  moves,
  ply,
  rank_order,
  primary_class,
  best_move_san,
  best_move_uci,
  natural_move_san,
  natural_move_uci,
  eval_before_cp,
  eval_after_cp,
  drop_cp,
  explanation,
  bestLine,
  tags,
  requires_explanation = true,
}: {
  moves: GameMove[];
  ply: number;
  rank_order: number;
  primary_class: MovePrimaryClass;
  best_move_san?: string;
  best_move_uci?: string;
  natural_move_san?: string;
  natural_move_uci?: string;
  eval_before_cp: number;
  eval_after_cp: number;
  drop_cp: number;
  explanation: string;
  bestLine: BestLine;
  tags: string[];
  requires_explanation?: boolean;
}): AnalysisMoveMarker {
  const move = moves[ply - 1];
  if (move === undefined) {
    throw new Error(`Mock move ${ply} is missing`);
  }

  return {
    rank_order,
    ply,
    move_number: move.move_number,
    side: move.side,
    san: move.san,
    uci: move.uci,
    best_move_san: best_move_san ?? bestLine.san,
    best_move_uci: best_move_uci ?? bestLine.uci,
    natural_move_san: natural_move_san ?? null,
    natural_move_uci: natural_move_uci ?? null,
    primary_class,
    tags,
    label_metadata: {
      requires_explanation,
      score_loss_vs_best_cp: drop_cp,
      swing_from_root: eval_after_cp - eval_before_cp,
      context_version: "mock-context-v1",
      verifier: "deterministic display mock",
    },
    eval_before_cp,
    eval_after_cp,
    drop_cp,
    explanation,
    explanation_segments: [
      { text: explanation, line_card_id: null, line_card_anchor: null, highlight_color: null },
    ],
    explanation_line_cards: [],
    best_lines: [bestLine],
  };
}

function line(san: string, uci: string, eval_cp: number, pv_san: string[]): BestLine {
  return {
    san,
    uci,
    eval_cp,
    pv_san,
    pv_uci: [uci],
  };
}
