import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisMoveMarker, GameMove } from "../../types/analysis";
import { MoveList } from "./MoveList";

const formatClockProbe = vi.hoisted(() => ({
  calls: 0,
  reset() {
    this.calls = 0;
  },
}));

vi.mock("../../lib/chess", async () => {
  const actual = await vi.importActual<typeof import("../../lib/chess")>("../../lib/chess");
  return {
    ...actual,
    formatClock: vi.fn((seconds: number) => {
      formatClockProbe.calls += 1;
      return `${seconds}s`;
    }),
  };
});

describe("MoveList", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    formatClockProbe.reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("keeps move-cell work scoped when the selected ply changes", () => {
    const moves = buildMoves(40);
    const moveMarkers: AnalysisMoveMarker[] = [];
    const onSelectPly = vi.fn();

    const view = render(
      <MoveList currentPly={1} moveMarkers={moveMarkers} moves={moves} onSelectPly={onSelectPly} />,
    );

    expect(formatClockProbe.calls).toBe(40);

    formatClockProbe.reset();
    view.rerender(
      <MoveList currentPly={2} moveMarkers={moveMarkers} moves={moves} onSelectPly={onSelectPly} />,
    );

    expect(formatClockProbe.calls).toBeLessThanOrEqual(2);
  });
});

function buildMoves(count: number): GameMove[] {
  return Array.from({ length: count }, (_, index) => {
    const ply = index + 1;
    return {
      ply,
      move_number: Math.ceil(ply / 2),
      side: ply % 2 === 1 ? "white" : "black",
      san: `M${ply}`,
      uci: `m${ply}`,
      fen_before: `before ${ply}`,
      fen_after: `after ${ply}`,
      remaining_clock_seconds: 600 - ply,
    };
  });
}
