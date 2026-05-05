import { describe, expect, it } from "vitest";
import { MOCK_ANALYSIS } from "../../data/mock-analysis";
import {
  browserAnalysisReasonForPosition,
  buildAnalysisIndexes,
  buildPreAnalysisFens,
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
});
