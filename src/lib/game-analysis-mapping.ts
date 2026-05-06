import type {
  AnalysisMoveMarker,
  AnalysisResponse,
  AnalysisTimelinePoint,
  BestLine,
  BookLine,
  ExplanationLineCard,
  ExplanationSegment,
  GameMove,
  MovePrimaryClass,
} from "../types/analysis";
import type {
  ExplanationLineCard as ApiExplanationLineCard,
  ExplanationSegment as ApiExplanationSegment,
  CandidateMove,
  ColorName,
  ContextResult,
  EngineLine,
  GameAnalysisGame,
  GameAnalysisImportResponse,
  GameAnalysisSnapshot,
  GameMainlineMove,
  GameMoveAnalysis,
  ImportedGameMetadata,
  OpeningBookMetadata,
  Score,
  Wdl,
} from "../types/api";

const MATE_SCORE_BASE = 100_000;

export function mapGameAnalysisSnapshot(
  snapshot: GameAnalysisSnapshot,
  source: ImportedGameMetadata | null = null,
  fallbackGame: GameAnalysisGame | null = null,
): AnalysisResponse {
  const movesWithContext = snapshot.moves
    .filter((move): move is GameMoveAnalysis & { context: ContextResult } => move.context !== null)
    .sort((a, b) => a.ply - b.ply);
  const game = snapshot.game ?? fallbackGame;
  const moves = game?.moves.length
    ? game.moves.map(mapMainlineMove)
    : movesWithContext.map(mapGameMove);
  const timeline = movesWithContext.map(mapTimelinePoint);
  const moveMarkers = movesWithContext.map((move, index) => mapMoveMarker(move, index));
  const firstContext = movesWithContext[0]?.context ?? null;

  return {
    id: snapshot.analysis_id,
    title: source?.title ?? `Game analysis ${snapshot.analysis_id.slice(0, 8)}`,
    player_side: "white",
    headers: sourceHeaders(source),
    moves,
    timeline,
    move_markers: moveMarkers,
    summary: {
      engine_version:
        firstContext?.evidence.engine.engine_version ?? "g6explanation game-analysis API",
      context_version: firstContext?.evidence.context_version ?? snapshot.snapshot_version,
      verifier_version: firstContext?.verification.verifier_version ?? "pending",
    },
  };
}

export function mapGameAnalysisImportResponse(
  response: GameAnalysisImportResponse,
): AnalysisResponse | null {
  if (!response.game?.moves.length) {
    return null;
  }
  return mapGameAnalysisGame(response.analysis_id, response.game, response.source);
}

export function mapGameAnalysisGame(
  analysisId: string,
  game: GameAnalysisGame,
  source: ImportedGameMetadata | null = null,
): AnalysisResponse {
  return {
    id: analysisId,
    title: source?.title ?? `Game analysis ${analysisId.slice(0, 8)}`,
    player_side: "white",
    headers: sourceHeaders(source),
    moves: game.moves.map(mapMainlineMove),
    timeline: [],
    move_markers: [],
    summary: {
      engine_version: "pending",
      context_version: "pending",
      verifier_version: "pending",
    },
  };
}

export function scoreToWhitePovCp(score: Score, playerColor: ColorName): number | null {
  const playerPovCp = scoreToPlayerPovCp(score);
  if (playerPovCp === null) {
    return null;
  }
  return playerColor === "white" ? playerPovCp : -playerPovCp;
}

function mapGameMove(move: GameMoveAnalysis & { context: ContextResult }): GameMove {
  const position = move.context.evidence.position;
  return {
    ply: move.ply,
    move_number: position.move_number,
    side: move.player_color,
    san: move.context.evidence.played.san || move.san,
    uci: move.context.evidence.played.uci || move.uci,
    fen_before: position.fen_before,
    fen_after: position.fen_after,
    ...(move.remaining_clock_seconds == null
      ? {}
      : { remaining_clock_seconds: move.remaining_clock_seconds }),
    ...(move.think_time_seconds == null ? {} : { think_time_seconds: move.think_time_seconds }),
  };
}

