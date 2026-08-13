import { describe, expect, it } from "vitest";
import type { CachedAnalysis } from "./useStockfish";
import { createStockfishDisplayGate, getStockfishDisplayKey } from "./useStockfish";

const FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

describe("getStockfishDisplayKey", () => {
  it("ignores centipawn noise inside the same display bucket", () => {
    expect(getStockfishDisplayKey(FEN, analysis({ evalCp: 630 }))).toBe(
      getStockfishDisplayKey(FEN, analysis({ evalCp: 631 })),
    );
  });

  it("changes when the visible PV changes", () => {
    expect(getStockfishDisplayKey(FEN, analysis({ pv: ["e2e4", "e7e5"] }))).not.toBe(
      getStockfishDisplayKey(FEN, analysis({ pv: ["d2d4", "d7d5"] })),
    );
  });

  it("keeps mate distance exact", () => {
    expect(getStockfishDisplayKey(FEN, analysis({ evalCp: 29_700 }))).not.toBe(
      getStockfishDisplayKey(FEN, analysis({ evalCp: 29_600 })),
    );
  });
});

describe("Stockfish display publishing", () => {
  it("publishes only semantic display changes from a noisy analysis stream", () => {
    const gate = createStockfishDisplayGate();
    const published = [
      gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ evalCp: 630 }))),
      gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ evalCp: 631 }))),
      gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ evalCp: 632 }))),
      gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ pv: ["d2d4", "d7d5"] }))),
      gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ evalCp: 29_700 }))),
      gate.shouldPublish(
        getStockfishDisplayKey(
          "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
          analysis({ evalCp: 630 }),
        ),
      ),
    ];

    expect(published).toEqual([true, false, false, true, true, true]);
  });

  it("still treats depth changes as visible display changes", () => {
    const gate = createStockfishDisplayGate();

    expect(gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ depth: 18 })))).toBe(true);
    expect(gate.shouldPublish(getStockfishDisplayKey(FEN, analysis({ depth: 19 })))).toBe(true);
  });

  it("can force-publish cached state when the user navigates to a position", () => {
    const gate = createStockfishDisplayGate();
    const displayKey = getStockfishDisplayKey(FEN, analysis({ evalCp: 630 }));

    expect(gate.shouldPublish(displayKey)).toBe(true);
    expect(gate.shouldPublish(displayKey)).toBe(false);
    expect(gate.shouldPublish(displayKey, { force: true })).toBe(true);
  });
});

function analysis({
  evalCp = 630,
  depth = 18,
  pv = ["e2e4", "e7e5", "g1f3"],
}: {
  evalCp?: number;
  depth?: number;
  pv?: string[];
}): CachedAnalysis {
  return {
    depth,
    evalCp,
    lines: [
      {
        san: "e4",
        uci: pv[0] ?? "e2e4",
        eval_cp: evalCp,
        pv_san: ["e4", "e5", "Nf3"],
        pv_uci: pv,
      },
    ],
  };
}
