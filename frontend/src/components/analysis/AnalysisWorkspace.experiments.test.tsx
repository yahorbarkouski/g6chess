import { act, cleanup, render, screen } from "@testing-library/react";
import { Profiler, type ProfilerOnRenderCallback, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BestLine } from "../../types/analysis";
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
      for (const listener of listeners) listener();
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

const renderCounters = vi.hoisted(() => {
  const counts: Record<string, number> = {};
  return {
    counts,
    bump(name: string) {
      counts[name] = (counts[name] ?? 0) + 1;
    },
    reset() {
      for (const key of Object.keys(counts)) {
        delete counts[key];
      }
    },
  };
});

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

const apiMocks = vi.hoisted(() => ({
  pollGameAnalysis: vi.fn(),
  startImportedGameAnalysis: vi.fn(),
}));

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
    UltraAnalysisBoard: ({ fen }: { fen: string }) => {
      renderCounters.bump("UltraAnalysisBoard");
      return React.createElement("div", { "data-testid": "analysis-board" }, fen);
    },
  };
});

vi.mock("./EvalBar", () => ({
  EvalBar: ({ evalCp }: { evalCp: number | null }) => {
    renderCounters.bump("EvalBar");
    return <div data-testid="eval-bar">{evalCp ?? "none"}</div>;
  },
  HorizontalEvalBar: ({ evalCp }: { evalCp: number | null }) => {
    renderCounters.bump("HorizontalEvalBar");
    return <div data-testid="eval-bar-horizontal">{evalCp ?? "none"}</div>;
  },
}));

vi.mock("./MoveList", async () => {
  const actual = await vi.importActual<typeof import("./MoveList")>("./MoveList");
  return {
    ...actual,
    MoveList: (props: Parameters<typeof actual.MoveList>[0]) => {
      renderCounters.bump("MoveList");
      return actual.MoveList(props);
    },
  };
});

vi.mock("./PositionInfo", async () => {
  const actual = await vi.importActual<typeof import("./PositionInfo")>("./PositionInfo");
  return {
    ...actual,
    PositionInfo: (props: Parameters<typeof actual.PositionInfo>[0]) => {
      renderCounters.bump("PositionInfo");
      return actual.PositionInfo(props);
    },
  };
});

vi.mock("./EngineLinesView", async () => {
  const actual = await vi.importActual<typeof import("./EngineLinesView")>("./EngineLinesView");
  return {
    ...actual,
    EngineLinesView: (props: Parameters<typeof actual.EngineLinesView>[0]) => {
      renderCounters.bump("EngineLinesView");
      return actual.EngineLinesView(props);
    },
  };
});

vi.mock("./PlayerBar", async () => {
  const actual = await vi.importActual<typeof import("./PlayerBar")>("./PlayerBar");
  return {
    ...actual,
    PlayerBar: (props: Parameters<typeof actual.PlayerBar>[0]) => {
      renderCounters.bump("PlayerBar");
      return actual.PlayerBar(props);
    },
  };
});

vi.mock("../ui/morph-text", async () => {
  const React = await vi.importActual<typeof import("react")>("react");
  return {
    MorphText: ({ children }: { children: ReactNode }) => {
      renderCounters.bump("MorphText");
      return React.createElement(React.Fragment, null, children);
    },
  };
});

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  Element.prototype.scrollIntoView = vi.fn();
  Element.prototype.getAnimations = vi.fn().mockReturnValue([]);
  Element.prototype.animate = vi.fn().mockReturnValue({ cancel: vi.fn() });
  stockfishStore.reset();
  apiMocks.pollGameAnalysis.mockReset();
  apiMocks.startImportedGameAnalysis.mockReset();
  renderCounters.reset();
});

afterEach(() => {
  cleanup();
});

