export type ColorName = "white" | "black";

export type MoveQualityLabel =
  | "forced"
  | "best"
  | "excellent"
  | "good"
  | "neutral"
  | "inaccuracy"
  | "mistake"
  | "blunder"
  | "missed_win";

export type FindabilityLabel =
  | "obvious"
  | "findable"
  | "hard"
  | "very_hard"
  | "engine_like"
  | "unknown";

export type RecommendationPolicy =
  | "recommend_directly"
  | "mention_with_caveat"
  | "use_as_practical_alternative"
  | "explain_as_hidden_resource"
  | "do_not_recommend";

export type PracticalityCategory =
  | "clear_recommendation"
  | "practical_try"
  | "hard_but_important"
  | "engine_benchmark"
  | "only_move"
  | "unknown_practicality";

export type SignificanceLabel = "low" | "moderate" | "high" | "critical";

export type ConceptClaimKind =
  | "move_quality"
  | "forced_move"
  | "forced_mate"
  | "forcing_move"
  | "critical_best_move"
  | "capture"
  | "recapture"
  | "castling"
  | "en_passant"
  | "promotion"
  | "practical_alternative"
  | "better_alternative"
  | "opponent_resource"
  | "hidden_resource"
  | "hard_to_find"
  | "teachable_skill_gap"
  | "material"
  | "tactic"
  | "tactical_proof"
  | "king_safety"
  | "center"
  | "development"
  | "initiative"
  | "space"
  | "pawn_structure"
  | "passed_pawn"
  | "open_file"
  | "piece_activity"
  | "weak_square";

export type ConceptClaimSubject =
  | "played_move"
  | "key_move"
  | "featured_move"
  | "engine_best_move"
  | "practical_alternative"
  | "opponent_reply"
  | "tactical_reply"
  | "position";

export type ConceptClaimSource =
  | "quality_classification"
  | "legal_move_count"
  | "played_move_fact"
  | "candidate_policy"
  | "engine_line"
  | "human_likelihood"
  | "deterministic_detector";

export type GameImportSource = "chess_com_live_url" | "lichess_game_url" | "pgn";

export type GameAnalysisStatus = "pending" | "running" | "succeeded" | "failed";

export type GameMoveAnalysisState = "context_ready" | "explained" | "explanation_failed";

export interface ContextResult {
  evidence: EvidencePacket;
  llm_context: LLMContext;
  verification: VerificationResult;
}

export interface EvidencePacket {
  context_version: string;
  request: MoveContextRequest;
  position: PositionContext;
  played: PlayedMoveFacts;
  engine: EngineAnalysis;
  quality: MoveQuality;
  significance: MoveSignal;
  beauty: MoveSignal;
  candidates: CandidateMove[];
  main_point: MainPoint;
  concept_claims: ConceptClaim[];
  allowed_claims: string[];
}

export interface MoveContextRequest {
  player_color: ColorName;
  player_level: PlayerLevel;
  played_move: string | null;
  fen_before: string | null;
  pgn: string | null;
  ply: number | null;
  time_control: string | null;
  clock_before_seconds: number | null;
  increment_seconds: number | null;
  opponent_level: PlayerLevel | null;
}

export interface PlayerLevel {
  kind: "rating" | "label";
  value: number | string;
  system: string | null;
}

export interface PositionContext {
  fen_before: string;
  fen_after: string;
  side_to_move: ColorName;
  move_number: number;
  ply: number;
  phase: string;
  legal_moves_uci: string[];
}

export interface PlayedMoveFacts {
  uci: string;
  san: string;
  legal: boolean;
  is_check: boolean;
  is_capture: boolean;
  promotion: string | null;
}

export interface EngineAnalysis {
  engine_version: string;
  analysis_budget: EngineAnalysisBudget;
  engine_options: Record<string, number | string | boolean | null>;
  top_lines: EngineLine[];
  played_line: EngineLine;
  after_line: EngineLine | null;
}

export interface EngineAnalysisBudget {
  kind: "depth" | "nodes" | "static";
  value: number | string | null;
  multipv: number | null;
}

export interface EngineLine {
  move_uci: string;
  move_san: string;
  score: Score;
  rank: number | null;
  wdl: Wdl | null;
  pv_uci: string[];
  pv_san: string[];
  depth: number | null;
  seldepth: number | null;
  nodes: number | null;
  nps: number | null;
  tbhits: number | null;
}

export interface Score {
  kind: "cp" | "mate";
  value: number | null;
  mate_in: number | null;
  mate_for: "player" | "opponent" | null;
}

export interface Wdl {
  win: number;
  draw: number;
  loss: number;
}

export interface MoveQuality {
  label: MoveQualityLabel;
  score_delta_cp_player_pov: number | null;
  score_loss_vs_best_cp: number | null;
  wdl_delta_player_pov: Wdl | null;
  wdl_expected_score_loss: number | null;
  severity_text: string;
}

export interface MoveSignal {
  label: string;
  score: number;
}

