"""Training-data manifest gates for verified real explanation eval records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import Field

from g6explanation.context_engine.contracts import ContextContract
from g6explanation.real_game_evaluation.explanation_evaluation import (
    RealExplanationEvalRecord,
)

TRAINING_DATA_MANIFEST_VERSION = "training_data_manifest.v1"


class TrainingDataManifestEntry(ContextContract):
    case_id: str
    tags: list[str]
    provider_name: str
    model: str
    quality: str
    explanation: str


class TrainingDataManifest(ContextContract):
    manifest_version: str = TRAINING_DATA_MANIFEST_VERSION
    source_record_count: int
    entry_count: int
    excluded_counts: dict[str, int] = Field(default_factory=dict[str, int])
    entries: list[TrainingDataManifestEntry] = Field(
        default_factory=list[TrainingDataManifestEntry]
    )


def build_training_data_manifest(
    records: Sequence[RealExplanationEvalRecord],
) -> TrainingDataManifest:
    """Build a conservative manifest for reviewed, verified explanations."""

    entries: list[TrainingDataManifestEntry] = []
    excluded: Counter[str] = Counter()
    for record in records:
        reason = _training_exclusion_reason(record)
        if reason is not None:
            excluded[reason] += 1
            continue
        entries.append(
            TrainingDataManifestEntry(
                case_id=record.case_id,
                tags=record.tags,
                provider_name=record.provider_name or "",
                model=record.model or "",
                quality=record.quality or "",
                explanation=record.explanation or "",
            )
        )
    return TrainingDataManifest(
        source_record_count=len(records),
        entry_count=len(entries),
        excluded_counts=dict(sorted(excluded.items())),
        entries=entries,
    )


def _training_exclusion_reason(record: RealExplanationEvalRecord) -> str | None:
    if record.manual_review_category != "accepted":
        return "not_manually_accepted"
    if not record.passed:
        return "not_passed"
    if record.used_fallback is not False:
        return "fallback_or_unknown_finish"
    if record.error is not None:
        return "has_error"
    if not record.explanation:
        return "missing_explanation"
    if record.provider_name is None or record.model is None:
        return "missing_model_metadata"
    if record.stockfish_depth is None or record.stockfish_depth < 16:
        return "insufficient_stockfish_depth"
    return None
