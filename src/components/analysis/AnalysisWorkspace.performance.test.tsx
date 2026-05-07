import { act, cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BestLine, BoardSide } from "../../types/analysis";
import type { GameAnalysisSnapshot } from "../../types/api";
import { AnalysisWorkspace } from "./AnalysisWorkspace";

interface StockfishSnapshot {
  fen: string | null;
  lines: BestLine[];
  evalCp: number | null;
  depth: number;
  isReady: boolean;
  isAnalyzing: boolean;
}

interface BoardRenderSample {
  fen: string;
  arrows: unknown;
  highlightedMove: string | null;
  orientation: BoardSide;
}

interface EvalBarRenderSample {
  evalCp: number | null;
  orientation: BoardSide;
}

const stockfishStore = vi.hoisted(() => {
  let snapshot: StockfishSnapshot = {
    fen: null,
    lines: [],
    evalCp: null,
    depth: 0,
    isReady: true,
    isAnalyzing: false,
  };
  const listeners = new Set<() => void>();

  return {
    analyze: vi.fn(),
    preAnalyze: vi.fn(),
    emit(next: Partial<StockfishSnapshot>) {
      snapshot = { ...snapshot, ...next };
      for (const listener of listeners) {
        listener();
      }
    },
    getSnapshot() {
      return snapshot;
    },
    reset() {
      snapshot = {
        fen: null,
        lines: [],
        evalCp: null,
        depth: 0,
        isReady: true,
        isAnalyzing: false,
      };
      listeners.clear();
      this.analyze.mockReset();
      this.preAnalyze.mockReset();
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
});

const apiMocks = vi.hoisted(() => ({
  pollGameAnalysis: vi.fn(),
  startImportedGameAnalysis: vi.fn(),
}));

const boardMetrics = vi.hoisted(() => ({
  renderCount: 0,
  mountCount: 0,
  unmountCount: 0,
  samples: [] as BoardRenderSample[],
  reset() {
    this.renderCount = 0;
    this.mountCount = 0;
    this.unmountCount = 0;
    this.samples = [];
  },
}));

const evalBarMetrics = vi.hoisted(() => ({
  renderCount: 0,
  samples: [] as EvalBarRenderSample[],
  reset() {
    this.renderCount = 0;
    this.samples = [];
  },
}));

vi.mock("../../hooks/useStockfish", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  return {
    useStockfish: () => {
      const snapshot = React.useSyncExternalStore(
        stockfishStore.subscribe,
        stockfishStore.getSnapshot,
        stockfishStore.getSnapshot,
      );
      return {
        ...snapshot,
        analyze: stockfishStore.analyze,
        stop: vi.fn(),
        preAnalyze: stockfishStore.preAnalyze,
      };
    },
  };
});

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    pollGameAnalysis: apiMocks.pollGameAnalysis,
    startImportedGameAnalysis: apiMocks.startImportedGameAnalysis,
  };
});

vi.mock("../../lib/game-analysis-mapping", async () => {
  const actual = await vi.importActual<typeof import("../../lib/game-analysis-mapping")>(
    "../../lib/game-analysis-mapping",
  );
  const { MOCK_ANALYSIS } = await vi.importActual<typeof import("../../data/mock-analysis")>(
    "../../data/mock-analysis",
  );
  return {
    ...actual,
    mapGameAnalysisSnapshot: vi.fn(() => MOCK_ANALYSIS),
  };
});

vi.mock("./UltraAnalysisBoard", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  return {
    UltraAnalysisBoard: ({
      fen,
      arrows,
      highlightedMove = null,
      orientation = "white",
    }: {
      fen: string;
      arrows: unknown;
      highlightedMove?: string | null;
      orientation?: BoardSide;
    }) => {
      boardMetrics.renderCount += 1;
      boardMetrics.samples.push({ fen, arrows, highlightedMove, orientation });
      React.useEffect(() => {
        boardMetrics.mountCount += 1;
        return () => {
          boardMetrics.unmountCount += 1;
        };
      }, []);
      return React.createElement("div", { "data-testid": "analysis-board" }, fen);
    },
  };
});

