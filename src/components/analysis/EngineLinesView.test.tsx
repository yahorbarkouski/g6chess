import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { BookLinesView } from "./EngineLinesView";

vi.mock("../ui/morph-text", () => ({
  MorphText: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const ROOT_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";

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
