import type { ImportPanelStatus } from "../components/analysis/AnalysisImportPanel";
import type { ImportedGameMetadata } from "../types/api";

export const HOME_DOCUMENT_TITLE = "Chess: g6 Analysis";
export const GAME_TITLE_SUFFIX = "Chess: g6 Analysis";
export const ANONYMOUS_PLAYER_LABEL = "Anonymous";

const TITLE_SEPARATOR = " · ";

export interface DocumentTitleInput {
  source: ImportedGameMetadata | null;
  importStatus: ImportPanelStatus;
}

export function buildDocumentTitle({ source, importStatus }: DocumentTitleInput): string {
  if (source === null) {
    return importStatus === "idle" ? HOME_DOCUMENT_TITLE : GAME_TITLE_SUFFIX;
  }

  const white = normalizeNickname(source.white_username);
  const black = normalizeNickname(source.black_username);

  if (white === null && black === null) {
    return GAME_TITLE_SUFFIX;
  }

  const matchup = `${white ?? ANONYMOUS_PLAYER_LABEL} vs ${black ?? ANONYMOUS_PLAYER_LABEL}`;
  return `${matchup}${TITLE_SEPARATOR}${GAME_TITLE_SUFFIX}`;
}

function normalizeNickname(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}
