import { cleanup, render, screen } from "@testing-library/react";
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
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 1;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
    formatClockProbe.reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
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

  it("only scrolls the selected move when it is outside the visible move list", () => {
    const moves = buildMoves(4);
    const moveMarkers: AnalysisMoveMarker[] = [];
    const onSelectPly = vi.fn();

    const view = render(
      <MoveList currentPly={1} moveMarkers={moveMarkers} moves={moves} onSelectPly={onSelectPly} />,
    );

    const scrollIntoView = vi.mocked(Element.prototype.scrollIntoView);
    scrollIntoView.mockClear();

    const visibleMove = screen.getByRole("button", { name: /1\.\.\. M2/ });
    const scrollContainer = visibleMove.closest(".overflow-auto");
    if (!(scrollContainer instanceof HTMLElement)) {
      throw new Error("Expected move list scroll container.");
    }
    setScrollMetrics(scrollContainer, { clientHeight: 100, scrollHeight: 200 });
    setRect(scrollContainer, { top: 0, bottom: 100 });
    setRect(visibleMove, { top: 32, bottom: 60 });

    view.rerender(
      <MoveList currentPly={2} moveMarkers={moveMarkers} moves={moves} onSelectPly={onSelectPly} />,
    );

    expect(scrollIntoView).not.toHaveBeenCalled();

    const hiddenMove = screen.getByRole("button", { name: /2\. M3/ });
    setRect(hiddenMove, { top: 120, bottom: 148 });

    view.rerender(
      <MoveList currentPly={3} moveMarkers={moveMarkers} moves={moves} onSelectPly={onSelectPly} />,
    );

    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
  });
});

function setScrollMetrics(
  element: HTMLElement,
  metrics: { clientHeight: number; scrollHeight: number },
): void {
  Object.defineProperties(element, {
    clientHeight: { configurable: true, value: metrics.clientHeight },
    scrollHeight: { configurable: true, value: metrics.scrollHeight },
  });
}

function setRect(element: Element, rect: Pick<DOMRect, "bottom" | "top">): void {
  element.getBoundingClientRect = vi.fn(
    () =>
      ({
        bottom: rect.bottom,
        height: rect.bottom - rect.top,
        left: 0,
        right: 100,
        top: rect.top,
        width: 100,
        x: 0,
        y: rect.top,
        toJSON: () => ({}),
      }) as DOMRect,
  );
}

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
