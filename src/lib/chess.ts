import { type BoardModel, PieceType, type SquareIndex } from "@ultrachess/core";
import { Chess, Color, type MoveInput, type VerboseMove } from "ultrachess/inline";
import type { BoardSide, CapturedPieces, MaterialInfo } from "../types/analysis";

export const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
export const ENGINE_ARROW_COLORS = [
  "rgba(56, 189, 248, 0.62)",
  "rgba(16, 185, 129, 0.52)",
  "rgba(250, 204, 21, 0.48)",
] as const;
export const MAIA_ARROW_COLOR = "rgba(236, 72, 153, 0.48)";

const STARTING_COUNTS = {
  p: 8,
  n: 2,
  b: 2,
  r: 2,
  q: 1,
} as const;

const PIECE_VALUE = {
  p: 1,
  n: 3,
  b: 3,
  r: 5,
  q: 9,
} as const;

const SCORED_PIECES = ["q", "r", "b", "n", "p"] as const;
const PIECE_TYPE_TO_CHAR = ["p", "n", "b", "r", "q", "k"] as const;

export function uciToSquares(uci: string): [string, string] | null {
  if (uci.length < 4) {
    return null;
  }
  return [uci.slice(0, 2), uci.slice(2, 4)];
}

export function squareName(square: SquareIndex): string {
  const file = Number(square) % 8;
  const rank = Math.floor(Number(square) / 8) + 1;
  return `${String.fromCharCode("a".charCodeAt(0) + file)}${rank}`;
}

function getSafeFen(fen: string | null | undefined): string {
  if (!fen || fen === "start") {
    return START_FEN;
  }
  try {
    withChess(fen, () => undefined);
    return fen;
  } catch {
    return START_FEN;
  }
}

export function sideToMoveFromFen(fen: string): BoardSide {
  return withChess(getSafeFen(fen), (chess) => (chess.turn() === Color.White ? "white" : "black"));
}

export function sanToSquares(fen: string, san: string): [string, string] | null {
  return withChess(getSafeFen(fen), (chess) => {
    try {
      const packed = chess.parseSan(san);
      const verbose = chess.verboseMove(packed) as VerboseMove;
      return [verbose.from, verbose.to];
    } catch {
      return null;
    }
  });
}

export function fenAfterMoves(rootFen: string, moves: string[], count: number): string | null {
  return withChess(getSafeFen(rootFen), (chess) => {
    try {
      for (let index = 0; index < count; index += 1) {
        const move = moves[index];
        if (move === undefined) {
          return null;
        }
        chess.move(move);
      }
      return chess.fen();
    } catch {
      return null;
    }
  });
}

export function tryApplyMove(
  fen: string,
  sourceSquare: string,
  targetSquare: string,
  piece = "",
): { san: string; uci: string } | null {
  return withChess(getSafeFen(fen), (chess) => {
    try {
      const sourcePiece = pieceAtSquareFromFen(fen, sourceSquare) ?? piece;
      const isPromotion =
        sourcePiece[1]?.toLowerCase() === "p" &&
        (targetSquare.endsWith("1") || targetSquare.endsWith("8"));
      const input: MoveInput = isPromotion
        ? { from: sourceSquare, to: targetSquare, promotion: PieceType.Queen }
        : { from: sourceSquare, to: targetSquare };
      const packed = chess.moveFromInput(input);
      const verbose = chess.verboseMove(packed) as VerboseMove;
      chess.move(packed);
      return { san: verbose.san, uci: verbose.uci };
    } catch {
      return null;
    }
  });
}

function pieceAtSquareFromFen(fen: string, square: string): string | null {
  const placement = getSafeFen(fen).split(" ")[0] ?? "";
  const fileIndex = square.charCodeAt(0) - "a".charCodeAt(0);
  const rank = Number.parseInt(square[1] ?? "", 10);
  if (fileIndex < 0 || fileIndex > 7 || rank < 1 || rank > 8) {
    return null;
  }

  const targetRankIndex = 8 - rank;
  const rows = placement.split("/");
  const row = rows[targetRankIndex];
  if (!row) {
    return null;
  }

  let file = 0;
  for (const char of row) {
    if (/\d/.test(char)) {
      file += Number(char);
      continue;
    }
    if (file === fileIndex) {
      const color = char === char.toUpperCase() ? "w" : "b";
      return `${color}${char.toUpperCase()}`;
    }
    file += 1;
  }
  return null;
}