interface ProfilerSample {
  id: string;
  phase: "mount" | "update" | "nested-update";
  actualDuration: number;
  baseDuration: number;
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

function renderWorkspace(profileId: string, onRender: ProfilerOnRenderCallback) {
  window.history.replaceState(null, "", "/analysis/analysis-experiments");
  apiMocks.pollGameAnalysis.mockResolvedValue(completedSnapshot());
  return render(
    <Profiler id={profileId} onRender={onRender}>
      <AnalysisWorkspace />
    </Profiler>,
  );
}

function clickNextMove(): void {
  const button = screen.getAllByRole("button", { name: /next move/i })[0];
  if (!button) {
    throw new Error("Could not find Next move button");
  }
  act(() => {
    button.click();
  });
}

function publishStockfish(next: Partial<StockfishSnapshot>): void {
  act(() => stockfishStore.emit(next));
}

function bestLine(uci: string, evalCp: number, san = "Rxd7"): BestLine {
  return {
    san,
    uci,
    eval_cp: evalCp,
    pv_san: [san, "Rxd7", "Rd1"],
    pv_uci: [uci, "d8d7", "f1d1"],
  };
}

function summarize(samples: ProfilerSample[]): {
  count: number;
  totalMs: number;
  maxMs: number;
} {
  let totalMs = 0;
  let maxMs = 0;
  for (const sample of samples) {
    totalMs += sample.actualDuration;
    if (sample.actualDuration > maxMs) {
      maxMs = sample.actualDuration;
    }
  }
  return { count: samples.length, totalMs, maxMs };
}

function logExperiment(name: string, payload: Record<string, unknown>): void {
  if (import.meta.env.VITE_PRINT_PERF_BASELINE !== "1") {
    return;
  }
  const line = `[experiment] ${name} ${JSON.stringify(payload)}\n`;
  const proc = (globalThis as { process?: { stderr?: { write?: (data: string) => void } } })
    .process;
  if (proc?.stderr?.write) {
    proc.stderr.write(line);
  } else {
    console.warn(line);
  }
}

async function waitForBoard(): Promise<void> {
  await screen.findByTestId("analysis-board");
}

describe("AnalysisWorkspace experiments — desktop", () => {
  beforeEach(() => installMatchMedia(true));

  it("baseline mount cost (desktop, completed analysis)", async () => {
    const samples: ProfilerSample[] = [];
    const onRender: ProfilerOnRenderCallback = (_id, phase, actualDuration, baseDuration) => {
      samples.push({ id: _id, phase, actualDuration, baseDuration });
    };
    renderWorkspace("desktop-mount", onRender);
    await waitForBoard();

    const summary = summarize(samples);
    logExperiment("desktop mount", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
    expect(samples.some((s) => s.phase === "mount")).toBe(true);
  });

  it("stepping forward 5 plies (desktop)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("desktop-step", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    renderCounters.reset();
    samples.length = 0;

    for (let i = 0; i < 5; i += 1) {
      clickNextMove();
    }

    const summary = summarize(samples);
    logExperiment("desktop step (5 forward)", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("stockfish snapshot fan-out (desktop, browser-eval position)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("desktop-stockfish", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();

    clickNextMove();
    clickNextMove();
    renderCounters.reset();
    samples.length = 0;

    for (let depth = 14; depth <= 24; depth += 1) {
      publishStockfish({
        depth,
        evalCp: 30 + depth,
        lines: [bestLine("d2d4", 30 + depth)],
        isAnalyzing: true,
      });
    }
    publishStockfish({ isAnalyzing: false });

    const summary = summarize(samples);
    logExperiment("desktop stockfish 11 ticks", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });
});

describe("AnalysisWorkspace experiments — mobile", () => {
  beforeEach(() => installMatchMedia(false));

  it("baseline mount cost (mobile)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-mount", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();

    const summary = summarize(samples);
    logExperiment("mobile mount", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("stepping forward 5 plies (mobile)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-step", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    renderCounters.reset();
    samples.length = 0;

    for (let i = 0; i < 5; i += 1) {
      clickNextMove();
    }

    const summary = summarize(samples);
    logExperiment("mobile step (5 forward)", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("toggle mobile tab moves<->analysis 4 times", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-tab", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    renderCounters.reset();
    samples.length = 0;

    for (let i = 0; i < 4; i += 1) {
      const button = screen.getByRole("button", { name: /show (analysis|moves)/i });
      act(() => {
        button.click();
      });
    }

    const summary = summarize(samples);
    logExperiment("mobile tab toggle x4", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("settings popover open/close (mobile)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-settings-toggle", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    renderCounters.reset();
    samples.length = 0;

    for (let i = 0; i < 4; i += 1) {
      const settings = screen.getByRole("button", { name: /board settings/i });
      act(() => {
        settings.click();
      });
    }

    const summary = summarize(samples);
    logExperiment("mobile settings popover toggle x4", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("rapid stepping (mobile, 30 next clicks)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-rapid-step", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    renderCounters.reset();
    samples.length = 0;
    const start = performance.now();

    for (let i = 0; i < 30; i += 1) {
      clickNextMove();
    }

    const wallClockMs = performance.now() - start;
    const summary = summarize(samples);
    logExperiment("mobile rapid stepping x30", {
      wallClockMs: Number(wallClockMs.toFixed(2)),
      profilerSummary: summary,
      rendersPerStep: {
        HorizontalEvalBar: (renderCounters.counts.HorizontalEvalBar ?? 0) / 30,
        PlayerBar: (renderCounters.counts.PlayerBar ?? 0) / 30,
        UltraAnalysisBoard: (renderCounters.counts.UltraAnalysisBoard ?? 0) / 30,
        PositionInfo: (renderCounters.counts.PositionInfo ?? 0) / 30,
        EngineLinesView: (renderCounters.counts.EngineLinesView ?? 0) / 30,
        MorphText: (renderCounters.counts.MorphText ?? 0) / 30,
      },
      counters: { ...renderCounters.counts },
    });
  });

  it("change engine arrow count from popover (mobile)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-arrow-change", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();

    const settings = screen.getByRole("button", { name: /board settings/i });
    act(() => settings.click());
    renderCounters.reset();
    samples.length = 0;

    const arrowOptions = ["0", "1", "2", "3"];
    for (const value of arrowOptions) {
      const button = screen.queryByRole("button", { name: `Best line arrows: ${value}` });
      if (button) {
        act(() => button.click());
      }
    }

    const summary = summarize(samples);
    logExperiment("mobile arrow count change x4", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });

  it("stockfish snapshot fan-out (mobile, browser-eval)", async () => {
    const samples: ProfilerSample[] = [];
    renderWorkspace("mobile-stockfish", (_id, phase, actualDuration, baseDuration) =>
      samples.push({ id: _id, phase, actualDuration, baseDuration }),
    );
    await waitForBoard();
    clickNextMove();
    clickNextMove();
    renderCounters.reset();
    samples.length = 0;

    for (let depth = 14; depth <= 24; depth += 1) {
      publishStockfish({
        depth,
        evalCp: 30 + depth,
        lines: [bestLine("d2d4", 30 + depth)],
        isAnalyzing: true,
      });
    }
    publishStockfish({ isAnalyzing: false });

    const summary = summarize(samples);
    logExperiment("mobile stockfish 11 ticks", {
      profilerSummary: summary,
      counters: { ...renderCounters.counts },
    });
  });
});
