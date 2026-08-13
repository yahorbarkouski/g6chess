import { useCallback, useEffect, useMemo, useState } from "react";
import { fenAfterMoves, sanToSquares, tryApplyMove } from "../lib/chess";

export interface PreviewState {
  rootFen: string;
  lineMoves: string[];
  step: number;
  source: PreviewSource;
}

type PreviewSource = "engine" | "book";

export interface DiscoveryState {
  anchorPly: number;
  rootFen: string;
  moves: string[];
  currentStep: number;
}

interface UseAnalysisBoardOptions {
  baseFen: string | null;
  currentPly: number;
  baseHighlightedMove: string | null;
  onExitDiscovery?: (anchorPly: number) => void;
}

export function useAnalysisBoard({
  baseFen,
  currentPly,
  baseHighlightedMove,
  onExitDiscovery,
}: UseAnalysisBoardOptions) {
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryState | null>(null);

  const displayFen = useMemo(() => {
    if (preview) {
      return fenAfterMoves(preview.rootFen, preview.lineMoves, preview.step) ?? preview.rootFen;
    }
    if (discovery) {
      return (
        fenAfterMoves(discovery.rootFen, discovery.moves, discovery.currentStep) ??
        discovery.rootFen
      );
    }
    return baseFen;
  }, [baseFen, discovery, preview]);

  const boardFeedback = useMemo(() => {
    if (preview) {
      if (preview.step <= 0) {
        return null;
      }
      const moveSan = preview.lineMoves[preview.step - 1] ?? null;
      const fenBeforeStep =
        fenAfterMoves(preview.rootFen, preview.lineMoves, preview.step - 1) ?? preview.rootFen;
      const moveSquares = moveSan ? sanToSquares(fenBeforeStep, moveSan) : null;
      return {
        highlightedMove: moveSquares ? `${moveSquares[0]}${moveSquares[1]}` : null,
      };
    }

    if (discovery && discovery.currentStep > 0) {
      const moveSan = discovery.moves[discovery.currentStep - 1] ?? null;
      const fenBeforeStep =
        fenAfterMoves(discovery.rootFen, discovery.moves, discovery.currentStep - 1) ??
        discovery.rootFen;
      const moveSquares = moveSan ? sanToSquares(fenBeforeStep, moveSan) : null;
      return {
        highlightedMove: moveSquares ? `${moveSquares[0]}${moveSquares[1]}` : null,
      };
    }

    if (!baseHighlightedMove) {
      return null;
    }
    return {
      highlightedMove: baseHighlightedMove,
    };
  }, [baseHighlightedMove, discovery, preview]);

  const clearPreview = useCallback(() => {
    setPreview(null);
  }, []);

  const clearDiscovery = useCallback(() => {
    setDiscovery(null);
  }, []);

  const exitDiscovery = useCallback(() => {
    if (!discovery) {
      return;
    }
    const anchorPly = discovery.anchorPly;
    clearDiscovery();
    onExitDiscovery?.(anchorPly);
  }, [clearDiscovery, discovery, onExitDiscovery]);

  const handleDiscoveryStepClick = useCallback((step: number) => {
    setDiscovery((current) => (current ? { ...current, currentStep: step } : current));
  }, []);

  const stepInDiscovery = useCallback(
    (delta: number): boolean => {
      if (!discovery) {
        return false;
      }
      const nextStep = discovery.currentStep + delta;
      if (nextStep >= 0 && nextStep <= discovery.moves.length) {
        setDiscovery({ ...discovery, currentStep: nextStep });
        return true;
      }
      exitDiscovery();
      return false;
    },
    [discovery, exitDiscovery],
  );

  const handlePreview = useCallback(
    (rootFen: string, lineMoves: string[], step: number, source: PreviewSource = "engine") => {
      setPreview((current) => {
        if (
          current?.rootFen === rootFen &&
          current.step === step &&
          current.source === source &&
          current.lineMoves.length === lineMoves.length &&
          current.lineMoves.every((move, index) => move === lineMoves[index])
        ) {
          return null;
        }
        return { rootFen, lineMoves, step, source };
      });
    },
    [],
  );

  const handlePieceDrop = useCallback(
    ({
      sourceSquare,
      targetSquare,
      piece,
    }: {
      sourceSquare: string;
      targetSquare: string | null;
      piece: string;
    }): boolean => {
      if (!targetSquare || !baseFen) {
        return false;
      }

      const activeFen = discovery
        ? (fenAfterMoves(discovery.rootFen, discovery.moves, discovery.currentStep) ??
          discovery.rootFen)
        : preview
          ? (fenAfterMoves(preview.rootFen, preview.lineMoves, preview.step) ?? baseFen)
          : baseFen;

      const result = tryApplyMove(activeFen, sourceSquare, targetSquare, piece);
      if (!result) {
        return false;
      }

      if (!discovery) {
        if (preview) {
          const previewMoves = preview.lineMoves.slice(0, preview.step);
          setPreview(null);
          setDiscovery({
            anchorPly: currentPly,
            rootFen: preview.rootFen,
            moves: [...previewMoves, result.san],
            currentStep: previewMoves.length + 1,
          });
          return true;
        }

        setPreview(null);
        setDiscovery({
          anchorPly: currentPly,
          rootFen: activeFen,
          moves: [result.san],
          currentStep: 1,
        });
        return true;
      }

      const prefix = discovery.moves.slice(0, discovery.currentStep);
      setDiscovery({
        ...discovery,
        moves: [...prefix, result.san],
        currentStep: prefix.length + 1,
      });
      return true;
    },
    [baseFen, currentPly, discovery, preview],
  );

  useEffect(() => {
    if (!discovery) {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        exitDiscovery();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [discovery, exitDiscovery]);

  return {
    discovery,
    preview,
    displayFen,
    highlightedMove: boardFeedback?.highlightedMove ?? null,
    dimmed: Boolean(preview) || (discovery !== null && discovery.currentStep > 0),
    handlePieceDrop,
    handlePreview,
    handleDiscoveryStepClick,
    clearPreview,
    clearDiscovery,
    exitDiscovery,
    stepInDiscovery,
  };
}