function mapMainlineMove(move: GameMainlineMove): GameMove {
  return {
    ply: move.ply,
    move_number: move.move_number,
    side: move.player_color,
    san: move.san,
    uci: move.uci,
    fen_before: move.fen_before,
    fen_after: move.fen_after,
    ...(move.remaining_clock_seconds == null
      ? {}
      : { remaining_clock_seconds: move.remaining_clock_seconds }),
    ...(move.think_time_seconds == null ? {} : { think_time_seconds: move.think_time_seconds }),
  };
}

function mapTimelinePoint(
  move: GameMoveAnalysis & { context: ContextResult },
): AnalysisTimelinePoint {
  const evidence = move.context.evidence;
  const openingBook = move.opening_book ?? null;
  const bookLines = mapBookLines(openingBook?.book_lines ?? []);
  return {
    ply: move.ply,
    san: evidence.played.san || move.san,
    side: move.player_color,
    eval_cp: scoreToWhitePovCp(evidence.engine.played_line.score, move.player_color),
    fen_before: evidence.position.fen_before,
    best_lines: evidence.engine.top_lines.map((line) => mapBestLine(line, move.player_color)),
    ...(openingBook === null
      ? {}
      : {
          is_book_move: openingBook.is_book_move,
          is_novelty: openingBook.is_novelty,
          book_lines: bookLines,
          opening_name: openingBook.opening_name,
          eco: openingBook.eco,
        }),
  };
}

function mapMoveMarker(
  move: GameMoveAnalysis & { context: ContextResult },
  index: number,
): AnalysisMoveMarker {
  const evidence = move.context.evidence;
  const openingBook = move.opening_book ?? null;
  const bookLines = mapBookLines(openingBook?.book_lines ?? []);
  const topLine = evidence.engine.top_lines[0] ?? evidence.engine.played_line;
  const naturalMove = humanCommonCandidate(evidence.candidates);
  const evalBeforeCp = scoreToWhitePovCp(topLine.score, move.player_color) ?? 0;
  const evalAfterCp = scoreToWhitePovCp(evidence.engine.played_line.score, move.player_color) ?? 0;
  const tags = markerTags(move, evidence.main_point.concept, openingBook);
  const explanation = move.explanation ?? evidence.main_point.claim;
  const explanationLineCards = mapExplanationLineCards(move.explanation_line_cards);
  const explanationSegments = mapExplanationSegments(
    move.explanation_segments,
    explanation,
    explanationLineCards,
  );

  return {
    rank_order: index + 1,
    ply: move.ply,
    move_number: evidence.position.move_number,
    side: move.player_color,
    san: evidence.played.san || move.san,
    uci: evidence.played.uci || move.uci,
    best_move_san: topLine.move_san,
    best_move_uci: topLine.move_uci,
    natural_move_san: naturalMove?.san ?? null,
    natural_move_uci: naturalMove?.uci ?? null,
    primary_class: openingBook?.is_book_move ? "book" : primaryClassFromApi(move),
    tags,
    label_metadata: {
      state: move.state,
      requires_explanation: move.requires_explanation,
      quality: move.quality,
      severity_text: evidence.quality.severity_text,
      significance_label: move.significance.label,
      significance_score: move.significance.score,
      beauty_label: move.beauty.label,
      beauty_score: move.beauty.score,
      phase: evidence.position.phase,
      legal_move_count: evidence.position.legal_moves_uci.length,
      main_point_concept: evidence.main_point.concept,
      main_point_claim: evidence.main_point.claim,
      allowed_claims: evidence.allowed_claims,
      player_level: move.context.llm_context.player_level,
      time_situation: move.context.llm_context.time_situation,
      best_or_key_move: move.context.llm_context.best_or_key_move?.move ?? null,
      best_or_key_reason: move.context.llm_context.best_or_key_move?.reason ?? null,
      engine_depth: topLine.depth,
      engine_nodes: topLine.nodes,
      context_latency_seconds: move.context_latency_seconds,
      explanation_model: move.explanation_model,
      explanation_error: move.explanation_error,
      is_book_move: openingBook?.is_book_move ?? false,
      is_novelty: openingBook?.is_novelty ?? false,
      book_lines: bookLines,
      opening_name: openingBook?.opening_name ?? null,
      eco: openingBook?.eco ?? null,
    },
    ...(openingBook === null
      ? {}
      : {
          is_book_move: openingBook.is_book_move,
          is_novelty: openingBook.is_novelty,
          book_lines: bookLines,
          opening_name: openingBook.opening_name,
          eco: openingBook.eco,
        }),
    eval_before_cp: evalBeforeCp,
    eval_after_cp: evalAfterCp,
    drop_cp: move.context.evidence.quality.score_loss_vs_best_cp ?? 0,
    explanation,
    explanation_segments: explanationSegments,
    explanation_line_cards: explanationLineCards,
    best_lines: evidence.engine.top_lines.map((line) => mapBestLine(line, move.player_color)),
  };
}

