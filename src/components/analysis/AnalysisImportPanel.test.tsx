import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisImportPanel } from "./AnalysisImportPanel";

describe("AnalysisImportPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("surfaces the URL import error inline and highlights the PGN toggle", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockRejectedValue(new Error("Chess.com timed out"));

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.type(screen.getByLabelText("Chess.com URL"), "https://www.chess.com/game/1");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("chess.com import failed")).toBeTruthy();
    expect(screen.getByLabelText("Chess.com URL")).toBeTruthy();
    expect(screen.queryByLabelText("PGN fallback")).toBeNull();

    const toggle = screen.getByTitle("PGN fallback");
    expect(toggle.className).toContain("font-medium");
    expect(toggle.className).toContain("text-stone-800");

    await user.click(toggle);
    expect(screen.getByLabelText("PGN fallback")).toBeTruthy();
    expect(screen.queryByText("chess.com import failed")).toBeNull();
  });

  it("submits pasted PGN through the same import boundary without a player level", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.click(screen.getByTitle("PGN fallback"));
    await user.type(screen.getByLabelText("PGN fallback"), "1. e4 e5 *");
    await user.click(screen.getByRole("button", { name: "Analyze PGN" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith({
      source: "pgn",
      pgn: "1. e4 e5 *",
      include_context: true,
      use_baseline_fallback: false,
      explain_significance: ["critical"],
    });
  });

  it("accepts a production-domain Chess.com game route and sends the canonical Chess.com URL", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(<AnalysisImportPanel error={null} onImport={onImport} status="idle" />);

    await user.type(screen.getByLabelText("Chess.com URL"), "g6chess.com/game/live/168193636078");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith({
      source: "chess_com_live_url",
      url: "https://www.chess.com/game/live/168193636078",
      include_context: true,
      use_baseline_fallback: false,
      explain_significance: ["critical"],
    });
  });
});
