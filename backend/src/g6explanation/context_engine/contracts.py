"""Schema contracts for the move context engine."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ColorName: TypeAlias = Literal["white", "black"]
PlayerLevelKind: TypeAlias = Literal["rating", "label"]
ScoreKind: TypeAlias = Literal["cp", "mate"]
MoveQualityLabel: TypeAlias = Literal[
    "best",
    "excellent",
    "good",
    "neutral",
    "inaccuracy",
    "mistake",
    "blunder",
    "missed_win",
]
FindabilityLabel: TypeAlias = Literal[
    "obvious",
    "findable",
    "hard",
    "very_hard",
    "engine_like",
    "unknown",
]
CandidateRole: TypeAlias = Literal[
    "played_move",
    "engine_best",
    "close_engine_alternative",
    "practical_alternative",
    "human_common_move",
    "best_reply_after_played",
    "only_saving_move",
    "only_winning_move",
    "tablebase_exact_move",
]
PracticalityCategory: TypeAlias = Literal[
    "clear_recommendation",
    "practical_try",
    "hard_but_important",
    "engine_benchmark",
    "only_move",
    "unknown_practicality",
]
RecommendationPolicy: TypeAlias = Literal[
    "recommend_directly",
    "mention_with_caveat",
    "use_as_practical_alternative",
    "explain_as_hidden_resource",
    "do_not_recommend",
]
SignificanceLabel: TypeAlias = Literal["low", "moderate", "high", "critical"]
BeautyLabel: TypeAlias = Literal["low", "notable", "beautiful", "brilliant"]
TimeSituation: TypeAlias = Literal[
    "unknown",
    "classical_or_no_pressure",
    "rapid_normal",
    "blitz_normal",
    "low_time",
    "time_scramble",
]
AnalysisBudgetKind: TypeAlias = Literal["depth", "nodes", "static"]
EngineOptionValue: TypeAlias = int | str | bool | None


class ContextContract(BaseModel):
    """Base model for frozen, versioned context contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        return cls.model_json_schema()


class PlayerLevel(ContextContract):
    kind: PlayerLevelKind
    value: int | str
    system: str | None = None

    @classmethod
    def rating(cls, value: int, system: str | None = None) -> PlayerLevel:
        return cls(kind="rating", value=value, system=system)

    @classmethod
    def label_value(cls, value: str, system: str | None = None) -> PlayerLevel:
        return cls(kind="label", value=value, system=system)

    @model_validator(mode="after")
    def _validate_level_shape(self) -> PlayerLevel:
        if self.kind == "rating" and not isinstance(self.value, int):
            raise ValueError("Rating player levels require an integer value.")
        if self.kind == "label" and not isinstance(self.value, str):
            raise ValueError("Label player levels require a string value.")
        return self

    def label(self) -> str:
        if self.kind == "rating":
            suffix = f" {self.system}" if self.system else ""
            return f"{self.value}{suffix}"
        return str(self.value)

    def rating_value(self) -> int | None:
        if self.kind == "rating" and isinstance(self.value, int):
            return self.value
        return None


class MoveContextRequest(ContextContract):
    player_color: ColorName
    player_level: PlayerLevel
    played_move: str | None = None
    fen_before: str | None = None
    pgn: str | None = None
    ply: int | None = None
    time_control: str | None = None
    clock_before_seconds: float | None = None
    increment_seconds: float | None = None
    opponent_level: PlayerLevel | None = None


class Score(ContextContract):
    kind: ScoreKind
    value: int | None = None
    mate_in: int | None = None
    mate_for: Literal["player", "opponent"] | None = None

    @classmethod
    def cp(cls, value: int) -> Score:
        return cls(kind="cp", value=value)

    @classmethod
    def mate(cls, mate_in: int, mate_for: Literal["player", "opponent"]) -> Score:
        return cls(kind="mate", mate_in=mate_in, mate_for=mate_for)

    @model_validator(mode="after")
    def _validate_score_shape(self) -> Score:
        if self.kind == "cp":
            if self.value is None:
                raise ValueError("Centipawn scores require value.")
            if self.mate_in is not None or self.mate_for is not None:
                raise ValueError("Centipawn scores cannot include mate fields.")
        if self.kind == "mate":
            if self.value is not None:
                raise ValueError("Mate scores cannot include centipawn value.")
            if self.mate_in is None or self.mate_for is None:
                raise ValueError("Mate scores require mate_in and mate_for.")
            if self.mate_in < 0:
                raise ValueError("mate_in must be non-negative.")
        return self


class Wdl(ContextContract):
    win: int
    draw: int
    loss: int


