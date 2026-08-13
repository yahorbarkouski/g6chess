"""Export the reviewed FastAPI contract without constructing runtime providers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from g6explanation.api.app import ApiProtectionBoundary, create_app
from g6explanation.game_analysis import GameAnalysisService
from g6explanation.game_imports import GameImportService

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPOSITORY_ROOT / "contracts/openapi.json"


def main() -> None:
    inert_dependency = object()
    application = create_app(
        game_analysis_service=cast(GameAnalysisService, inert_dependency),
        game_import_service=cast(GameImportService, inert_dependency),
        api_protection=cast(ApiProtectionBoundary, inert_dependency),
    )
    document = application.openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
