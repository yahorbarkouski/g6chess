export type BoardSide = "white" | "black";

type MoveQualityLabel =
  | "best"
  | "excellent"
  | "good"
  | "neutral"
  | "inaccuracy"
  | "mistake"
  | "blunder"
  | "miss"
  | "brilliant"
  | "great"
  | "book"
  | "forced";

export type MovePrimaryClass = Exclude<MoveQualityLabel, "forced">;

export interface CapturedPieces {
  q: number;
  r: number;
  b: number;
  n: number;
  p: number;
}

export interface MaterialInfo {
  white: CapturedPieces;
  black: CapturedPieces;
  advantage: number;
}

export interface GameMove {
  ply: number;
  move_number: number;
  side: BoardSide;
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  remaining_clock_seconds?: number;
  think_time_seconds?: number;
}

export interface BestLine {
  san: string;
  uci: string;
  eval_cp: number;
  win_probability?: number;
  pv_san: string[];
  pv_uci: string[];
}

interface BookLineMove {
  san: string;
  uci: string;
}

export interface BookLine {
  moves: BookLineMove[];
  weight: number;
  opening_name: string | null;
  eco: string | null;
}

export interface ExplanationSegment {
  text: string;
  line_card_id: string | null;
  line_card_anchor: string | null;
  highlight_color: ExplanationHighlightColor | null;
}

export type ExplanationHighlightColor = "red" | "orange" | "green" | "blue";

export interface ExplanationLineCard {
  id: string;
  moves: string[];
  title: string;
  why: string;
}

export interface AnalysisTimelinePoint {
  ply: number;
  san: string;
  side: BoardSide;
  eval_cp: number | null;
  fen_before: string;
  best_lines: BestLine[];
  is_book_move?: boolean;
  is_novelty?: boolean;
  book_lines?: BookLine[];
  opening_name?: string | null;
  eco?: string | null;
}

export interface AnalysisMoveMarker {
  rank_order: number;
  ply: number;
  move_number: number;
  side: BoardSide;
  san: string;
  uci: string;
  best_move_san?: string | null;
  best_move_uci?: string | null;
  natural_move_san?: string | null;
  natural_move_uci?: string | null;
  primary_class: MovePrimaryClass;
  tags: string[];
  label_metadata: Record<string, unknown>;
  is_book_move?: boolean;
  is_novelty?: boolean;
  book_lines?: BookLine[];
  opening_name?: string | null;
  eco?: string | null;
  eval_before_cp: number;
  eval_after_cp: number;
  drop_cp: number;
  explanation: string;
  explanation_segments: ExplanationSegment[];
  explanation_line_cards: ExplanationLineCard[];
  best_lines: BestLine[];
}

export interface AnalysisResponse {
  id: string;
  title: string;
  player_side: BoardSide;
  headers: Record<string, string>;
  moves: GameMove[];
  timeline: AnalysisTimelinePoint[];
  move_markers: AnalysisMoveMarker[];
  summary: {
    engine_version: string;
    context_version: string;
    verifier_version: string;
  };
}
