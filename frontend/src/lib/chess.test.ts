import { describe, expect, it } from "vitest";
import { formatEvalLong, parseMateFromCp } from "./chess";

describe("parseMateFromCp", () => {
  it("preserves exact backend mate distances", () => {
    expect(parseMateFromCp(99_995)).toBe(5);
    expect(parseMateFromCp(99_996)).toBe(4);
    expect(parseMateFromCp(-99_996)).toBe(-4);
  });

  it("preserves exact browser Stockfish mate distances", () => {
    expect(parseMateFromCp(29_500)).toBe(5);
    expect(parseMateFromCp(29_600)).toBe(4);
    expect(parseMateFromCp(-29_600)).toBe(-4);
  });
});

describe("formatEvalLong", () => {
  it("formats backend mate distances without halving them", () => {
    expect(formatEvalLong(99_995)).toBe("Mate in 5");
    expect(formatEvalLong(99_996)).toBe("Mate in 4");
  });
});
