import { afterEach, describe, expect, it, vi } from "vitest";
import { type ApiError, getCachedChessComLiveGameAnalysis, startImportedGameAnalysis } from "./api";

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

  it("reads cached Chess.com live-game analyses by external game id", async () => {
    const responsePayload = {
      analysis_id: "analysis-1",
      status: "succeeded",
      status_url: "/api/game-analysis/analysis-1",
      source: {
        source: "chess_com_live_url",
        source_url: "https://www.chess.com/game/live/168193636078",
        external_game_id: "168193636078",
        title: "Alpha vs Beta",
        white_username: "Alpha",
        black_username: "Beta",
        white_rating: 1600,
        black_rating: 1500,
        time_control: "180+2",
        result: "1-0",
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

    await getCachedChessComLiveGameAnalysis("168193636078");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/game-analysis/import/chess-com/live/168193636078",
      {},
    );
  });

  it("preserves backend error code and Retry-After for rate limits", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: "import_start_rate_limited",
              message: "Too many requests. Try again after the cooldown.",
            },
          }),
          {
            status: 429,
            headers: {
              "Content-Type": "application/json",
              "Retry-After": "30",
            },
          },
        ),
      ),
    );

    await expect(
      startImportedGameAnalysis({ source: "pgn", pgn: "1. e4 e5 *" }),
    ).rejects.toMatchObject({
      status: 429,
      code: "import_start_rate_limited",
      retryAfterSeconds: 30,
      detail: "Too many requests. Try again after the cooldown.",
    } satisfies Partial<ApiError>);
  });
});
