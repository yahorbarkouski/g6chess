/**
 * Public transport types projected from the generated OpenAPI document.
 * UI-only state belongs in `analysis.ts`; do not hand-copy backend schemas here.
 */
import type { components, operations } from "../generated/g6-api";

type Schemas = components["schemas"];

export type ColorName = Schemas["GameMainlineMove"]["player_color"];
export type MoveQualityLabel = Schemas["GameMoveAnalysis"]["quality"];
export type FindabilityLabel = Schemas["CandidateMove"]["time_adjusted_findability"];
export type RecommendationPolicy = Schemas["CandidateMove"]["recommendation_policy"];
export type PracticalityCategory = Schemas["CandidateMove"]["practicality"];
export type SignificanceLabel = NonNullable<
  Schemas["GameAnalysisSnapshot"]["explain_significance"]
>[number];
export type ConceptClaimKind = Schemas["ConceptClaim"]["kind"];
export type ConceptClaimSubject = Schemas["ConceptClaim"]["subject"];
export type ConceptClaimSource = Schemas["ConceptClaim"]["source"];
export type GameImportSource = Schemas["ImportedGameMetadata"]["source"];
export type GameAnalysisStatus = Schemas["GameAnalysisSnapshot"]["status"];
export type GameMoveAnalysisState = Schemas["GameMoveAnalysis"]["state"];
export type ExplanationHighlightColor = NonNullable<
  Schemas["ExplanationSegment"]["highlight_color"]
>;

export type ContextResult = Schemas["ContextResult"];
export type EvidencePacket = Schemas["EvidencePacket"];
export type MoveContextRequest = Schemas["MoveContextRequest"];
export type PlayerLevel = Schemas["PlayerLevel"];
export type PositionContext = Schemas["PositionContext"];
export type PlayedMoveFacts = Schemas["PlayedMoveFacts"];
export type EngineAnalysis = Schemas["EngineAnalysis"];
export type EngineAnalysisBudget = Schemas["EngineAnalysisBudget"];
export type EngineLine = Schemas["EngineLine"];
export type Score = Schemas["Score"];
export type Wdl = Schemas["Wdl"];
export type MoveQuality = Schemas["MoveQuality"];
export type MoveSignal = Schemas["MoveSignificance"];
export type CandidateMove = Schemas["CandidateMove"];
export type MainPoint = Schemas["MainPoint"];
export type ConceptClaim = Schemas["ConceptClaim"];
export type LLMContext = Schemas["LLMContext"];
export type KeyMoveContext = Schemas["KeyMoveContext"];
export type VerificationResult = Schemas["VerificationResult"];
export type VerificationIssue = Schemas["VerificationIssue"];
export type ImportedGameMetadata = Schemas["ImportedGameMetadata"];
type GeneratedImportRequest =
  operations["submit_imported_game_analysis_api_game_analysis_import_post"]["requestBody"]["content"]["application/json"];
type ImportRequestDefaults = "include_context" | "use_baseline_fallback";
type WithOptionalImportDefaults<T> = T extends unknown
  ? Omit<T, ImportRequestDefaults> & Partial<Pick<T, Extract<keyof T, ImportRequestDefaults>>>
  : never;
export type GameAnalysisImportRequest = WithOptionalImportDefaults<GeneratedImportRequest>;
export type GameAnalysisImportResponse = Schemas["GameAnalysisImportResponse"];
export type GameMainlineMove = Schemas["GameMainlineMove"];
export type GameAnalysisGame = Schemas["GameAnalysisGame"];
export type ExplanationSegment = Schemas["ExplanationSegment"];
export type ExplanationLineCard = Schemas["ExplanationLineCard"];
export type BookLineMove = Schemas["BookLineMove"];
export type BookLine = Schemas["BookLine"];
export type OpeningBookMetadata = Schemas["OpeningBookMetadata"];
export type GameMoveAnalysis = Schemas["GameMoveAnalysis"];
export type GameAnalysisSnapshot = Schemas["GameAnalysisSnapshot"];
