import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PlayerBar } from "./PlayerBar";

afterEach(cleanup);

const player = {
  name: "Alpha",
  side: "white",
  rating: 1500,
  captured: { q: 0, r: 0, b: 0, n: 0, p: 0 },
  materialAdvantage: 0,
} satisfies Parameters<typeof PlayerBar>[0];

describe("PlayerBar accuracy", () => {
  it("shows an unavailable placeholder until the complete game has accuracy", () => {
    const { rerender } = render(<PlayerBar {...player} />);

    expect(screen.getByLabelText("White game accuracy unavailable")).toHaveTextContent("—");

    rerender(<PlayerBar {...player} accuracyPercent={92.3} />);

    expect(screen.getByLabelText("White game accuracy 92.3%")).toHaveTextContent("92.3%");
  });

  it("preserves zero and full accuracy and labels the player's side", () => {
    const { rerender } = render(<PlayerBar {...player} side="black" accuracyPercent={0} />);

    expect(screen.getByLabelText("Black game accuracy 0.0%")).toHaveTextContent("0.0%");

    rerender(<PlayerBar {...player} side="black" accuracyPercent={100} />);

    expect(screen.getByLabelText("Black game accuracy 100.0%")).toHaveTextContent("100.0%");
  });
});
