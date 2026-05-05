import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisImportPanel } from "./AnalysisImportPanel";

describe("AnalysisImportPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens the PGN fallback and preserves the URL import error", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockRejectedValue(new Error("Chess.com timed out"));

    render(
      <AnalysisImportPanel
        error={null}
        onImport={onImport}
        snapshot={null}
        source={null}
        status="idle"
      />,
    );

    await user.type(screen.getByLabelText("Chess.com URL"), "https://www.chess.com/game/1");
    await user.click(screen.getByRole("button", { name: "Analyze" }));

    expect(await screen.findByText("Chess.com timed out")).toBeTruthy();
    expect(screen.getByLabelText("PGN fallback")).toBeTruthy();
  });

  it("submits pasted PGN through the same import boundary", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);

    render(
      <AnalysisImportPanel
        error={null}
        onImport={onImport}
        snapshot={null}
        source={null}
        status="idle"
      />,
    );

    await user.click(screen.getByTitle("PGN fallback"));
    await user.type(screen.getByLabelText("PGN fallback"), "1. e4 e5 *");
    await user.click(screen.getByRole("button", { name: "Analyze PGN" }));

    await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1));
    expect(onImport).toHaveBeenCalledWith(
      expect.objectContaining({
        source: "pgn",
        pgn: "1. e4 e5 *",
        include_context: true,
        use_baseline_fallback: false,
        player_level: { kind: "rating", value: 1500, system: "frontend-default" },
      }),
    );
  });
});
