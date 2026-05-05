import { describe, expect, it } from "vitest";
import { MOCK_ANALYSIS } from "../../data/mock-analysis";
import { buildAnalysisIndexes, buildPreAnalysisFens } from "./AnalysisWorkspace";

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
