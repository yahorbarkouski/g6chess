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

  it("renders brilliant moves like great moves but with a purple double-exclamation badge", () => {
    const moves = buildMoves(2);
    const onSelectPly = vi.fn();

    render(
      <MoveList
        currentPly={1}
        moveMarkers={[buildMarker({ ply: 1, primary_class: "brilliant" })]}
        moves={moves}
        onSelectPly={onSelectPly}
      />,
    );

    expect(screen.getByText("!!")).toHaveClass("bg-purple-600", "text-white", "size-3.5");
    expect(screen.getByRole("button", { name: /1\. M1 Brilliant/ })).toHaveClass("bg-stone-100");
  });

  it("filters out non-critical markers when markerDisplayMode is critical", () => {
    const moves = buildMoves(2);
    const onSelectPly = vi.fn();

    const bookMarker = buildMarker({ ply: 1, primary_class: "book" });
    bookMarker.label_metadata.requires_explanation = false;

    const blunderMarker = buildMarker({ ply: 2, primary_class: "blunder" });
    blunderMarker.label_metadata.requires_explanation = true;

    const { rerender } = render(
      <MoveList
        currentPly={1}
        markerDisplayMode="critical"
        moveMarkers={[bookMarker, blunderMarker]}
        moves={moves}
        onSelectPly={onSelectPly}
      />,
    );

    // Book marker (non-critical) should not show its description or badge in critical display mode
    expect(screen.getByRole("button", { name: /^1\. M1$/ })).toBeInTheDocument();
    // Blunder marker (critical) should show its description
    expect(screen.getByRole("button", { name: /1\.\.\. M2 Blunder/ })).toBeInTheDocument();

    // In 'all' display mode, both should be shown
    rerender(
      <MoveList
        currentPly={1}
        markerDisplayMode="all"
        moveMarkers={[bookMarker, blunderMarker]}
        moves={moves}
        onSelectPly={onSelectPly}
      />,
    );

    expect(screen.getByRole("button", { name: /1\. M1 Book/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /1\.\.\. M2 Blunder/ })).toBeInTheDocument();
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

function buildMarker({
  ply,
  primary_class,
}: {
  ply: number;
  primary_class: AnalysisMoveMarker["primary_class"];
}): AnalysisMoveMarker {
  return {
    rank_order: 1,
    ply,
    move_number: Math.ceil(ply / 2),
    side: ply % 2 === 1 ? "white" : "black",
    san: `M${ply}`,
    uci: `m${ply}`,
    best_move_san: null,
    best_move_uci: null,
    natural_move_san: null,
    natural_move_uci: null,
    primary_class,
    tags: [],
    label_metadata: { requires_explanation: true },
    eval_before_cp: 0,
    eval_after_cp: 0,
    drop_cp: 0,
    explanation: "",
    explanation_segments: [],
    explanation_line_cards: [],
    best_lines: [],
  };
}
