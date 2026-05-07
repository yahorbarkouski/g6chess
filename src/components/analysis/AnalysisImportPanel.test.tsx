import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisImportPanel } from "./AnalysisImportPanel";

describe("AnalysisImportPanel", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    vi.resetModules();
    delete window.turnstile;
    delete window.__g6TurnstileScriptLoading;
  });

  it("surfaces the URL import error inline and highlights the PGN toggle", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockRejectedValue(new Error("Chess.com timed out"));

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.type(screen.getByLabelText("Game URL"), "https://www.chess.com/game/1");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("link import failed")).toBeTruthy();
    expect(screen.getByLabelText("Game URL")).toBeTruthy();
    expect(screen.queryByLabelText("PGN fallback")).toBeNull();

    const toggle = screen.getByTitle("PGN fallback");
    expect(toggle.className).toContain("font-medium");
    expect(toggle.className).toContain("text-stone-800");

    await user.click(toggle);
    expect(screen.getByLabelText("PGN fallback")).toBeTruthy();
    expect(screen.queryByText("link import failed")).toBeNull();
  });

  it("prompts for missing PGN Elo and submits PGN with rating headers", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.click(screen.getByTitle("PGN fallback"));
    fireEvent.change(screen.getByLabelText("PGN fallback"), {
      target: { value: '[Event "Test"]\n[White "Alpha"]\n[Black "Beta"]\n\n1. e4 e5 *' },
    });
    await user.click(screen.getByRole("button", { name: "Analyze PGN" }));

    expect(await screen.findByRole("dialog", { name: "Add missing Elo" })).toBeTruthy();
    expect(onImport).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("White Elo"), "1725");
    await user.type(screen.getByLabelText("Black Elo"), "1680");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith({
      source: "pgn",
      pgn: '[Event "Test"]\n[White "Alpha"]\n[Black "Beta"]\n[WhiteElo "1725"]\n[BlackElo "1680"]\n\n1. e4 e5 *',
      include_context: false,
      use_baseline_fallback: false,
      explain_significance: ["critical"],
    });
  });

  it("can apply default Elo values for missing PGN ratings", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.click(screen.getByTitle("PGN fallback"));
    fireEvent.change(screen.getByLabelText("PGN fallback"), {
      target: { value: '[White "Alpha"]\n[Black "Beta"]\n\n1. e4 e5 *' },
    });
    await user.click(screen.getByRole("button", { name: "Analyze PGN" }));
    await user.click(await screen.findByRole("button", { name: "Use default" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith(
      expect.objectContaining({
        pgn: '[White "Alpha"]\n[Black "Beta"]\n[WhiteElo "1500"]\n[BlackElo "1500"]\n\n1. e4 e5 *',
      }),
    );
  });

  it("submits pasted PGN immediately when Elo headers exist", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);
    const pgn = '[WhiteElo "1600"]\n[BlackElo "1500"]\n\n1. e4 e5 *';

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.click(screen.getByTitle("PGN fallback"));
    fireEvent.change(screen.getByLabelText("PGN fallback"), { target: { value: pgn } });
    await user.click(screen.getByRole("button", { name: "Analyze PGN" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onImport).toHaveBeenCalledWith({
      source: "pgn",
      pgn,
      include_context: false,
      use_baseline_fallback: false,
      explain_significance: ["critical"],
    });
  });

  it("switches from URL mode to PGN mode when pasted text looks like PGN", async () => {
    const pgn = '[Event "Paste"]\n[White "Alpha"]\n[Black "Beta"]\n\n1. e4 e5 *';

    render(<AnalysisImportPanel error={null} onImport={vi.fn()} status="idle" />);

    fireEvent.change(screen.getByLabelText("Game URL"), { target: { value: pgn } });

    expect(screen.getByLabelText("PGN fallback")).toHaveValue(pgn);
    expect(screen.getByRole("button", { name: "Analyze PGN" })).toBeTruthy();
  });

  it("accepts a production-domain Chess.com game route and sends the canonical Chess.com URL", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.type(screen.getByLabelText("Game URL"), "g6chess.com/game/live/168193636078");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith({
      source: "chess_com_live_url",
      url: "https://www.chess.com/game/live/168193636078",
      include_context: false,
      use_baseline_fallback: false,
      explain_significance: ["critical"],
    });
  });

  it("accepts a Lichess game URL and sends the canonical Lichess import source", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.type(screen.getByLabelText("Game URL"), "https://lichess.org/fY44h4OY/black#56");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith(
      {
        source: "lichess_game_url",
        url: "https://lichess.org/fY44h4OY",
        include_context: false,
        use_baseline_fallback: false,
        explain_significance: ["critical"],
      },
      {
        boardOrientation: "black",
        externalGameId: "fY44h4OY",
        source: "lichess_game_url",
      },
    );
  });

  it("accepts a 12-character Lichess URL and imports the canonical 8-character game ID", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    const submitButton = screen.getByRole("button", { name: "Analyze" });
    await user.type(screen.getByLabelText("Game URL"), "https://lichess.org/fY44h4OYabcd/black");

    expect(submitButton).toBeEnabled();

    await user.keyboard("{Enter}");

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith(
      {
        source: "lichess_game_url",
        url: "https://lichess.org/fY44h4OY",
        include_context: false,
        use_baseline_fallback: false,
        explain_significance: ["critical"],
      },
      {
        boardOrientation: "black",
        externalGameId: "fY44h4OY",
        source: "lichess_game_url",
      },
    );
  });

  it("verifies with Turnstile before starting an import when protection is enabled", async () => {
    vi.stubEnv("VITE_G6_TURNSTILE_SITE_KEY", "site-key");
    vi.resetModules();
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    let verifyTurnstile: ((token: string) => void) | undefined;
    const removeTurnstile = vi.fn();
    window.turnstile = {
      render: vi.fn((container, options) => {
        container.dataset.testid = "turnstile-widget";
        container.textContent = "Turnstile challenge";
        verifyTurnstile = options.callback;
        return "widget-id";
      }),
      remove: removeTurnstile,
    };

    const { AnalysisImportPanel: PanelWithTurnstile } = await import("./AnalysisImportPanel");

    render(<PanelWithTurnstile error={null} onImport={onImport} status="idle" />);

    expect(screen.queryByTestId("turnstile-widget")).toBeNull();

    await user.type(screen.getByLabelText("Game URL"), "g6chess.com/game/live/168193636078");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    const turnstile = await screen.findByTestId("turnstile-widget");
    expect(onImport).not.toHaveBeenCalled();
    const feedbackCard = screen.getByRole("link", { name: /Leave feedback/i });
    expect(feedbackCard.compareDocumentPosition(turnstile)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);

    act(() => {
      verifyTurnstile?.("verified-token");
    });

    await waitFor(() => expect(screen.queryByTestId("turnstile-widget")).toBeNull());
    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(onImport).toHaveBeenCalledWith({
        source: "chess_com_live_url",
        url: "https://www.chess.com/game/live/168193636078",
        include_context: false,
        use_baseline_fallback: false,
        explain_significance: ["critical"],
        turnstile_token: "verified-token",
      }),
    );
    expect(removeTurnstile).toHaveBeenCalledWith("widget-id");
  });
});