class PlayedMoveFacts(ContextContract):
    uci: str
    san: str
    legal: bool
    is_check: bool
    is_capture: bool
    promotion: str | None = None


class PositionContext(ContextContract):
    fen_before: str
    fen_after: str
    side_to_move: ColorName
    move_number: int
    ply: int
    phase: str
    legal_moves_uci: list[str] = Field(default_factory=list[str])


class ReconstructedMoveContext(ContextContract):
    position: PositionContext
    played: PlayedMoveFacts


class EngineAnalysisBudget(ContextContract):
    kind: AnalysisBudgetKind
    value: int | str | None
    multipv: int | None = None


class EngineLine(ContextContract):
    move_uci: str
    move_san: str
    score: Score
    rank: int | None = None
    wdl: Wdl | None = None
    pv_uci: list[str] = Field(default_factory=list[str])
    pv_san: list[str] = Field(default_factory=list[str])
    depth: int | None = None
    seldepth: int | None = None
    nodes: int | None = None
    nps: int | None = None
    tbhits: int | None = None


class EngineAnalysis(ContextContract):
    engine_version: str
    analysis_budget: EngineAnalysisBudget
    engine_options: dict[str, EngineOptionValue] = Field(default_factory=dict)
    top_lines: list[EngineLine] = Field(default_factory=list[EngineLine])
    played_line: EngineLine
    after_line: EngineLine | None = None

    @field_validator("top_lines")
    @classmethod
    def _top_lines_not_empty(cls, value: list[EngineLine]) -> list[EngineLine]:
        if not value:
            raise ValueError("EngineAnalysis requires at least one top line.")
        return value


class HumanMoveLikelihood(ContextContract):
    player_level_probability: float | None = None
    plus_400_probability: float | None = None
    evidence_source: str | None = None
    model_type: str | None = None
    model_version: str | None = None
    rank: int | None = None
    is_top_human_move: bool = False

    @field_validator("player_level_probability", "plus_400_probability")
    @classmethod
    def _probability_in_range(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("Move probabilities must be between 0 and 1.")
        return value


class MoveQuality(ContextContract):
    label: MoveQualityLabel
    score_delta_cp_player_pov: int | None
    score_loss_vs_best_cp: int | None
    wdl_delta_player_pov: Wdl | None = None
    wdl_expected_score_loss: int | None = None
    severity_text: str


class MoveSignificance(ContextContract):
    label: SignificanceLabel
    score: float = Field(ge=0, le=1)


class MoveBeauty(ContextContract):
    label: BeautyLabel
    score: float = Field(ge=0, le=1)


class CandidateMove(ContextContract):
    san: str
    uci: str
    roles: list[CandidateRole] = Field(default_factory=list[CandidateRole])
    engine_rank: int | None
    human_rank: int | None = None
    score: Score
    score_loss_vs_best_cp: int | None
    wdl: Wdl | None = None
    pv_short_san: list[str] = Field(default_factory=list[str])
    player_level_probability: float | None
    plus_400_probability: float | None
    time_adjusted_findability: FindabilityLabel
    findability_source: str
    findability_confidence: str
    teachable_skill_gap: bool
    practicality: PracticalityCategory
    recommendation_policy: RecommendationPolicy


class MainPoint(ContextContract):
    concept: str
    claim: str


class KeyMoveContext(ContextContract):
    move: str
    practicality: PracticalityCategory
    findability: FindabilityLabel
    reason: str
    recommendation_policy: RecommendationPolicy


class EvidencePacket(ContextContract):
    context_version: str
    request: MoveContextRequest
    position: PositionContext
    played: PlayedMoveFacts
    engine: EngineAnalysis
    quality: MoveQuality
    significance: MoveSignificance
    beauty: MoveBeauty
    candidates: list[CandidateMove] = Field(default_factory=list[CandidateMove])
    main_point: MainPoint
    allowed_claims: list[str] = Field(default_factory=list[str])


class LLMContext(ContextContract):
    played: str
    quality: MoveQualityLabel
    significance: MoveSignificance
    beauty: MoveBeauty
    player_level: str
    time_situation: TimeSituation
    severity: str
    main_point: str
    best_or_key_move: KeyMoveContext | None
    human_note: str | None
    allowed_claims: list[str] = Field(default_factory=list[str])


class VerificationResult(ContextContract):
    verifier_version: str
    passed: bool
    failures: list[str] = Field(default_factory=list[str])
    warnings: list[str] = Field(default_factory=list[str])


class ContextResult(ContextContract):
    evidence: EvidencePacket
    llm_context: LLMContext
