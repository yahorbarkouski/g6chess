from __future__ import annotations

from g6explanation.context_engine.candidate_moves.recommendation import (
    practicality,
    recommendation_policy,
)


def test_hard_engine_best_is_caveated_instead_of_recommended_directly() -> None:
    candidate_practicality = practicality(["engine_best"], 0, "engine_like")

    assert candidate_practicality == "hard_but_important"
    assert recommendation_policy(candidate_practicality, "engine_like", False) == (
        "explain_as_hidden_resource"
    )


def test_close_findable_alternative_is_practical_try() -> None:
    candidate_practicality = practicality(["close_engine_alternative"], 35, "findable")

    assert candidate_practicality == "practical_try"
    assert recommendation_policy(candidate_practicality, "findable", False) == (
        "use_as_practical_alternative"
    )