function mapBookLines(apiBookLines: OpeningBookMetadata["book_lines"]): BookLine[] {
  return apiBookLines
    .map((line) => {
      const moves = line.moves
        .map((move) => ({
          san: move.san.trim(),
          uci: move.uci.trim(),
        }))
        .filter((move) => move.san.length > 0 && move.uci.length > 0);
      if (moves.length === 0) {
        return null;
      }
      return {
        moves,
        weight: Math.max(0, line.weight),
        opening_name: cleanNullableString(line.opening_name),
        eco: cleanNullableString(line.eco),
      };
    })
    .filter((line): line is BookLine => line !== null);
}

function mapExplanationSegments(
  apiSegments: ApiExplanationSegment[] | undefined,
  fallbackExplanation: string,
  lineCards: ExplanationLineCard[],
): ExplanationSegment[] {
  const cardIds = new Set(lineCards.map((card) => card.id));
  const segments = (apiSegments ?? [])
    .map((segment) => {
      const text = segment.text.trim();
      if (!text) {
        return null;
      }
      const lineCardId =
        segment.line_card_id && cardIds.has(segment.line_card_id) ? segment.line_card_id : null;
      const anchor = segment.line_card_anchor?.trim() ?? null;
      const lineCardAnchor = lineCardId && anchor && text.includes(anchor) ? anchor : null;
      return { text, line_card_id: lineCardId, line_card_anchor: lineCardAnchor };
    })
    .filter((segment): segment is ExplanationSegment => segment !== null);

  if (segments.length > 0) {
    return segments;
  }

  const text = fallbackExplanation.trim();
  return text ? [{ text, line_card_id: null, line_card_anchor: null }] : [];
}

function mapExplanationLineCards(
  apiLineCards: ApiExplanationLineCard[] | undefined,
): ExplanationLineCard[] {
  return (apiLineCards ?? [])
    .map((card) => {
      const id = card.id.trim();
      const title = card.title.trim();
      const why = card.why.trim();
      const moves = card.moves.map((move) => move.trim()).filter(Boolean);
      if (!id || !title || !why || moves.length === 0) {
        return null;
      }
      return { id, title, why, moves };
    })
    .filter((card): card is ExplanationLineCard => card !== null);
}

function mapBestLine(line: EngineLine, playerColor: ColorName): BestLine {
  const evalCp = scoreToWhitePovCp(line.score, playerColor) ?? 0;
  const winProbability = winProbabilityFromWdl(line.wdl, playerColor, evalCp);
  return {
    san: line.move_san,
    uci: line.move_uci,
    eval_cp: evalCp,
    ...(winProbability === null ? {} : { win_probability: winProbability }),
    pv_san: line.pv_san,
    pv_uci: line.pv_uci,
  };
}

function scoreToPlayerPovCp(score: Score): number | null {
  if (score.kind === "cp") {
    return score.value;
  }
  if (score.mate_for === null || score.mate_in === null) {
    return null;
  }
  const distance = Math.max(0, score.mate_in);
  const sign = score.mate_for === "player" ? 1 : -1;
  return sign * Math.max(90_000, MATE_SCORE_BASE - distance);
}

