import { useEffect, useRef } from "react";
import { triggerHaptic, warmupHaptics } from "./haptics";

const MOVE_SOUND_MIN_INTERVAL_MS = 14;
const MOVE_SOUND_POOL_SIZE = 4;
const MOVE_SOUND_VOLUME = 1;
const COARSE_POINTER_QUERY = "(hover: none), (pointer: coarse)";

function isCoarsePointer(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(COARSE_POINTER_QUERY).matches;
}

const CHESS_COM_SOUND_URLS = {
  moveSelf: "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-self.mp3",
  moveOpponent:
    "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-opponent.mp3",
  capture: "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/capture.mp3",
  castle: "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/castle.mp3",
  moveCheck: "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/move-check.mp3",
  promote: "https://images.chesscomfiles.com/chess-themes/sounds/_MP3_/default/promote.mp3",
} as const;

type MoveSoundKey = keyof typeof CHESS_COM_SOUND_URLS;

const MOVE_SOUND_HAPTIC: Record<MoveSoundKey, Parameters<typeof triggerHaptic>[0]> = {
  moveSelf: "selection",
  moveOpponent: "selection",
  capture: "medium",
  castle: "medium",
  moveCheck: "success",
  promote: "success",
};

function resolveMoveSoundKey(san: string | null, movedByPlayer: boolean): MoveSoundKey {
  if (!san) {
    return movedByPlayer ? "moveSelf" : "moveOpponent";
  }
  if (san.includes("#") || san.includes("+")) {
    return "moveCheck";
  }
  if (san.startsWith("O-O") || san.startsWith("0-0")) {
    return "castle";
  }
  if (san.includes("=")) {
    return "promote";
  }
  if (san.includes("x")) {
    return "capture";
  }
  return movedByPlayer ? "moveSelf" : "moveOpponent";
}

function unlockAudioPool(audios: HTMLAudioElement[]): void {
  for (const audio of audios) {
    const previousVolume = audio.volume;
    audio.muted = true;
    audio.volume = 0;
    const playResult = audio.play();
    if (playResult instanceof Promise) {
      playResult
        .then(() => {
          audio.pause();
          audio.currentTime = 0;
          audio.muted = false;
          audio.volume = previousVolume;
        })
        .catch(() => {
          audio.muted = false;
          audio.volume = previousVolume;
        });
    } else {
      audio.pause();
      audio.currentTime = 0;
      audio.muted = false;
      audio.volume = previousVolume;
    }
  }
}

export function useChessComMoveSound(
  positionKey: string | null | undefined,
  san: string | null,
  movedByPlayer: boolean,
) {
  const poolsRef = useRef<Record<MoveSoundKey, HTMLAudioElement[]> | null>(null);
  const indicesRef = useRef<Record<MoveSoundKey, number> | null>(null);
  const lastPositionRef = useRef<string | null>(null);
  const lastPlayAtRef = useRef(0);
  const audioEnabledRef = useRef(false);

  useEffect(() => {
    const audioEnabled = !isCoarsePointer();
    audioEnabledRef.current = audioEnabled;

    if (audioEnabled) {
      const createPool = (url: string) =>
        Array.from({ length: MOVE_SOUND_POOL_SIZE }, () => {
          const audio = new Audio(url);
          audio.preload = "auto";
          audio.volume = MOVE_SOUND_VOLUME;
          return audio;
        });

      poolsRef.current = {
        moveSelf: createPool(CHESS_COM_SOUND_URLS.moveSelf),
        moveOpponent: createPool(CHESS_COM_SOUND_URLS.moveOpponent),
        capture: createPool(CHESS_COM_SOUND_URLS.capture),
        castle: createPool(CHESS_COM_SOUND_URLS.castle),
        moveCheck: createPool(CHESS_COM_SOUND_URLS.moveCheck),
        promote: createPool(CHESS_COM_SOUND_URLS.promote),
      };

      indicesRef.current = {
        moveSelf: 0,
        moveOpponent: 0,
        capture: 0,
        castle: 0,
        moveCheck: 0,
        promote: 0,
      };
    }

    let unlocked = false;
    const unlock = () => {
      if (unlocked) {
        return;
      }
      unlocked = true;
      warmupHaptics();
      if (audioEnabled) {
        const pools = poolsRef.current;
        if (pools) {
          for (const audios of Object.values(pools)) {
            unlockAudioPool(audios);
          }
        }
      }
      window.removeEventListener("pointerdown", unlock, true);
      window.removeEventListener("touchstart", unlock, true);
      window.removeEventListener("keydown", unlock, true);
    };
    window.addEventListener("pointerdown", unlock, { capture: true, passive: true });
    window.addEventListener("touchstart", unlock, { capture: true, passive: true });
    window.addEventListener("keydown", unlock, { capture: true });

    return () => {
      poolsRef.current = null;
      indicesRef.current = null;
      audioEnabledRef.current = false;
      window.removeEventListener("pointerdown", unlock, true);
      window.removeEventListener("touchstart", unlock, true);
      window.removeEventListener("keydown", unlock, true);
    };
  }, []);

  useEffect(() => {
    if (!positionKey) {
      return;
    }

    const previousPosition = lastPositionRef.current;
    lastPositionRef.current = positionKey;

    if (!previousPosition || previousPosition === positionKey) {
      return;
    }

    const nowMs = performance.now();
    if (nowMs - lastPlayAtRef.current < MOVE_SOUND_MIN_INTERVAL_MS) {
      return;
    }
    lastPlayAtRef.current = nowMs;

    const key = resolveMoveSoundKey(san, movedByPlayer);
    triggerHaptic(MOVE_SOUND_HAPTIC[key]);

    if (!audioEnabledRef.current) {
      return;
    }

    const pools = poolsRef.current;
    const indices = indicesRef.current;
    if (!pools || !indices) {
      return;
    }

    const pool = pools[key];
    if (!pool.length) {
      return;
    }

    indices[key] = (indices[key] + 1) % pool.length;
    const audio = pool[indices[key]];
    if (!audio) {
      return;
    }
    audio.volume = MOVE_SOUND_VOLUME;
    audio.currentTime = 0;
    void audio.play().catch(() => undefined);
  }, [movedByPlayer, positionKey, san]);
}
