import { describe, expect, it } from "vitest";
import { MOCK_ANALYSIS } from "../../data/mock-analysis";
import {
  browserAnalysisReasonForPosition,
  buildAnalysisIndexes,
  buildPreAnalysisFens,
  selectDisplayedEngineLines,
} from "./AnalysisWorkspace";

describe("buildPreAnalysisFens", () => {
  it("keeps pre-analysis capped, unique, and centered on the current position", () => {
    const indexes = buildAnalysisIndexes(MOCK_ANALYSIS);
    const currentPly = 25;
    const currentFen = indexes.moveByPly.get(currentPly)?.fen_after ?? "";

    const fens = buildPreAnalysisFens(MOCK_ANALYSIS, indexes, currentPly, currentFen);

    expect(fens.length).toBeLessThanOrEqual(12);
    expect(new Set(fens).size).toBe(fens.length);
    expect(fens[0]).toBe(currentFen);
    expect(fens).toContain(indexes.moveByPly.get(currentPly + 1)?.fen_after);
    expect(fens).toContain(indexes.moveByPly.get(currentPly - 1)?.fen_after);
  });

  it("prioritizes nearby marked moves after the current-neighbor window", () => {
    const indexes = buildAnalysisIndexes(MOCK_ANALYSIS);
    const currentPly = 25;
    const currentFen = indexes.moveByPly.get(currentPly)?.fen_after ?? "";

    const fens = buildPreAnalysisFens(MOCK_ANALYSIS, indexes, currentPly, currentFen);
    const markedPlyBeforeFen = indexes.moveByPly.get(28)?.fen_before;

    expect(markedPlyBeforeFen).toBeDefined();
    expect(fens).toContain(markedPlyBeforeFen);
  });
});

describe("browserAnalysisReasonForPosition", () => {
  const serverEngineLines = {
    fen: "server fen",
    lines: [
      {
        san: "e4",
        uci: "e2e4",
        eval_cp: 30,
        pv_san: ["e4"],
        pv_uci: ["e2e4"],
      },
    ],
  };

  it("does not run browser Stockfish for backend-covered mainline positions", () => {
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "mainline fen",
        discoveryActive: false,
        previewActive: false,
        serverEngineLines,
      }),
    ).toBeNull();
  });

  it("runs browser Stockfish for local discovery, preview, and missing server data", () => {
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "discovery fen",
        discoveryActive: true,
        previewActive: false,
        serverEngineLines,
      }),
    ).toBe("discovery");
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "preview fen",
        discoveryActive: false,
        previewActive: true,
        serverEngineLines,
      }),
    ).toBe("preview");
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "mainline fen",
        discoveryActive: false,
        previewActive: false,
        serverEngineLines: null,
      }),
    ).toBe("missing-server-lines");
  });

  it("runs browser Stockfish for the current position while backend analysis is loading", () => {
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "loading fen",
        discoveryActive: false,
        loadingActive: true,
        previewActive: false,
        serverEngineLines: null,
      }),
    ).toBe("loading");
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "server-backed loading fen",
        discoveryActive: false,
        loadingActive: true,
        previewActive: false,
        serverEngineLines,
      }),
    ).toBeNull();
  });

  it("can suppress missing-server fallback for backend book-line panels", () => {
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "book fen",
        discoveryActive: false,
        loadingActive: true,
        previewActive: false,
        serverEngineLines: null,
        suppressMissingServerLines: true,
      }),
    ).toBeNull();
    expect(
      browserAnalysisReasonForPosition({
        analysisFen: "book discovery fen",
        discoveryActive: true,
        loadingActive: true,
        previewActive: false,
        serverEngineLines: null,
        suppressMissingServerLines: true,
      }),
    ).toBe("discovery");
  });
});

describe("selectDisplayedEngineLines", () => {
  const serverEngineLines = engineLineSet("server fen", "e4", "e2e4");
  const browserEngineLines = engineLineSet("preview fen", "Nf3", "g1f3");

  it("keeps server-backed lines stable outside discovery even when browser lines are available", () => {
    expect(
      selectDisplayedEngineLines({
        browserEngineLines,
        discoveryActive: false,
        serverEngineLines,
      }),
    ).toBe(serverEngineLines);
  });

  it("uses browser lines for discovery and as a fallback when server lines are missing", () => {
    expect(
      selectDisplayedEngineLines({
        browserEngineLines,
        discoveryActive: true,
        serverEngineLines,
      }),
    ).toBe(browserEngineLines);
    expect(
      selectDisplayedEngineLines({
        browserEngineLines,
        discoveryActive: false,
        serverEngineLines: null,
      }),
    ).toBe(browserEngineLines);
  });
});

function engineLineSet(fen: string, san: string, uci: string) {
  return {
    fen,
    lines: [
      {
        san,
        uci,
        eval_cp: 30,
        pv_san: [san],
        pv_uci: [uci],
      },
    ],
  };
}
