import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ElementType, ReactNode } from "react";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisMoveMarker, BestLine, GameMove } from "../../types/analysis";
import { PositionInfo } from "./PositionInfo";

vi.mock("../ui/morph-text", () => ({
  MorphText: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/loading-ui/text-shimmer", () => ({
  TextShimmer: ({
    as: Component = "p",
    children,
    className,
  }: {
    as?: ElementType;
    children: string;
    className?: string;
  }) => (
    <Component className={className} data-testid="text-shimmer">
      {children}
    </Component>
  ),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

vi.mock("./UltraAnalysisBoard", () => ({
  UltraAnalysisBoard: ({
    className = "",
    fen,
    highlightedMove = null,
  }: {
    className?: string;
    fen: string;
    highlightedMove?: string | null;
  }) => (
    <div
      data-classname={className}
      data-highlighted={highlightedMove ?? ""}
      data-testid="mini-board"
    >
      {fen}
    </div>
  ),
}));

const ROOT_FEN = "rn1qkbnr/pppbpppp/8/3p4/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1";

describe("PositionInfo", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    installPointerMedia(false);
    vi.unstubAllGlobals();
  });

  it("highlights only the segment anchor and previews the attached line", async () => {
    const user = userEvent.setup();
    const onMoveClick = vi.fn();
    const marker = markerWithRichExplanation();

    render(
      <PositionInfo
        currentMove={move()}
        onMoveClick={onMoveClick}
        rootFen={ROOT_FEN}
        selectedMarker={marker}
      />,
    );

    expect(screen.getByRole("button", { name: "b5" })).toBeInTheDocument();
    expect(screen.getByText(/was a blunder because it allowed the/)).toBeInTheDocument();
    const playedAnchor = screen.getByRole("button", { name: /key reply Nxb5/i });
    const betterAnchor = screen.getByRole("button", { name: /Kd8: The calmer defense/i });

    expect(playedAnchor).toHaveTextContent("key reply Nxb5");
    expect(playedAnchor.className).toContain("bg-red");
    expect(playedAnchor.className).toContain("whitespace-normal");
    expect(playedAnchor.className).toContain("box-decoration-clone");
    expect(playedAnchor.parentElement?.className).toContain("inline");
    expect(playedAnchor.parentElement?.className).not.toContain("inline-block");
    expect(playedAnchor.className).not.toContain("border-b");
    expect(betterAnchor.className).toContain("bg-emerald");
    expect(screen.queryByRole("button", { name: /b5 was a blunder because/i })).toBeNull();

    await user.hover(playedAnchor);

    const preview = screen.getByTestId("line-card-preview");
    const title = within(preview).getByText("What b5 allows");
    const board = within(preview).getByTestId("mini-board");
    const description = within(preview).getByText(
      "The knight jump opens the b-file before Black can castle.",
    );
    const lastMove = within(preview).getByText("b4+");

    expect(board).toHaveAttribute("data-classname", expect.stringContaining("rounded-none"));
    expect(preview.querySelector("svg")).toBeNull();
    expect(isBefore(title, board)).toBe(true);
    expect(isBefore(board, description)).toBe(true);
    expect(isBefore(description, lastMove)).toBe(true);

    await user.click(playedAnchor);

    expect(onMoveClick).toHaveBeenCalledWith(ROOT_FEN, ["b5", "Nxb5", "Qb4+"], 3);
  });

  it("loops the mini-board line while the hover card is open", async () => {
    vi.useFakeTimers();

    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={markerWithRichExplanation()}
      />,
    );

    fireEvent.pointerEnter(screen.getByRole("button", { name: /key reply Nxb5/i }));

    const board = screen.getByTestId("mini-board");
    expect(board).toHaveTextContent(ROOT_FEN);

    act(() => vi.advanceTimersByTime(850));
    expect(board).not.toHaveTextContent(ROOT_FEN);

    act(() => vi.advanceTimersByTime(850 * 3));
    expect(board).toHaveTextContent(ROOT_FEN);
  });

  it("keeps the hover card open while moving from the anchor into the card", () => {
    vi.useFakeTimers();

    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={markerWithRichExplanation()}
      />,
    );

    const anchor = screen.getByRole("button", { name: /key reply Nxb5/i });
    fireEvent.pointerEnter(anchor);

    const preview = screen.getByTestId("line-card-preview");
    const shell = preview.parentElement;
    const root = anchor.parentElement;

    expect(shell).not.toBeNull();
    expect(root).not.toBeNull();

    fireEvent.pointerLeave(root as HTMLElement);
    fireEvent.pointerEnter(shell as HTMLElement);

    act(() => vi.advanceTimersByTime(180));

    expect(screen.getByTestId("line-card-preview")).toBeInTheDocument();
  });

  it("lets users click a move inside the hover card", async () => {
    const user = userEvent.setup();
    const onMoveClick = vi.fn();

    render(
      <PositionInfo
        currentMove={move()}
        onMoveClick={onMoveClick}
        rootFen={ROOT_FEN}
        selectedMarker={markerWithRichExplanation()}
      />,
    );

    await user.hover(screen.getByRole("button", { name: /key reply Nxb5/i }));

    const preview = screen.getByTestId("line-card-preview");
    await user.click(within(preview).getByRole("button", { name: /xb5/i }));

    expect(onMoveClick).toHaveBeenCalledWith(ROOT_FEN, ["b5", "Nxb5", "Qb4+"], 2);
    expect(screen.getByTestId("line-card-preview")).toBeInTheDocument();
  });

  it("opens and dismisses a tap popover on coarse pointers", async () => {
    installPointerMedia(true);
    const user = userEvent.setup();

    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={markerWithRichExplanation()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /key reply Nxb5/i }));

    const dialog = screen.getByRole("dialog", { name: "What b5 allows" });
    expect(within(dialog).getByTestId("mini-board")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Close line preview" }));

    expect(screen.queryByRole("dialog", { name: "What b5 allows" })).toBeNull();
  });

  it("keeps plain explanation move tokens clickable", async () => {
    const user = userEvent.setup();
    const onMoveClick = vi.fn();
    const marker = {
      ...markerWithRichExplanation(),
      explanation:
        "Kd8 was the better idea because after Bxf7 Black still gets the king toward c7.",
      explanation_segments: [],
      explanation_line_cards: [],
      best_lines: [line("Kd8", ["Kd8", "Bxf7", "Kc7"])],
    };

    render(
      <PositionInfo
        currentMove={move()}
        onMoveClick={onMoveClick}
        rootFen={ROOT_FEN}
        selectedMarker={marker}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Bxf7" }));

    expect(onMoveClick).toHaveBeenCalledWith(ROOT_FEN, ["Kd8", "Bxf7", "Kc7"], 2);
  });

  it("copies the current PGN when the move title is clicked", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", {
      ...navigator,
      clipboard: { writeText },
    });

    render(
      <PositionInfo
        currentMove={move()}
        currentPly={3}
        moves={[
          gameMove({ ply: 1, move_number: 1, side: "white", san: "e4" }),
          gameMove({ ply: 2, move_number: 1, side: "black", san: "e5" }),
          gameMove({ ply: 3, move_number: 2, side: "white", san: "Nf3" }),
          gameMove({ ply: 4, move_number: 2, side: "black", san: "Nc6" }),
        ]}
        rootFen={ROOT_FEN}
        selectedMarker={markerWithRichExplanation()}
      />,
    );

    const moveTitle = screen.getByRole("button", { name: "Copy moves through 9... b5" });
    expect(moveTitle).toHaveAttribute("title", "Copy moves to clipboard");

    await user.click(moveTitle);

    expect(writeText).toHaveBeenCalledWith("1. e4 e5 2. Nf3");
    expect(toast.success).toHaveBeenCalledWith("Moves copied to clipboard");
  });

  it("uses the opening name as the selected book move badge", () => {
    render(
      <PositionInfo
        currentMove={move()}
        openingName="King's Pawn Game: Open Game"
        rootFen={ROOT_FEN}
        selectedMarker={{
          ...markerWithRichExplanation(),
          primary_class: "book",
          label_metadata: { is_book_move: true },
        }}
      />,
    );

    expect(screen.getByText("King's Pawn Game")).toBeInTheDocument();
    expect(screen.queryByText("Book")).toBeNull();
  });

  it("uses beautiful metadata to decorate the selected move badge", () => {
    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={{
          ...markerWithRichExplanation(),
          primary_class: "best",
          label_metadata: { beauty_label: "beautiful" },
        }}
      />,
    );

    expect(screen.queryByText("Beautiful")).toBeNull();
    expect(screen.getByText("Best")).toBeInTheDocument();
  });

  it("uses brilliant metadata to decorate the selected move badge", () => {
    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={{
          ...markerWithRichExplanation(),
          primary_class: "brilliant",
          label_metadata: { beauty_label: "brilliant" },
        }}
      />,
    );

    const brilliantBadges = screen.getAllByText("Brilliant");

    expect(brilliantBadges).toHaveLength(1);
    expect(brilliantBadges[0]).toHaveClass("bg-purple-100", "text-purple-800");
  });

  it("does not show notable metadata as a selected move highlight", () => {
    render(
      <PositionInfo
        currentMove={move()}
        rootFen={ROOT_FEN}
        selectedMarker={{
          ...markerWithRichExplanation(),
          primary_class: "good",
          label_metadata: { beauty_label: "notable" },
        }}
      />,
    );

    expect(screen.queryByText("Notable")).toBeNull();
    expect(screen.getByText("Good")).toBeInTheDocument();
  });
});

