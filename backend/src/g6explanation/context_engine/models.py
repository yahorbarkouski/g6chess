"""Data contracts for the move context engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ColorName = Literal["white", "black"]
ScoreKind = Literal["cp", "mate"]


@dataclass(frozen=True)
class PlayerLevel:
    kind: str
    value: int | str
    system: str | None = None

    @classmethod
    def rating(cls, value: int, system: str | None = None) -> PlayerLevel:
        return cls(kind="rating", value=value, system=system)

    def label(self) -> str:
        if self.kind == "rating":
            suffix = f" {self.system}" if self.system else ""
            return f"{self.value}{suffix}"
        return str(self.value)


@dataclass(frozen=True)
class MoveContextRequest:
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


@dataclass(frozen=True)
class Score:
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


@dataclass(frozen=True)
class Wdl:
    win: int
    draw: int
    loss: int


@dataclass(frozen=True)
class MoveFacts:
    uci: str
    san: str
    legal: bool
    is_check: bool
    is_capture: bool
    promotion: str | None = None


@dataclass(frozen=True)
class PositionContext:
    fen_before: str
    fen_after: str
    side_to_move: ColorName
    move_number: int
    ply: int
    phase: str
    legal_moves_uci: list[str]


@dataclass(frozen=True)
class BoardContext:
    position: PositionContext
    played: MoveFacts


@dataclass(frozen=True)
class EngineLine:
    move_uci: str
    move_san: str
    score: Score
    rank: int | None = None
    wdl: Wdl | None = None
    pv_uci: list[str] | None = None
    pv_san: list[str] | None = None


@dataclass(frozen=True)
class EngineAnalysis:
    engine_version: str
    analysis_budget: dict[str, int | str]
    top_lines: list[EngineLine]
    played_line: EngineLine
    after_line: EngineLine | None = None


@dataclass(frozen=True)
class HumanMoveStats:
    player_level_probability: float | None = None
    plus_400_probability: float | None = None
    evidence_source: str | None = None


@dataclass(frozen=True)
class MoveQuality:
    label: str
    score_delta_cp_player_pov: int | None
    score_loss_vs_best_cp: int | None
    severity_text: str


@dataclass(frozen=True)
class CandidateMove:
    san: str
    uci: str
    roles: list[str]
    engine_rank: int | None
    score: Score
    score_loss_vs_best_cp: int | None
    pv_short_san: list[str]
    player_level_probability: float | None
    plus_400_probability: float | None
    time_adjusted_findability: str
    practicality: str
    recommendation_policy: str


@dataclass(frozen=True)
class MainPoint:
    concept: str
    claim: str


@dataclass(frozen=True)
class EvidencePacket:
    context_version: str
    request: MoveContextRequest
    position: PositionContext
    played: MoveFacts
    engine: EngineAnalysis
    quality: MoveQuality
    candidates: list[CandidateMove]
    main_point: MainPoint
    allowed_claims: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LLMContext:
    played: str
    quality: str
    player_level: str
    time_situation: str
    severity: str
    main_point: str
    best_or_key_move: dict[str, str] | None
    human_note: str | None
    allowed_claims: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextResult:
    evidence: EvidencePacket
    llm_context: LLMContext

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