function winProbabilityFromWdl(
  wdl: Wdl | null,
  playerColor: ColorName,
  evalCpWhitePov: number,
): number | null {
  if (wdl === null) {
    return null;
  }
  const total = wdl.win + wdl.draw + wdl.loss;
  if (total <= 0) {
    return null;
  }
  const whiteWin = playerColor === "white" ? wdl.win : wdl.loss;
  const blackWin = playerColor === "black" ? wdl.win : wdl.loss;
  return (evalCpWhitePov >= 0 ? whiteWin : blackWin) / total;
}

function primaryClassFromApi(move: GameMoveAnalysis): MovePrimaryClass {
  if (move.quality === "forced") {
    return "good";
  }
  if (move.quality === "missed_win") {
    return "miss";
  }
  if (isPositiveQuality(move.quality) && hasExceptionalPlayedMoveEvidence(move)) {
    if (move.beauty.label === "brilliant") {
      return "brilliant";
    }
    return "great";
  }
  return move.quality;
}

function isPositiveQuality(label: GameMoveAnalysis["quality"]): boolean {
  return label === "best" || label === "excellent" || label === "good";
}

function hasExceptionalPlayedMoveEvidence(move: GameMoveAnalysis): boolean {
  return hasPlayedMoveTacticClaim(move) || isPlayedMateForPlayer(move);
}

function hasPlayedMoveTacticClaim(move: GameMoveAnalysis): boolean {
  const playedSan = move.context?.evidence.played.san || move.san;
  return (move.context?.evidence.concept_claims ?? []).some(
    (claim) =>
      claim.kind === "tactic" &&
      claim.subject === "played_move" &&
      claim.source === "deterministic_detector" &&
      (claim.move_san === null || claim.move_san === playedSan),
  );
}

function isPlayedMateForPlayer(move: GameMoveAnalysis): boolean {
  const score = move.context?.evidence.engine.played_line.score;
  return score?.kind === "mate" && score.mate_for === "player";
}

function humanCommonCandidate(candidates: CandidateMove[]): CandidateMove | null {
  return (
    candidates.find(
      (candidate) =>
        candidate.roles.includes("human_common_move") && !candidate.roles.includes("played_move"),
    ) ?? null
  );
}

function markerTags(
  move: GameMoveAnalysis,
  concept: string,
  openingBook: OpeningBookMetadata | null,
): string[] {
  const tags = new Set<string>();
  if (move.quality === "forced") {
    tags.add("forced");
  }
  if (openingBook?.is_book_move) {
    tags.add("opening");
  }
  if (openingBook?.is_novelty) {
    tags.add("novelty");
  }
  if (move.significance.label !== "low") {
    tags.add(`${move.significance.label}_significance`);
  }
  if (move.beauty.label !== "ordinary") {
    tags.add(safeTag(move.beauty.label));
  }
  const conceptTag = safeTag(concept);
  if (conceptTag) {
    tags.add(conceptTag);
  }
  return Array.from(tags);
}

function cleanNullableString(value: string | null | undefined): string | null {
  const clean = value?.trim();
  return clean ? clean : null;
}

function sourceHeaders(source: ImportedGameMetadata | null): Record<string, string> {
  if (source === null) {
    return {};
  }
  return {
    ...(source.white_username === null ? {} : { White: source.white_username }),
    ...(source.black_username === null ? {} : { Black: source.black_username }),
    ...(source.white_rating === null ? {} : { WhiteElo: String(source.white_rating) }),
    ...(source.black_rating === null ? {} : { BlackElo: String(source.black_rating) }),
    ...(source.time_control === null ? {} : { TimeControl: source.time_control }),
    ...(source.result === null ? {} : { Result: source.result }),
    ...(source.source_url === null ? {} : { Link: source.source_url }),
  };
}

function safeTag(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function isTerminalGameAnalysisStatus(status: GameAnalysisSnapshot["status"]): boolean {
  return status === "succeeded" || status === "failed";
}