function move(): GameMove {
  return {
    ply: 18,
    move_number: 9,
    side: "black",
    san: "b5",
    uci: "b7b5",
    fen_before: ROOT_FEN,
    fen_after: "rn1qkb1r/ppp1pppp/5n2/1B1p4/8/8/PPPPPPPP/RNBQK1NR w KQkq - 0 2",
  };
}

function gameMove(moveOverrides: Pick<GameMove, "move_number" | "ply" | "san" | "side">): GameMove {
  return {
    ...moveOverrides,
    uci: `${moveOverrides.san.toLowerCase()}-uci`,
    fen_before: `before-${moveOverrides.ply}`,
    fen_after: `after-${moveOverrides.ply}`,
  };
}

function markerWithRichExplanation(): AnalysisMoveMarker {
  return {
    rank_order: 1,
    ply: 18,
    move_number: 9,
    side: "black",
    san: "b5",
    uci: "b7b5",
    best_move_san: "Kd8",
    best_move_uci: "e8d8",
    natural_move_san: null,
    natural_move_uci: null,
    primary_class: "blunder",
    tags: ["king_safety"],
    label_metadata: {
      requires_explanation: true,
      explanation_model: "test-model",
    },
    eval_before_cp: 248,
    eval_after_cp: 720,
    drop_cp: 472,
    explanation: "b5 was a blunder because it let White open the b-file. Kd8 was the better idea.",
    explanation_segments: [
      {
        text: "b5 was a blunder because it allowed the key reply Nxb5, opening the b-file.",
        line_card_id: "played-line",
        line_card_anchor: "key reply Nxb5",
        highlight_color: "red",
      },
      {
        text: "Kd8 was the better idea because Black keeps the king connected to c7.",
        line_card_id: "better-line",
        line_card_anchor: "Kd8",
        highlight_color: "green",
      },
    ],
    explanation_line_cards: [
      {
        id: "played-line",
        moves: ["b5", "Nxb5", "Qb4+"],
        title: "What b5 allows",
        why: "The knight jump opens the b-file before Black can castle.",
      },
      {
        id: "better-line",
        moves: ["Kd8", "Bxf7", "Kc7"],
        title: "The calmer defense",
        why: "Black gives up comfort but keeps enough pieces near the king.",
      },
    ],
    best_lines: [line("Kd8", ["Kd8", "Bxf7", "Kc7"])],
  };
}

function installPointerMedia(isCoarse: boolean): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("hover: none") || query.includes("pointer: coarse") ? isCoarse : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

function isBefore(first: Element, second: Element): boolean {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
}

function line(san: string, pvSan: string[]): BestLine {
  return {
    san,
    uci: "e8d8",
    eval_cp: 120,
    pv_san: pvSan,
    pv_uci: ["e8d8", "c4f7", "d8c7"],
  };
}
