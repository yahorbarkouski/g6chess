import { afterEach, describe, expect, it, vi } from "vitest";
import { startImportedGameAnalysis } from "./api";

describe("startImportedGameAnalysis", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts PGN fallback requests to the import endpoint", async () => {
    const responsePayload = {
      analysis_id: "analysis-1",
      status: "pending",
      status_url: "/api/game-analysis/analysis-1",
      source: {
        source: "pgn",
        source_url: null,
        external_game_id: null,
        title: "Pasted PGN",
        white_username: null,
        black_username: null,
        white_rating: null,
        black_rating: null,
        time_control: null,
        result: null,
        allows_global_training: false,
        rights_basis: "User-requested analysis input only.",
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responsePayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await startImportedGameAnalysis({ source: "pgn", pgn: "1. e4 e5 *" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/game-analysis/import",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ source: "pgn", pgn: "1. e4 e5 *" }),
      }),
    );
  });
});
