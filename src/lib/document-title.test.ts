import { describe, expect, it } from "vitest";
import type { ImportedGameMetadata } from "../types/api";
import { buildDocumentTitle, GAME_TITLE_SUFFIX, HOME_DOCUMENT_TITLE } from "./document-title";

function source(overrides: Partial<ImportedGameMetadata> = {}): ImportedGameMetadata {
  return {
    source: "chess_com_live_url",
    source_url: "https://www.chess.com/game/live/168193636078",
    external_game_id: "168193636078",
    title: "Chess.com game 168193636078",
    white_username: null,
    black_username: null,
    white_rating: null,
    black_rating: null,
    time_control: null,
    result: null,
    allows_global_training: false,
    rights_basis: "Public Chess.com game link.",
    ...overrides,
  };
}

describe("buildDocumentTitle", () => {
  it("returns the home title when nothing is loaded", () => {
    expect(buildDocumentTitle({ source: null, importStatus: "idle" })).toBe(HOME_DOCUMENT_TITLE);
  });

  it("returns the generic game title while an import is in flight", () => {
    expect(buildDocumentTitle({ source: null, importStatus: "submitting" })).toBe(
      GAME_TITLE_SUFFIX,
    );
    expect(buildDocumentTitle({ source: null, importStatus: "polling" })).toBe(GAME_TITLE_SUFFIX);
  });

  it("returns the generic game title when the source has no nicknames", () => {
    expect(
      buildDocumentTitle({
        source: source({ white_username: null, black_username: "   " }),
        importStatus: "polling",
      }),
    ).toBe(GAME_TITLE_SUFFIX);
  });

  it("formats both nicknames with the g6 suffix", () => {
    expect(
      buildDocumentTitle({
        source: source({ white_username: "Magnus", black_username: "Hikaru" }),
        importStatus: "succeeded",
      }),
    ).toBe("Magnus vs Hikaru · g6 Chess Analysis");
  });

  it("falls back to Anonymous for missing slots", () => {
    expect(
      buildDocumentTitle({
        source: source({ white_username: null, black_username: "Hikaru" }),
        importStatus: "succeeded",
      }),
    ).toBe("Anonymous vs Hikaru · g6 Chess Analysis");
    expect(
      buildDocumentTitle({
        source: source({ white_username: "Magnus", black_username: "" }),
        importStatus: "succeeded",
      }),
    ).toBe("Magnus vs Anonymous · g6 Chess Analysis");
  });

  it("trims whitespace from nicknames", () => {
    expect(
      buildDocumentTitle({
        source: source({ white_username: "  Magnus  ", black_username: " Hikaru " }),
        importStatus: "succeeded",
      }),
    ).toBe("Magnus vs Hikaru · g6 Chess Analysis");
  });
});
