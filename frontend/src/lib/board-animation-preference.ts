export const BOARD_ANIMATION_MS = { slow: 300, normal: 150, fast: 45 } as const;
export type BoardAnimationSpeed = keyof typeof BOARD_ANIMATION_MS;
export const DEFAULT_BOARD_ANIMATION_MS = BOARD_ANIMATION_MS.normal;

const STORAGE_KEY = "g6explanation.boardAnimationSpeed";

export function readBoardAnimationSpeed(): BoardAnimationSpeed {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "slow" || stored === "normal" || stored === "fast") {
      return stored;
    }
  } catch {}
  return "normal";
}

export function saveBoardAnimationSpeed(speed: BoardAnimationSpeed): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, speed);
  } catch {}
}
