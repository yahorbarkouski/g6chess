import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { BestLine } from "../../types/analysis";
import { BookLinesView, EngineLinesView } from "./EngineLinesView";

vi.mock("../ui/morph-text", () => ({
  MorphText: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const ROOT_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
const WHITE_TO_MOVE_FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2";

describe("BookLinesView", () => {
  it("renders opening names, weighted continuations, and preview chips", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();

    render(
      <BookLinesView
        bookLines={[
          {
            moves: [
              { san: "e5", uci: "e7e5" },
              { san: "Nf3", uci: "g1f3" },
            ],
            weight: 3,
            opening_name: "King's Pawn Game: Open Game",
            eco: "C20",
          },
          {
            moves: [{ san: "c5", uci: "c7c5" }],
            weight: 1,
            opening_name: "Sicilian Defense",
            eco: "B20",
          },
        ]}
        onPreview={onPreview}
        rootFen={ROOT_FEN}
      />,
    );

    expect(screen.getByText("King's Pawn Game")).toBeInTheDocument();
    expect(screen.getByText("King's Pawn Game: Open Game")).toBeInTheDocument();
    expect(screen.getByText("Sicilian Defense")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Preview e5 Nf3" }));

    expect(onPreview).toHaveBeenCalledWith(ROOT_FEN, ["e5", "Nf3"], 2);
  });
});

describe("EngineLinesView", () => {
  it("promotes the next-ply continuation when the played move matched the best line", () => {
    render(
      <EngineLinesView
        bestMatchesContinuation
        continuationLine={{
          fen: ROOT_FEN,
          line: line("Bb7", "c8b7", 176, ["Bb7", "Bxf4", "Nxg4"], 0.957),
        }}
        lines={[
          line("Qf3", "d1f3", 171, ["Qf3", "Bb7", "Bxf4"]),
          line("Nd2", "b1d2", 1, ["Nd2", "Nxg4", "Qxg4"]),
          line("Nc3", "b1c3", -23, ["Nc3", "Qd8", "Bxf4"]),
        ]}
        onPreview={vi.fn()}
        rootFen={WHITE_TO_MOVE_FEN}
      />,
    );

    expect(screen.getByText("Best continuation")).toBeInTheDocument();
    expect(screen.getAllByText("Alternative")).toHaveLength(1);
    expect(screen.queryByText(/Win \\d+%/)).not.toBeInTheDocument();
    expect(screen.queryByText("Line 2")).not.toBeInTheDocument();
    expect(screen.queryByText(/% at/)).not.toBeInTheDocument();
  });
});

function line(
  san: string,
  uci: string,
  evalCp: number,
  pvSan: string[],
  winProbability?: number,
): BestLine {
  return {
    san,
    uci,
    eval_cp: evalCp,
    ...(winProbability === undefined ? {} : { win_probability: winProbability }),
    pv_san: pvSan,
    pv_uci: [uci],
  };
}
