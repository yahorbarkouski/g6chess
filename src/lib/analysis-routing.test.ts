import { describe, expect, it } from "vitest";
import {
  extractGameImportTarget,
  extractLichessGameId,
  normalizeGameImportUrl,
  parseAnalysisRoute,
} from "./analysis-routing";

describe("analysis routing", () => {
  it("parses Lichess game URLs and normalizes to the canonical import URL", () => {
    expect(extractLichessGameId("https://lichess.org/fY44h4OY/black#56")).toBe("fY44h4OY");
    expect(extractLichessGameId("https://lichess.org/game/export/fY44h4OY")).toBe("fY44h4OY");
    expect(normalizeGameImportUrl("https://lichess.org/fY44h4OY/black#56")).toBe(
      "https://lichess.org/fY44h4OY",
    );
    expect(extractGameImportTarget("https://lichess.org/fY44h4OY")).toEqual({
      source: "lichess_game_url",
      externalGameId: "fY44h4OY",
    });
  });

  it("parses shareable Lichess routes", () => {
    expect(parseAnalysisRoute("/lichess/fY44h4OY", "?analysis=analysis-1&ply=3")).toEqual({
      kind: "lichess_game",
      externalSource: "lichess_game_url",
      externalGameId: "fY44h4OY",
      analysisId: "analysis-1",
      ply: 3,
      canonicalPath: "/lichess/fY44h4OY?analysis=analysis-1&ply=3",
    });
  });
});