vi.mock("./EvalBar", () => ({
  EvalBar: ({ evalCp, orientation }: { evalCp: number | null; orientation: BoardSide }) => {
    evalBarMetrics.renderCount += 1;
    evalBarMetrics.samples.push({ evalCp, orientation });
    return <div data-testid="eval-bar">{evalCp ?? "none"}</div>;
  },
  HorizontalEvalBar: ({
    evalCp,
    orientation,
  }: {
    evalCp: number | null;
    orientation: BoardSide;
  }) => {
    evalBarMetrics.renderCount += 1;
    evalBarMetrics.samples.push({ evalCp, orientation });
    return <div data-testid="eval-bar-horizontal">{evalCp ?? "none"}</div>;
  },
}));

vi.mock("../ui/morph-text", () => ({
  MorphText: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

describe("AnalysisWorkspace performance baseline", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    window.localStorage.clear();
    Element.prototype.scrollIntoView = vi.fn();
    Element.prototype.getAnimations = vi.fn().mockReturnValue([]);
    Element.prototype.animate = vi.fn().mockReturnValue({ cancel: vi.fn() });
    stockfishStore.reset();
    apiMocks.pollGameAnalysis.mockReset();
    apiMocks.startImportedGameAnalysis.mockReset();
    boardMetrics.reset();
    evalBarMetrics.reset();
  });

  afterEach(() => {
    cleanup();
  });

  it("mounts exactly one board for each responsive layout", async () => {
    installMatchMedia(true);
    const desktop = renderWorkspaceWithCompletedAnalysis();

    await screen.findByTestId("analysis-board");
    expect(screen.getAllByTestId("analysis-board")).toHaveLength(1);
    expect(boardMetrics.mountCount).toBe(1);
    expect(boardMetrics.unmountCount).toBe(0);

    desktop.unmount();
    boardMetrics.reset();
    installMatchMedia(false);
    renderWorkspaceWithCompletedAnalysis();

    await screen.findByTestId("analysis-board");
    expect(screen.getAllByTestId("analysis-board")).toHaveLength(1);
    expect(boardMetrics.mountCount).toBe(1);
    expect(boardMetrics.unmountCount).toBe(0);
  });

  it("ignores browser engine snapshots for backend-covered mainline positions", async () => {
    installMatchMedia(true);
    renderWorkspaceWithCompletedAnalysis();
    await screen.findByTestId("analysis-board");
    await screen.findByTestId("eval-bar");

    const initialRenderCount = boardMetrics.renderCount;
    const initialEvalRenderCount = evalBarMetrics.renderCount;
    const initialSample = lastBoardSample();
    const engineLine = bestLine("d1d7", 630);

    publishStockfish({
      fen: initialSample.fen,
      lines: [engineLine],
      depth: 18,
      evalCp: 630,
      isAnalyzing: true,
    });
    publishStockfish({ evalCp: 631, depth: 19 });
    publishStockfish({ evalCp: 632, depth: 20 });

    await waitForNoBrowserEngineTick();

    const engineOnlyRenderCount = boardMetrics.renderCount - initialRenderCount;
    const engineOnlySamples = boardMetrics.samples.slice(initialRenderCount);
    const boardPropChangesAfterFirstPublish = countBoardPropChanges(engineOnlySamples);
    const boardPropChangesFromInitial = countBoardPropChanges([
      initialSample,
      ...engineOnlySamples,
    ]);

    recordBaselineMetric("engine-only board renders", engineOnlyRenderCount);
    recordBaselineMetric("engine-only board prop changes", boardPropChangesAfterFirstPublish);
    recordBaselineMetric(
      "engine-only board prop changes from initial",
      boardPropChangesFromInitial,
    );

    expect(boardMetrics.mountCount).toBe(1);
    expect(boardMetrics.unmountCount).toBe(0);
    expect(lastEvalBarSample().evalCp).toBe(24);
    expect(evalBarMetrics.renderCount).toBe(initialEvalRenderCount);
    expect(engineOnlyRenderCount).toBe(0);
    expect(engineOnlySamples.every((sample) => sample.fen === initialSample.fen)).toBe(true);
    expect(boardPropChangesFromInitial).toBe(0);
    expect(
      engineOnlySamples.every((sample) => sample.orientation === initialSample.orientation),
    ).toBe(true);
    expect(
      engineOnlySamples.every((sample) => sample.highlightedMove === initialSample.highlightedMove),
    ).toBe(true);
  });

  it("does not pre-analyze backend-covered mainline positions", async () => {
    installMatchMedia(true);
    renderWorkspaceWithCompletedAnalysis();

    await screen.findByTestId("analysis-board");
    await waitForNoBrowserEngineTick();

    expect(stockfishStore.analyze).not.toHaveBeenCalled();
    expect(stockfishStore.preAnalyze).not.toHaveBeenCalled();
    recordBaselineMetric("pre-analysis queued fens", 0);
  });

  it("keeps the mobile board and eval bar stable while switching tabs", async () => {
    installMatchMedia(false);
    renderWorkspaceWithCompletedAnalysis();

    await screen.findByTestId("analysis-board");
    await screen.findByTestId("eval-bar-horizontal");
    boardMetrics.reset();
    evalBarMetrics.reset();

    for (let index = 0; index < 4; index += 1) {
      const button = screen.getByRole("button", { name: /show (analysis|moves)/i });
      act(() => {
        button.click();
      });
    }

    expect(boardMetrics.renderCount).toBe(0);
    expect(evalBarMetrics.renderCount).toBe(0);
  });

  it("keeps the mobile eval bar stable while changing board arrows", async () => {
    installMatchMedia(false);
    renderWorkspaceWithCompletedAnalysis();

    await screen.findByTestId("analysis-board");
    await screen.findByTestId("eval-bar-horizontal");

    act(() => {
      screen.getByRole("button", { name: /board settings/i }).click();
    });
    boardMetrics.reset();
    evalBarMetrics.reset();

    for (const value of ["0", "1", "2", "3"]) {
      const option = screen.queryByRole("button", { name: `Best line arrows: ${value}` });
      if (option) {
        act(() => {
          option.click();
        });
      }
    }

    expect(boardMetrics.renderCount).toBeGreaterThan(0);
    expect(evalBarMetrics.renderCount).toBe(0);
  });
});