export interface CandidateMove {
  san: string;
  uci: string;
  roles: string[];
  engine_rank: number | null;
  human_rank: number | null;
  score: Score;
  score_loss_vs_best_cp: number | null;
  wdl: Wdl | null;
  pv_short_san: string[];
  player_level_probability: number | null;
  plus_400_probability: number | null;
  player_level_bucket?: string | null;
  plus_400_level_bucket?: string | null;
  time_adjusted_findability: FindabilityLabel;
  forcing_tier?: string | null;
  findability_source: string;
  findability_confidence: string;
  teachable_skill_gap: boolean;
  practicality: PracticalityCategory;
  recommendation_policy: RecommendationPolicy;
}

export interface MainPoint {
  concept: string;
  claim: string;
}

export interface ConceptClaim {
  kind: ConceptClaimKind;
  subject: ConceptClaimSubject;
  claim: string;
  source: ConceptClaimSource;
  move_san: string | null;
}

export interface LLMContext {
  played: string;
  quality: MoveQualityLabel;
  significance: MoveSignal;
  beauty: MoveSignal;
  player_level: string;
  time_situation: string;
  severity: string;
  main_point: string;
  best_or_key_move: KeyMoveContext | null;
  human_note: string | null;
  concept_claims: ConceptClaim[];
  allowed_claims: string[];
}

export interface KeyMoveContext {
  move: string;
  practicality: PracticalityCategory;
  findability: FindabilityLabel;
  reason: string;
  recommendation_policy: RecommendationPolicy;
}

export interface VerificationResult {
  verifier_version: string;
  passed: boolean;
  failures: VerificationIssue[];
  warnings: VerificationIssue[];
}

export interface VerificationIssue {
  code: string;
  message: string;
  path: string;
}

export interface ImportedGameMetadata {
  source: GameImportSource;
  source_url: string | null;
  external_game_id: string | null;
  title: string;
  white_username: string | null;
  black_username: string | null;
  white_rating: number | null;
  black_rating: number | null;
  time_control: string | null;
  result: string | null;
  allows_global_training: boolean;
  rights_basis: string;
}

export interface GameAnalysisImportRequest {
  source: GameImportSource;
  url?: string | null;
  pgn?: string | null;
  player_level?: PlayerLevel | null;
  white_player_level?: PlayerLevel | null;
  black_player_level?: PlayerLevel | null;
  time_control?: string | null;
  explain_significance?: SignificanceLabel[];
  include_context?: boolean;
  use_baseline_fallback?: boolean;
  turnstile_token?: string | null;
}

export interface GameAnalysisImportResponse {
  analysis_id: string;
  status: GameAnalysisStatus;
  status_url: string;
  source: ImportedGameMetadata;
  game?: GameAnalysisGame | null;
}

export interface GameMainlineMove {
  ply: number;
  move_number: number;
  player_color: ColorName;
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  clock_before_seconds?: number | null;
  remaining_clock_seconds?: number | null;
  think_time_seconds?: number | null;
}

export interface GameAnalysisGame {
  total_plies: number;
  moves: GameMainlineMove[];
}

export interface ExplanationSegment {
  text: string;
  line_card_id: string | null;
  line_card_anchor?: string | null;
}

export interface ExplanationLineCard {
  id: string;
  moves: string[];
  title: string;
  why: string;
}

export interface BookLineMove {
  san: string;
  uci: string;
}

export interface BookLine {
  moves: BookLineMove[];
  weight: number;
  opening_name: string | null;
  eco: string | null;
}

export interface OpeningBookMetadata {
  is_book_move: boolean;
  is_novelty: boolean;
  book_lines: BookLine[];
  opening_name: string | null;
  eco: string | null;
}

export interface GameMoveAnalysis {
  ply: number;
  move_number?: number | null;
  san: string;
  uci: string;
  player_color: ColorName;
  fen_before?: string | null;
  fen_after?: string | null;
  state: GameMoveAnalysisState;
  requires_explanation: boolean;
  quality: MoveQualityLabel;
  significance: MoveSignal;
  beauty: MoveSignal;
  quality_severity_text?: string | null;
  score_loss_vs_best_cp?: number | null;
  phase?: string | null;
  legal_move_count?: number | null;
  context_version?: string | null;
  verifier_version?: string | null;
  engine_version?: string | null;
  engine_top_lines?: EngineLine[];
  engine_played_line?: EngineLine | null;
  main_point?: MainPoint | null;
  concept_claims?: ConceptClaim[];
  allowed_claims?: string[];
  human_common_candidate?: CandidateMove | null;
  player_level?: string | null;
  time_situation?: string | null;
  best_or_key_move?: KeyMoveContext | null;
  context_latency_seconds: number;
  clock_before_seconds?: number | null;
  remaining_clock_seconds?: number | null;
  think_time_seconds?: number | null;
  opening_book?: OpeningBookMetadata | null;
  explanation: string | null;
  explanation_segments?: ExplanationSegment[];
  explanation_line_cards?: ExplanationLineCard[];
  explanation_latency_seconds: number | null;
  explanation_attempts: number;
  explanation_model: string | null;
  explanation_error: string | null;
  context: ContextResult | null;
}

export interface GameAnalysisSnapshot {
  snapshot_version: string;
  analysis_id: string;
  status: GameAnalysisStatus;
  total_plies: number;
  context_completed: number;
  explanation_required: number;
  explanation_completed: number;
  explanation_failed: number;
  explain_significance: SignificanceLabel[];
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  game?: GameAnalysisGame | null;
  moves: GameMoveAnalysis[];
}