export function pieceCodeAtSquare(model: BoardModel, square: SquareIndex): string {
  const cell = model.getSnapshot().board[square] ?? 0;
  if (cell === 0) {
    return "";
  }
  const colorChar = cell <= 6 ? "w" : "b";
  const typeIndex = (cell - 1) % 6;
  const typeChar = PIECE_TYPE_TO_CHAR[typeIndex] ?? "";
  return colorChar + typeChar.toUpperCase();
}

export function computeCapturedMaterial(fen: string): MaterialInfo {
  const placement = (fen || START_FEN).split(" ")[0] ?? "";
  const onBoard = {
    w: emptyPieceCounts(),
    b: emptyPieceCounts(),
  };

  for (const char of placement) {
    const lower = char.toLowerCase();
    if (isScoredPiece(lower)) {
      const side = char === lower ? "b" : "w";
      onBoard[side][lower] += 1;
    }
  }

  const white = capturedPieces(onBoard.b);
  const black = capturedPieces(onBoard.w);
  return { white, black, advantage: materialValue(white) - materialValue(black) };
}

export function formatClock(totalSeconds?: number | null): string {
  if (totalSeconds == null) {
    return "--";
  }
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatEval(cp: number | null): string {
  if (cp === null) {
    return "--";
  }
  const mate = parseMateFromCp(cp);
  if (mate !== null) {
    const n = Math.abs(mate);
    return n === 0 ? (cp >= 0 ? "+M" : "-M") : cp >= 0 ? `+M${n}` : `-M${n}`;
  }
  const sign = cp >= 0 ? "+" : "";
  return `${sign}${(cp / 100).toFixed(2)}`;
}

export function formatEvalLong(cp: number | null): string {
  if (cp === null) {
    return "Evaluation unavailable";
  }
  const mate = parseMateFromCp(cp);
  if (mate !== null) {
    const n = Math.abs(mate);
    return n === 0 ? "Mate" : `Mate in ${n}`;
  }
  const sign = cp >= 0 ? "+" : "";
  return `${sign}${(cp / 100).toFixed(2)}`;
}

function withChess<T>(fen: string, fn: (chess: Chess) => T): T {
  const chess = Chess.createSync(fen);
  try {
    return fn(chess);
  } finally {
    chess.dispose();
  }
}

function emptyPieceCounts() {
  return { p: 0, n: 0, b: 0, r: 0, q: 0 };
}

function isScoredPiece(piece: string): piece is keyof typeof PIECE_VALUE {
  return piece === "p" || piece === "n" || piece === "b" || piece === "r" || piece === "q";
}

function capturedPieces(onBoard: ReturnType<typeof emptyPieceCounts>): CapturedPieces {
  return {
    q: Math.max(0, STARTING_COUNTS.q - onBoard.q),
    r: Math.max(0, STARTING_COUNTS.r - onBoard.r),
    b: Math.max(0, STARTING_COUNTS.b - onBoard.b),
    n: Math.max(0, STARTING_COUNTS.n - onBoard.n),
    p: Math.max(0, STARTING_COUNTS.p - onBoard.p),
  };
}

function materialValue(pieces: CapturedPieces): number {
  let total = 0;
  for (const piece of SCORED_PIECES) {
    total += pieces[piece] * PIECE_VALUE[piece];
  }
  return total;
}

export function parseMateFromCp(cp: number): number | null {
  const abs = Math.abs(cp);
  if (abs >= 90000) {
    const plies = 100000 - abs;
    const moves = plies <= 0 ? 0 : Math.max(1, Math.floor((plies + 1) / 2));
    return cp > 0 ? moves : -moves;
  }
  if (abs >= 20000) {
    const n = Math.round((30000 - abs) / 100);
    return cp > 0 ? n : -n;
  }
  return null;
}