function renderWorkspaceWithCompletedAnalysis() {
  window.history.replaceState(null, "", "/analysis/analysis-performance-baseline");
  apiMocks.pollGameAnalysis.mockResolvedValue(completedSnapshot());
  return render(<AnalysisWorkspace />);
}

function publishStockfish(next: Partial<StockfishSnapshot>): void {
  act(() => {
    stockfishStore.emit(next);
  });
}

function lastBoardSample(): BoardRenderSample {
  const sample = boardMetrics.samples.at(-1);
  if (sample === undefined) {
    throw new Error("Expected at least one board render sample.");
  }
  return sample;
}

function lastEvalBarSample(): EvalBarRenderSample {
  const sample = evalBarMetrics.samples.at(-1);
  if (sample === undefined) {
    throw new Error("Expected at least one eval bar render sample.");
  }
  return sample;
}

function bestLine(uci: string, evalCp: number): BestLine {
  return {
    san: "Rxd7",
    uci,
    eval_cp: evalCp,
    pv_san: ["Rxd7", "Rxd7", "Rd1"],
    pv_uci: [uci, "d8d7", "f1d1"],
  };
}

function countBoardPropChanges(samples: BoardRenderSample[]): number {
  let changes = 0;
  let previous = samples[0];
  for (const sample of samples.slice(1)) {
    if (
      previous !== undefined &&
      (sample.fen !== previous.fen ||
        sample.arrows !== previous.arrows ||
        sample.orientation !== previous.orientation ||
        sample.highlightedMove !== previous.highlightedMove)
    ) {
      changes += 1;
    }
    previous = sample;
  }
  return changes;
}

function installMatchMedia(isDesktop: boolean): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query === "(min-width: 1100px)" ? isDesktop : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function completedSnapshot(): GameAnalysisSnapshot {
  return {
    status: "succeeded",
    error: null,
    moves: [{ context: {} }],
  } as GameAnalysisSnapshot;
}

function recordBaselineMetric(name: string, value: unknown): void {
  if (import.meta.env.VITE_PRINT_PERF_BASELINE === "1") {
    console.info(`[perf-baseline] ${name}: ${JSON.stringify(value)}`);
  }
}

async function waitForNoBrowserEngineTick(): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, 120));
}
