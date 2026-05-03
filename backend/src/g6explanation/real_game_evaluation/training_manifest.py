"""Training-data manifest gates for verified real explanation eval records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import Field

from g6explanation.context_engine.contracts import ContextContract, LLMContext
from g6explanation.real_game_evaluation.explanation_evaluation import (
    RealExplanationEvalRecord,
)
from g6explanation.real_game_evaluation.source_rights import ExplanationDataSource

TRAINING_DATA_MANIFEST_VERSION = "training_data_manifest.v1"


class TrainingDataManifestEntry(ContextContract):
    case_id: str
    tags: list[str]
    source: ExplanationDataSource
    provider_name: str
    model: str
    schema_version: str
    context_version: str
    prompt_id: str
    prompt_version: str
    verifier_version: str
    quality: str
    llm_context: LLMContext
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
        assert record.source is not None
        assert record.llm_context is not None
        assert record.schema_version is not None
        assert record.context_version is not None
        assert record.prompt_id is not None
        assert record.prompt_version is not None
        assert record.verifier_version is not None
        entries.append(
            TrainingDataManifestEntry(
                case_id=record.case_id,
                tags=record.tags,
                source=record.source,
                provider_name=record.provider_name or "",
                model=record.model or "",
                schema_version=record.schema_version,
                context_version=record.context_version,
                prompt_id=record.prompt_id,
                prompt_version=record.prompt_version,
                verifier_version=record.verifier_version,
                quality=record.quality or "",
                llm_context=record.llm_context,
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
    if record.source is None:
        return "missing_source_rights"
    if not record.source.allows_global_training:
        return "source_rights_do_not_allow_training"
    if record.llm_context is None:
        return "missing_llm_context"
    if not record.explanation:
        return "missing_explanation"
    if record.provider_name is None or record.model is None:
        return "missing_model_metadata"
    if (
        record.schema_version is None
        or record.context_version is None
        or record.prompt_id is None
        or record.prompt_version is None
        or record.verifier_version is None
    ):
        return "missing_generation_metadata"
    if record.stockfish_depth is None or record.stockfish_depth < 16:
        return "insufficient_stockfish_depth"
    return None
