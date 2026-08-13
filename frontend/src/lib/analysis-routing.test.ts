import { describe, expect, it } from "vitest";
import {
  extractGameImportTarget,
  extractLichessGameId,
  normalizeGameImportUrl,
  parseAnalysisRoute,
} from "./analysis-routing";

describe("analysis routing", () => {
  it("parses legacy production-domain Chess.com game routes as live imports", () => {
    expect(parseAnalysisRoute("/game/168319028894")).toEqual({
      kind: "chess_com_live",
      externalSource: "chess_com_live_url",
      externalGameId: "168319028894",
      boardOrientation: null,
      analysisId: null,
      ply: null,
      canonicalPath: "/game/live/168319028894",
    });
    expect(extractGameImportTarget("https://www.g6chess.com/game/168319028894")).toEqual({
      source: "chess_com_live_url",
      externalGameId: "168319028894",
      boardOrientation: null,
    });
    expect(normalizeGameImportUrl("https://www.g6chess.com/game/168319028894")).toBe(
      "https://www.chess.com/game/live/168319028894",
    );
  });

  it("parses Lichess game URLs and normalizes to the canonical import URL", () => {
    expect(extractLichessGameId("https://lichess.org/fY44h4OY/black#56")).toBe("fY44h4OY");
    expect(extractLichessGameId("https://lichess.org/game/export/fY44h4OY")).toBe("fY44h4OY");
    expect(extractLichessGameId("https://lichess.org/fY44h4OYabcd")).toBe("fY44h4OY");
    expect(normalizeGameImportUrl("https://lichess.org/fY44h4OY/black#56")).toBe(
      "https://lichess.org/fY44h4OY",
    );
    expect(normalizeGameImportUrl("https://lichess.org/fY44h4OYabcd/black#56")).toBe(
      "https://lichess.org/fY44h4OY",
    );
    expect(extractGameImportTarget("https://lichess.org/fY44h4OY")).toEqual({
      source: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: null,
    });
  });

  it("preserves explicit Lichess board orientation hints", () => {
    expect(extractGameImportTarget("https://lichess.org/fY44h4OY/black#56")).toEqual({
      source: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: "black",
    });
    expect(normalizeGameImportUrl("https://lichess.org/fY44h4OY/black#56")).toBe(
      "https://lichess.org/fY44h4OY",
    );
    expect(parseAnalysisRoute("/lichess/fY44h4OY/black", "?analysis=analysis-1")).toEqual({
      kind: "lichess_game",
      externalSource: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: "black",
      analysisId: "analysis-1",
      ply: null,
      canonicalPath: "/lichess/fY44h4OY/black?analysis=analysis-1",
    });
  });

  it("parses shareable Lichess routes", () => {
    expect(parseAnalysisRoute("/lichess/fY44h4OY", "?analysis=analysis-1&ply=3")).toEqual({
      kind: "lichess_game",
      externalSource: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: null,
      analysisId: "analysis-1",
      ply: 3,
      canonicalPath: "/lichess/fY44h4OY?analysis=analysis-1&ply=3",
    });
  });

  it("normalizes 12-character Lichess route IDs to the 8-character game ID", () => {
    expect(parseAnalysisRoute("/lichess/fY44h4OYabcd/black", "?analysis=analysis-1")).toEqual({
      kind: "lichess_game",
      externalSource: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: "black",
      analysisId: "analysis-1",
      ply: null,
      canonicalPath: "/lichess/fY44h4OY/black?analysis=analysis-1",
    });
    expect(extractGameImportTarget("https://www.g6chess.com/lichess/fY44h4OYabcd")).toEqual({
      source: "lichess_game_url",
      externalGameId: "fY44h4OY",
      boardOrientation: null,
    });
  });

  it("parses Lichess study chapter URLs and normalizes to the canonical chapter URL", () => {
    expect(extractGameImportTarget("https://lichess.org/study/ybdiAVdQ/2pHkbFS9")).toEqual({
      source: "lichess_study_chapter_url",
      externalGameId: "ybdiAVdQ/2pHkbFS9",
      boardOrientation: null,
    });
    expect(normalizeGameImportUrl("https://lichess.org/study/ybdiAVdQ/2pHkbFS9#12")).toBe(
      "https://lichess.org/study/ybdiAVdQ/2pHkbFS9",
    );
    expect(
      extractGameImportTarget("https://www.g6chess.com/lichess/study/ybdiAVdQ/2pHkbFS9"),
    ).toEqual({
      source: "lichess_study_chapter_url",
      externalGameId: "ybdiAVdQ/2pHkbFS9",
      boardOrientation: null,
    });
  });

  it("parses shareable Lichess study chapter routes", () => {
    expect(
      parseAnalysisRoute("/lichess/study/ybdiAVdQ/2pHkbFS9", "?analysis=analysis-1&ply=3"),
    ).toEqual({
      kind: "lichess_study_chapter",
      externalSource: "lichess_study_chapter_url",
      externalGameId: "ybdiAVdQ/2pHkbFS9",
      boardOrientation: null,
      analysisId: "analysis-1",
      ply: 3,
      canonicalPath: "/lichess/study/ybdiAVdQ/2pHkbFS9?analysis=analysis-1&ply=3",
    });
  });
});
