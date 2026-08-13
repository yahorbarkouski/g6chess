import { PieceType } from "@ultrachess/core";
import { Chess, type MoveInput, type VerboseMove } from "ultrachess/inline";
import type { BestLine, BoardSide } from "../types/analysis";

export interface UciInfoLine {
  depth: number;
  multipv: number;
  scoreCp: number | null;
  scoreMate: number | null;
  pv: string[];
}

const INFO_RE =
  /^info\s+.*depth\s+(\d+).*multipv\s+(\d+).*score\s+(cp|mate)\s+(-?\d+).*\bpv\s+(.+)$/;

const PROMOTION_PIECES = {
  q: PieceType.Queen,
  r: PieceType.Rook,
  b: PieceType.Bishop,
  n: PieceType.Knight,
} as const;

export function parseUciInfo(line: string): UciInfoLine | null {
  const match = INFO_RE.exec(line);
  if (!match) {
    return null;
  }
  const [, depth, multipv, scoreType, rawScoreValue, rawPv] = match;
  if (
    depth === undefined ||
    multipv === undefined ||
    scoreType === undefined ||
    rawScoreValue === undefined ||
    rawPv === undefined
  ) {
    return null;
  }
  const scoreValue = Number(rawScoreValue);
  return {
    depth: Number(depth),
    multipv: Number(multipv),
    scoreCp: scoreType === "cp" ? scoreValue : null,
    scoreMate: scoreType === "mate" ? scoreValue : null,
    pv: rawPv.trim().split(/\s+/),
  };
}

export function isUciOk(line: string): boolean {
  return line.trim() === "uciok";
}

export function isReadyOk(line: string): boolean {
  return line.trim() === "readyok";
}

export function uciInfoLinesToBestLines(
  fen: string,
  lines: UciInfoLine[],
  sideToMove: BoardSide,
): BestLine[] {
  return lines
    .map((info) => {
      const flip = sideToMove === "black" ? -1 : 1;
      const evalCp =
        info.scoreMate !== null ? mateScoreToCp(info.scoreMate) * flip : (info.scoreCp ?? 0) * flip;
      const pvSan = uciPvToSan(fen, info.pv);
      return {
        san: pvSan[0] ?? "",
        uci: info.pv[0] ?? "",
        eval_cp: evalCp,
        pv_san: pvSan,
        pv_uci: info.pv,
      };
    })
    .filter((line) => line.uci.length >= 4);
}

function mateScoreToCp(scoreMate: number): number {
  return scoreMate > 0 ? 30_000 - scoreMate * 100 : -30_000 - scoreMate * 100;
}

function uciPvToSan(fen: string, pvUci: string[]): string[] {
  const chess = Chess.createSync(fen);
  try {
    const sanMoves: string[] = [];
    for (const uci of pvUci) {
      const input = uciToMoveInput(uci);
      if (input === null) {
        break;
      }
      const packed = chess.moveFromInput(input);
      const verbose = chess.verboseMove(packed) as VerboseMove;
      sanMoves.push(verbose.san);
      chess.move(packed);
    }
    return sanMoves;
  } catch {
    return [];
  } finally {
    chess.dispose();
  }
}

function uciToMoveInput(uci: string): MoveInput | null {
  if (uci.length < 4) {
    return null;
  }
  const promotionChar = uci[4]?.toLowerCase();
  const promotion =
    promotionChar === undefined
      ? undefined
      : PROMOTION_PIECES[promotionChar as keyof typeof PROMOTION_PIECES];
  return {
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    ...(promotion === undefined ? {} : { promotion }),
  };
}
