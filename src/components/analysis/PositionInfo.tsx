import { BorderBeam } from "border-beam";
import { useReducedMotion } from "framer-motion";
import { ArrowRight, ChevronRight, X } from "lucide-react";
import {
  type FocusEvent,
  Fragment,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { toast } from "sonner";
import { TextShimmer } from "@/components/loading-ui/text-shimmer";
import { analysisTagLabel, primaryClassClass, primaryClassLabel } from "../../lib/analysis-format";
import { fenAfterMoves, sanToSquares, sideToMoveFromFen } from "../../lib/chess";
import { triggerHaptic } from "../../lib/haptics";
import { cn } from "../../lib/utils";
import type {
  AnalysisMoveMarker,
  BoardSide,
  ExplanationHighlightColor,
  ExplanationLineCard,
  ExplanationSegment,
  GameMove,
} from "../../types/analysis";
import { Badge } from "../ui/badge";
import { MorphText } from "../ui/morph-text";
import { SanMove } from "./EngineLinesView";
import { UltraAnalysisBoard } from "./UltraAnalysisBoard";

interface PositionInfoProps {
  currentMove: GameMove | null;
  selectedMarker: AnalysisMoveMarker | null;
  rootFen?: string | null;
  boardOrientation?: BoardSide | null;
  emptyMessage?: string | null;
  emptyMessageClassName?: string;
  emptyMessageVariant?: "plain" | "shimmer";
  openingName?: string | null;
  onMoveClick?: (rootFen: string, moves: string[], step: number) => void;
  moves?: GameMove[];
  currentPly?: number;
  className?: string;
}

const SAN_PATTERN = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b/g;
const SHOW_ENGINE_DETAIL_PANEL: boolean = false;
type LineCardMoveClick = (rootFen: string, moves: string[], step: number) => void;

export function PositionInfo({
  currentMove,
  selectedMarker,
  rootFen = null,
  boardOrientation = null,
  emptyMessage = null,
  emptyMessageClassName,
  emptyMessageVariant = "plain",
  openingName = null,
  onMoveClick,
  moves,
  currentPly,
  className,
}: PositionInfoProps) {
  const explanationContent = useMemo(() => {
    if (!selectedMarker || !rootFen) {
      return null;
    }
    return renderExplanationContent(selectedMarker, rootFen, boardOrientation, onMoveClick);
  }, [boardOrientation, onMoveClick, rootFen, selectedMarker]);
  const selectedMoveBadge = selectedMarker
    ? selectedMoveBadgeContent(selectedMarker, openingName)
    : null;
  const selectedMoveBeam = selectedMarker ? moveBeamVariant(selectedMarker) : null;
  const canCopyMoves = Boolean(moves?.length && currentPly && currentPly > 0);
  const handleCopyMoves = useCallback(() => {
    if (!moves || !currentPly) {
      return;
    }
    const moveText = movesToMoveText(moves, currentPly);
    if (!moveText) {
      return;
    }
    void navigator.clipboard?.writeText(moveText).then(() => {
      toast.success("Moves copied to clipboard");
    });
  }, [currentPly, moves]);
  const moveTitle = formatMoveLabel(currentMove);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          {canCopyMoves ? (
            <button
              aria-label={`Copy moves through ${moveTitle}`}
              className="cursor-pointer border-0 bg-transparent p-0 text-left font-serif text-2xl text-stone-900 transition-colors hover:text-stone-600 focus-visible:rounded-sm dark:text-stone-100 dark:hover:text-stone-300"
              onClick={handleCopyMoves}
              title="Copy moves to clipboard"
              type="button"
            >
              <MorphText>{moveTitle}</MorphText>
            </button>
          ) : (
            <div className="font-serif text-2xl text-stone-900 dark:text-stone-100">
              <MorphText>{moveTitle}</MorphText>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {selectedMoveBadge ? (
            <SelectedMoveBadge badge={selectedMoveBadge} beamVariant={selectedMoveBeam} />
          ) : null}
        </div>
      </div>

      {explanationContent ? (
        <div className="mt-2 text-sm leading-relaxed text-stone-600 text-pretty dark:text-stone-400">
          {explanationContent}
        </div>
      ) : emptyMessage ? (
        emptyMessageVariant === "shimmer" ? (
          <TextShimmer
            as="p"
            className={cn(
              "mt-2 text-sm leading-relaxed text-stone-500 text-pretty dark:text-stone-400",
              emptyMessageClassName,
            )}
          >
            {emptyMessage}
          </TextShimmer>
        ) : (
          <p
            className={cn(
              "mt-2 text-sm leading-relaxed text-stone-500 text-pretty dark:text-stone-400",
              emptyMessageClassName,
            )}
          >
            {emptyMessage}
          </p>
        )
      ) : null}

      {SHOW_ENGINE_DETAIL_PANEL ? <AnalysisMarkerStack marker={selectedMarker} /> : null}
    </div>
  );
}

interface SelectedMoveBadgeContent {
  label: string;
  className: string;
  icon?: ReactNode;
}

function SelectedMoveBadge({
  badge,
  beamVariant,
}: {
  badge: SelectedMoveBadgeContent;
  beamVariant: "beautiful" | "brilliant" | null;
}) {
  const content = (
    <Badge className={cn("min-h-0 rounded border px-2 py-1", badge.className)}>
      {badge.icon}
      {badge.label}
    </Badge>
  );

  if (beamVariant === null) {
    return content;
  }

  return (
    <BorderBeam
      borderRadius={4}
      brightness={1.05}
      className="inline-flex rounded [&_[data-beam-bloom]]:hidden"
      colorVariant={beamVariant === "brilliant" ? "colorful" : "ocean"}
      duration={1.96}
      size="sm"
      strength={0.48}
      theme="auto"
    >
      {content}
    </BorderBeam>
  );
}

function movesToMoveText(moves: GameMove[], upToPly: number): string {
  const parts: string[] = [];
  for (const move of moves) {
    if (move.ply > upToPly) {
      break;
    }
    if (move.side === "white") {
      parts.push(`${move.move_number}. ${move.san}`);
    } else {
      parts.push(move.san);
    }
  }
  return parts.join(" ");
}

function selectedMoveBadgeContent(
  marker: AnalysisMoveMarker,
  openingName: string | null,
): SelectedMoveBadgeContent | null {
  if (marker.tags.includes("forced")) {
    return {
      label: "Forced",
      className: "border-none bg-stone-200 text-stone-600 dark:bg-stone-700 dark:text-stone-300",
      icon: <ArrowRight className="mr-1 inline size-3" />,
    };
  }

  if (marker.primary_class === "book" && openingName) {
    return {
      label: openingNameBase(openingName),
      className: primaryClassClass(marker.primary_class),
    };
  }

  return {
    label: primaryClassLabel(marker.primary_class),
    className: primaryClassClass(marker.primary_class),
  };
}

function moveBeamVariant(marker: AnalysisMoveMarker): "beautiful" | "brilliant" | null {
  const beautyLabel = normalizedMeta(marker, "beauty_label");
  if (beautyLabel === "brilliant" || beautyLabel === "beautiful") {
    return beautyLabel;
  }

  return null;
}

function AnalysisMarkerStack({ marker }: { marker: AnalysisMoveMarker | null }) {
  const [open, setOpen] = useState(false);

  if (!marker) {
    return null;
  }

  const rows = detailRows(marker);
  const mainPoint = stringMeta(marker, "main_point_claim");
  const keyReason = stringMeta(marker, "best_or_key_reason");
  const allowedClaims = stringArrayMeta(marker, "allowed_claims").slice(0, 4);

  const scoreRows = [
    { label: "Before", value: formatCp(marker.eval_before_cp) },
    { label: "After", value: formatCp(marker.eval_after_cp) },
    { label: "Loss", value: `${marker.drop_cp} cp` },
  ];

  return (
    <div className="mt-3 space-y-3 border-stone-200 pt-2 dark:border-stone-800">
      <section>
        <button
          className="flex w-full cursor-pointer items-center gap-1 text-left"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          <ChevronRight
            className={cn(
              "size-3.5 text-stone-400 transition-transform duration-150 dark:text-stone-500",
              open && "rotate-90",
            )}
          />
          <h3 className="font-serif text-sm text-stone-900 dark:text-stone-100">
            Engine detail (this moment)
          </h3>
        </button>
        {open ? (
          <div className="mt-1.5 space-y-3">
            {marker.tags.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {marker.tags.map((tag) => (
                  <Badge
                    className="min-h-0 border-stone-200 bg-white px-2 py-1 text-stone-700 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-200"
                    key={tag}
                  >
                    {analysisTagLabel(tag)}
                  </Badge>
                ))}
              </div>
            ) : null}
            {mainPoint ? (
              <div className="space-y-1.5 rounded bg-stone-100/70 px-2 py-2 dark:bg-stone-800/40">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-stone-400 dark:text-stone-500">
                  Deterministic context
                </div>
                <p className="text-xs leading-relaxed text-stone-700 text-pretty dark:text-stone-300">
                  {mainPoint}
                </p>
                {keyReason ? (
                  <p className="text-xs leading-relaxed text-stone-500 text-pretty dark:text-stone-400">
                    {keyReason}
                  </p>
                ) : null}
              </div>
            ) : null}
            <div className="space-y-1.5 text-xs">
              {scoreRows.map((row) => (
                <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" key={row.label}>
                  <span className="font-medium text-stone-500 dark:text-stone-400">
                    {row.label}
                  </span>
                  <span className="font-mono text-stone-800 tabular-nums dark:text-stone-200">
                    <MorphText>{row.value}</MorphText>
                  </span>
                </div>
              ))}
              {rows.map((row) => (
                <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" key={row.label}>
                  <span className="font-medium text-stone-500 dark:text-stone-400">
                    {row.label}
                  </span>
                  <span className="max-w-48 truncate text-right font-mono text-stone-800 tabular-nums dark:text-stone-200">
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
            {allowedClaims.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {allowedClaims.map((claim) => (
                  <Badge
                    className="min-h-0 border-stone-200 bg-stone-50 px-2 py-1 text-stone-600 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300"
                    key={claim}
                  >
                    {claim}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function detailRows(marker: AnalysisMoveMarker): Array<{ label: string; value: string }> {
  return [
    row("Quality", primaryClassLabel(marker.primary_class)),
    row(
      "Significance",
      labelWithScore(
        stringMeta(marker, "significance_label"),
        numberMeta(marker, "significance_score"),
      ),
    ),
    row(
      "Beauty",
      labelWithScore(stringMeta(marker, "beauty_label"), numberMeta(marker, "beauty_score")),
    ),
    row("Phase", stringMeta(marker, "phase")),
    row("Best/key", stringMeta(marker, "best_or_key_move") ?? marker.best_move_san ?? null),
    row("Natural", marker.natural_move_san ?? null),
    row("Legal moves", formatNumber(numberMeta(marker, "legal_move_count"))),
    row("Depth", formatNumber(numberMeta(marker, "engine_depth"))),
    row("Nodes", formatCompactNumber(numberMeta(marker, "engine_nodes"))),
    row("Context", formatSeconds(numberMeta(marker, "context_latency_seconds"))),
    row("Wording", wordingSource(marker)),
  ].filter((item): item is { label: string; value: string } => item !== null);
}

function row(label: string, value: string | null): { label: string; value: string } | null {
  return value ? { label, value } : null;
}

function wordingSource(marker: AnalysisMoveMarker): string {
  const model = stringMeta(marker, "explanation_model");
  if (model) {
    return `LLM ${model.replace("openai/", "")}`;
  }
  return "Deterministic";
}

function labelWithScore(label: string | null, score: number | null): string | null {
  if (!label && score === null) {
    return null;
  }
  if (score === null) {
    return label;
  }
  return `${label ?? "score"} ${score.toFixed(2)}`;
}

function stringMeta(marker: AnalysisMoveMarker, key: string): string | null {
  const value = marker.label_metadata[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizedMeta(marker: AnalysisMoveMarker, key: string): string | null {
  return stringMeta(marker, key)?.trim().toLowerCase() ?? null;
}

function numberMeta(marker: AnalysisMoveMarker, key: string): number | null {
  const value = marker.label_metadata[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringArrayMeta(marker: AnalysisMoveMarker, key: string): string[] {
  const value = marker.label_metadata[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function formatNumber(value: number | null): string | null {
  return value === null ? null : String(value);
}

function formatCompactNumber(value: number | null): string | null {
  return value === null ? null : new Intl.NumberFormat("en", { notation: "compact" }).format(value);
}

function formatSeconds(value: number | null): string | null {
  return value === null ? null : `${value.toFixed(2)}s`;
}

function renderExplanationContent(
  marker: AnalysisMoveMarker,
  rootFen: string,
  boardOrientation: BoardSide | null,
  onMoveClick?: (rootFen: string, moves: string[], step: number) => void,
): ReactNode {
  const cardsById = new Map(marker.explanation_line_cards.map((card) => [card.id, card]));
  const segments =
    marker.explanation_segments.length > 0
      ? marker.explanation_segments
      : [
          {
            text: marker.explanation,
            line_card_id: null,
            line_card_anchor: null,
            highlight_color: null,
          },
        ];
  const renderedSegments = segments.map((segment, index) => ({
    key: `${segment.line_card_id ?? "text"}-${segment.text}`,
    needsLeadingSpace: index > 0,
    segment,
  }));

  return renderedSegments.map(({ key, needsLeadingSpace, segment }) => {
    const card = segment.line_card_id ? cardsById.get(segment.line_card_id) : null;
    return (
      <Fragment key={key}>
        {needsLeadingSpace ? " " : null}
        {card
          ? renderLineCardSegment({
              boardOrientation,
              card,
              marker,
              onMoveClick,
              rootFen,
              segment,
            })
          : parseExplanationWithMoves(segment.text, marker, rootFen, onMoveClick)}
      </Fragment>
    );
  });
}

function renderLineCardSegment({
  boardOrientation,
  card,
  marker,
  onMoveClick,
  rootFen,
  segment,
}: {
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  marker: AnalysisMoveMarker;
  onMoveClick: LineCardMoveClick | undefined;
  rootFen: string;
  segment: ExplanationSegment;
}): ReactNode {
  const anchor = segment.line_card_anchor;
  const highlightColor =
    segment.highlight_color ?? lineCardFallbackHighlightColor(marker, segment, card);
  if (!anchor || !segment.text.includes(anchor)) {
    return (
      <LineCardAnchor
        boardOrientation={boardOrientation}
        card={card}
        onMoveClick={onMoveClick}
        rootFen={rootFen}
        highlightColor={highlightColor}
        triggerText={segment.text}
      />
    );
  }

  const start = segment.text.indexOf(anchor);
  const before = segment.text.slice(0, start);
  const after = segment.text.slice(start + anchor.length);

  return (
    <>
      {parseExplanationWithMoves(before, marker, rootFen, onMoveClick)}
      <LineCardAnchor
        boardOrientation={boardOrientation}
        card={card}
        onMoveClick={onMoveClick}
        rootFen={rootFen}
        highlightColor={highlightColor}
        triggerText={anchor}
      />
      {parseExplanationWithMoves(after, marker, rootFen, onMoveClick)}
    </>
  );
}

function LineCardAnchor({
  boardOrientation,
  card,
  onMoveClick,
  rootFen,
  highlightColor,
  triggerText,
}: {
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  onMoveClick: ((rootFen: string, moves: string[], step: number) => void) | undefined;
  rootFen: string;
  highlightColor: ExplanationHighlightColor;
  triggerText: string;
}) {
  const isCoarsePointer = useCoarsePointer();
  const [hoverCardOpen, setHoverCardOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const canPreview = onMoveClick !== undefined && card.moves.length > 0;
  const clearCloseTimer = () => {
    if (closeTimerRef.current === null) {
      return;
    }
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  };
  const openHoverCard = () => {
    clearCloseTimer();
    setHoverCardOpen(true);
  };
  const closeHoverCardSoon = () => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setHoverCardOpen(false);
      closeTimerRef.current = null;
    }, 180);
  };
  const closeHoverCard = () => {
    clearCloseTimer();
    setHoverCardOpen(false);
  };
  const handleRootBlur = (event: FocusEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return;
    }
    closeHoverCard();
  };
  const handleClick = () => {
    if (isCoarsePointer) {
      triggerHaptic("medium");
      setDialogOpen(true);
      return;
    }
    if (canPreview) {
      onMoveClick(rootFen, card.moves, card.moves.length);
    }
  };

  const closeDialog = () => {
    triggerHaptic("nudge");
    setDialogOpen(false);
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    handleClick();
  };
  const showHoverCard = hoverCardOpen && !isCoarsePointer;

  useEffect(
    () => () => {
      if (closeTimerRef.current === null) {
        return;
      }
      window.clearTimeout(closeTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    if (dialogOpen) {
      dialogRef.current?.focus();
    }
  }, [dialogOpen]);

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: the role=button text span is the actual control; this wrapper keeps its hover preview interactive.
    <div
      className="relative inline align-baseline"
      onBlur={handleRootBlur}
      onFocus={openHoverCard}
      onPointerEnter={openHoverCard}
      onPointerLeave={closeHoverCardSoon}
    >
      {/* biome-ignore lint/a11y/useSemanticElements: native buttons are atomic in line layout here; this inline trigger must fragment so the highlight background wraps with text. */}
      <span
        aria-label={`${triggerText}: ${card.title}`}
        className={cn(
          "inline cursor-pointer whitespace-normal box-decoration-clone rounded-sm px-0.5 py-0.5 text-left text-sm transition-colors",
          lineCardHighlightClass(highlightColor),
        )}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
      >
        {triggerText}
      </span>
      {showHoverCard ? (
        <LineCardPreviewShell
          boardOrientation={boardOrientation}
          card={card}
          onMoveClick={onMoveClick}
          onPointerEnter={openHoverCard}
          rootFen={rootFen}
        />
      ) : null}
      {dialogOpen ? (
        <div
          aria-label={card.title}
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-end justify-center bg-stone-950/35 p-3 backdrop-blur-[2px] outline-none sm:items-center"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeDialog();
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              closeDialog();
            }
          }}
          ref={dialogRef}
          role="dialog"
          tabIndex={-1}
        >
          <div className="relative w-full max-w-sm rounded-lg border border-stone-200 bg-white p-3 shadow-[0_24px_70px_rgba(28,25,23,0.28)] dark:border-stone-700 dark:bg-stone-900">
            <div className="absolute top-2 right-2 z-10">
              <button
                aria-label="Close line preview"
                className="flex size-7 items-center justify-center rounded text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-200"
                onClick={closeDialog}
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>
            <LineCardPreview
              active
              boardOrientation={boardOrientation}
              card={card}
              onMoveClick={onMoveClick}
              rootFen={rootFen}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LineCardPreviewShell({
  boardOrientation,
  card,
  onMoveClick,
  onPointerEnter,
  rootFen,
}: {
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  onMoveClick: LineCardMoveClick | undefined;
  onPointerEnter: () => void;
  rootFen: string;
}) {
  return (
    <div
      className="absolute top-full left-1/2 z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] -translate-x-1/2 whitespace-normal rounded-lg border border-stone-200 bg-white p-2.5 text-left shadow-[0_18px_45px_rgba(28,25,23,0.18),0_1px_0_rgba(255,255,255,0.8)_inset] sm:w-80 dark:border-stone-700 dark:bg-stone-900 dark:shadow-[0_18px_45px_rgba(0,0,0,0.4)]"
      onPointerEnter={onPointerEnter}
    >
      <LineCardPreview
        active
        boardOrientation={boardOrientation}
        card={card}
        onMoveClick={onMoveClick}
        rootFen={rootFen}
      />
    </div>
  );
}

function LineCardPreview({
  active,
  boardOrientation,
  card,
  onMoveClick,
  rootFen,
}: {
  active: boolean;
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  onMoveClick: LineCardMoveClick | undefined;
  rootFen: string;
}) {
  const prefersReducedMotion = useReducedMotion();
  const [step, setStep] = useState(prefersReducedMotion ? card.moves.length : 0);
  const [userPaused, setUserPaused] = useState(false);
  const displayStep = prefersReducedMotion ? card.moves.length : step;
  const currentFen = fenAfterMoves(rootFen, card.moves, displayStep) ?? rootFen;
  const highlightedMove = lineStepSquares(rootFen, card.moves, displayStep);
  const firstMoveSide = sideToMoveFromFen(rootFen);
  const orientation = boardOrientation ?? firstMoveSide;

  useEffect(() => {
    if (!active || userPaused) {
      return;
    }
    if (prefersReducedMotion) {
      setStep(card.moves.length);
      return;
    }
    setStep(0);
    const timer = window.setInterval(() => {
      setStep((current) => (current + 1) % (card.moves.length + 1));
    }, 850);
    return () => window.clearInterval(timer);
  }, [active, card.moves.length, prefersReducedMotion, userPaused]);

  return (
    <div className="space-y-2.5" data-testid="line-card-preview">
      <span className="block pr-8 text-[10px] font-semibold tracking-wide text-stone-500 uppercase dark:text-stone-400">
        {card.title}
      </span>
      <div className="min-w-0 overflow-hidden border border-stone-200 bg-stone-100 dark:border-stone-700 dark:bg-stone-800">
        <UltraAnalysisBoard
          allowDrawingArrows={false}
          animationMs={prefersReducedMotion ? 0 : 180}
          className="rounded-none shadow-none"
          fen={currentFen}
          highlightedMove={highlightedMove}
          orientation={orientation}
          shadowed={false}
          showCoordinates={false}
        />
      </div>
      <span className="block text-xs leading-relaxed text-stone-700 text-pretty dark:text-stone-300">
        {card.why}
      </span>
      <span className="scrollbar-hide flex flex-wrap items-center gap-1 overflow-x-auto">
        {card.moves.map((move, index) => {
          const moveStep = index + 1;
          const activeMove = displayStep === moveStep;
          const moveSide = index % 2 === 0 ? firstMoveSide : otherBoardSide(firstMoveSide);
          const content = <SanMove san={move} side={moveSide} />;
          const className = cn(
            "inline-flex shrink-0 items-center rounded border px-1 py-0.5 transition-colors",
            activeMove
              ? "border-amber-300 bg-amber-100 dark:border-amber-700 dark:bg-amber-900/50"
              : "border-stone-200 bg-white/60 dark:border-stone-700 dark:bg-stone-900/60",
            onMoveClick
              ? "cursor-pointer hover:border-stone-300 hover:bg-stone-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-500/50 dark:hover:border-stone-600 dark:hover:bg-stone-800"
              : null,
          );
          const key = `${card.id}-${card.moves.slice(0, moveStep).join(" ")}`;
          if (onMoveClick) {
            return (
              <button
                className={className}
                key={key}
                onClick={() => {
                  setUserPaused(true);
                  setStep(moveStep);
                  triggerHaptic("selection");
                  onMoveClick(rootFen, card.moves, moveStep);
                }}
                type="button"
              >
                {content}
              </button>
            );
          }
          return (
            <span className={className} key={key}>
              {content}
            </span>
          );
        })}
      </span>
    </div>
  );
}

function lineCardHighlightClass(color: ExplanationHighlightColor): string {
  switch (color) {
    case "red":
      return "bg-red-50/85 text-red-950 hover:bg-red-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-500/50 dark:bg-red-950/50 dark:text-red-100 dark:hover:bg-red-900/55";
    case "orange":
      return "bg-orange-50/85 text-orange-950 hover:bg-orange-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-500/50 dark:bg-orange-950/50 dark:text-orange-100 dark:hover:bg-orange-900/55";
    case "green":
      return "bg-emerald-50/80 text-emerald-950 hover:bg-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-500/50 dark:bg-emerald-950/50 dark:text-emerald-100 dark:hover:bg-emerald-900/55";
    case "blue":
      return "bg-blue-50/85 text-blue-950 hover:bg-blue-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500/50 dark:bg-blue-950/55 dark:text-blue-100 dark:hover:bg-blue-900/60";
  }
}

function lineCardFallbackHighlightColor(
  marker: AnalysisMoveMarker,
  segment: ExplanationSegment,
  card: ExplanationLineCard,
): ExplanationHighlightColor {
  const cardText = `${card.id} ${card.title}`.toLowerCase();
  const segmentText = segment.text.toLowerCase();
  const combined = `${cardText} ${segmentText} ${card.why}`.toLowerCase();
  if (
    /\b(brilliant|great|beautiful|sacrifice|very strong|decisive resource)\b/.test(combined) ||
    ["brilliant", "great"].includes(marker.primary_class)
  ) {
    return "blue";
  }
  if (
    /\b(better|best|excellent|good|strong|works|defen[sc](?:e|ive)?|saves?|keeps?|calmer)\b/.test(
      combined,
    )
  ) {
    return "green";
  }
  if (
    /\b(cannot|can't|not simply free|capture fails|why .* fails|objection|does not work)\b/.test(
      combined,
    )
  ) {
    return "orange";
  }
  if (
    /\b(blunder|mistake|inaccuracy|missed|bad|allows?|allowed|punish(?:es|ed)?|loses?|fails?|problem)\b/.test(
      combined,
    )
  ) {
    return "red";
  }
  if (["best", "excellent", "good"].includes(marker.primary_class)) {
    return "green";
  }
  return "red";
}

function otherBoardSide(side: BoardSide): BoardSide {
  return side === "white" ? "black" : "white";
}

function lineStepSquares(rootFen: string, moves: string[], step: number): string | null {
  if (step <= 0) {
    return null;
  }
  const move = moves[step - 1];
  if (!move) {
    return null;
  }
  const beforeFen = fenAfterMoves(rootFen, moves, step - 1) ?? rootFen;
  const squares = sanToSquares(beforeFen, move);
  return squares ? `${squares[0]}${squares[1]}` : null;
}

function useCoarsePointer(): boolean {
  const [isCoarse, setIsCoarse] = useState(() => coarsePointerMatches());

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mediaQuery = window.matchMedia("(hover: none), (pointer: coarse)");
    const handleChange = () => setIsCoarse(mediaQuery.matches);
    handleChange();
    mediaQuery.addEventListener?.("change", handleChange);
    return () => mediaQuery.removeEventListener?.("change", handleChange);
  }, []);

  return isCoarse;
}

function coarsePointerMatches(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(hover: none), (pointer: coarse)").matches;
}

function parseExplanationWithMoves(
  text: string,
  marker: AnalysisMoveMarker,
  rootFen: string,
  onMoveClick?: (rootFen: string, moves: string[], step: number) => void,
) {
  if (!text || onMoveClick === undefined) {
    return text;
  }

  const knownMoves = new Set<string>([marker.san]);
  if (marker.best_move_san) {
    knownMoves.add(marker.best_move_san);
  }
  for (const card of marker.explanation_line_cards) {
    for (const san of card.moves) {
      knownMoves.add(san);
    }
  }
  for (const line of marker.best_lines) {
    for (const san of line.pv_san) {
      knownMoves.add(san);
    }
  }
  for (const line of marker.book_lines ?? []) {
    for (const move of line.moves) {
      knownMoves.add(move.san);
    }
  }

  const parts: Array<string | { move: string; key: string }> = [];
  let lastIndex = 0;
  for (const match of text.matchAll(SAN_PATTERN)) {
    const san = match[0];
    const index = match.index ?? 0;
    if (!knownMoves.has(san)) {
      continue;
    }
    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index));
    }
    parts.push({ move: san, key: `${san}-${index}` });
    lastIndex = index + san.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  if (parts.length <= 1) {
    return text;
  }

  return parts.map((part) => {
    if (typeof part === "string") {
      return part;
    }
    return (
      <button
        className="inline rounded border-stone-200 bg-stone-50 px-1 py-0.5 font-mono text-xs font-medium text-stone-700 transition-colors hover:border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300 dark:hover:border-stone-600 dark:hover:bg-stone-700"
        key={part.key}
        onClick={() => {
          const preview = previewForMove(marker, part.move);
          onMoveClick(rootFen, preview.moves, preview.step);
        }}
        type="button"
      >
        {part.move}
      </button>
    );
  });
}

function previewForMove(
  marker: AnalysisMoveMarker,
  san: string,
): { moves: string[]; step: number } {
  for (const card of marker.explanation_line_cards) {
    const idx = card.moves.indexOf(san);
    if (idx !== -1) {
      return { moves: card.moves, step: idx + 1 };
    }
  }
  for (const line of marker.book_lines ?? []) {
    const moves = line.moves.map((move) => move.san);
    const idx = moves.indexOf(san);
    if (idx !== -1) {
      return { moves, step: idx + 1 };
    }
  }
  for (const line of marker.best_lines) {
    const idx = line.pv_san.indexOf(san);
    if (idx !== -1) {
      return { moves: line.pv_san, step: idx + 1 };
    }
  }
  return { moves: [marker.san], step: 1 };
}

function formatMoveLabel(move: GameMove | null) {
  if (!move) {
    return "Starting position";
  }
  return `${move.move_number}${move.side === "white" ? "." : "..."} ${move.san}`;
}

function openingNameBase(openingName: string): string {
  const splitAt = openingName.indexOf(":");
  return splitAt === -1 ? openingName : openingName.slice(0, splitAt);
}

function formatCp(cp: number): string {
  if (Math.abs(cp) >= 90_000) {
    return cp > 0 ? "Mate" : "-Mate";
  }
  return `${cp > 0 ? "+" : ""}${(cp / 100).toFixed(2)}`;
}
