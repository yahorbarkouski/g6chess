import { useReducedMotion } from "framer-motion";
import { ArrowRight, ChevronRight, X } from "lucide-react";
import { Fragment, type ReactNode, useEffect, useMemo, useState } from "react";
import { TextShimmer } from "@/components/loading-ui/text-shimmer";
import { analysisTagLabel, primaryClassClass, primaryClassLabel } from "../../lib/analysis-format";
import { fenAfterMoves, sanToSquares, sideToMoveFromFen } from "../../lib/chess";
import { cn } from "../../lib/utils";
import type {
  AnalysisMoveMarker,
  BoardSide,
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
  className?: string;
}

const SAN_PATTERN = /\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b/g;
const SHOW_ENGINE_DETAIL_PANEL: boolean = false;
type LineCardTone = "good" | "bad";

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
  className,
}: PositionInfoProps) {
  const explanationContent = useMemo(() => {
    if (!selectedMarker || !rootFen) {
      return null;
    }
    return renderExplanationContent(selectedMarker, rootFen, boardOrientation, onMoveClick);
  }, [boardOrientation, onMoveClick, rootFen, selectedMarker]);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="font-serif text-2xl text-stone-900 dark:text-stone-100">
            <MorphText>{formatMoveLabel(currentMove)}</MorphText>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {selectedMarker?.tags.includes("forced") ? (
            <Badge className="min-h-0 rounded border-none bg-stone-200 px-2 py-1 text-stone-600 dark:bg-stone-700 dark:text-stone-300">
              <ArrowRight className="mr-1 inline size-3" />
              Forced
            </Badge>
          ) : selectedMarker?.primary_class ? (
            <Badge
              className={cn(
                "min-h-0 rounded border px-2 py-1",
                primaryClassClass(selectedMarker.primary_class),
              )}
            >
              {selectedMarker.primary_class === "book" && openingName
                ? openingNameBase(openingName)
                : primaryClassLabel(selectedMarker.primary_class)}
            </Badge>
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
      : [{ text: marker.explanation, line_card_id: null, line_card_anchor: null }];
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
  onMoveClick: ((rootFen: string, moves: string[], step: number) => void) | undefined;
  rootFen: string;
  segment: ExplanationSegment;
}): ReactNode {
  const anchor = segment.line_card_anchor;
  const tone = lineCardTone(marker, segment, card);
  if (!anchor || !segment.text.includes(anchor)) {
    return (
      <LineCardAnchor
        boardOrientation={boardOrientation}
        card={card}
        onMoveClick={onMoveClick}
        rootFen={rootFen}
        tone={tone}
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
        tone={tone}
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
  tone,
  triggerText,
}: {
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  onMoveClick: ((rootFen: string, moves: string[], step: number) => void) | undefined;
  rootFen: string;
  tone: LineCardTone;
  triggerText: string;
}) {
  const isCoarsePointer = useCoarsePointer();
  const [hoverCardOpen, setHoverCardOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const canPreview = onMoveClick !== undefined && card.moves.length > 0;
  const handleClick = () => {
    if (isCoarsePointer) {
      setDialogOpen(true);
      return;
    }
    if (canPreview) {
      onMoveClick(rootFen, card.moves, card.moves.length);
    }
  };
  const showHoverCard = hoverCardOpen && !isCoarsePointer;

  return (
    <div className="relative inline-block align-baseline">
      <button
        aria-label={`${triggerText}: ${card.title}`}
        className={cn(
          "inline cursor-pointer rounded-sm px-0.5 text-left transition-colors",
          tone === "good"
            ? "bg-emerald-50/80 text-emerald-950 hover:bg-emerald-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-500/50 dark:bg-emerald-950/50 dark:text-emerald-100 dark:hover:bg-emerald-900/55"
            : "bg-amber-50/80 text-stone-800 hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-500/50 dark:bg-amber-950/45 dark:text-stone-200 dark:hover:bg-amber-900/50",
        )}
        onBlur={() => setHoverCardOpen(false)}
        onClick={handleClick}
        onFocus={() => setHoverCardOpen(true)}
        onPointerEnter={() => setHoverCardOpen(true)}
        onPointerLeave={() => setHoverCardOpen(false)}
        type="button"
      >
        {triggerText}
      </button>
      {showHoverCard ? (
        <LineCardPreviewShell boardOrientation={boardOrientation} card={card} rootFen={rootFen} />
      ) : null}
      {dialogOpen ? (
        <div
          aria-label={card.title}
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-end justify-center bg-stone-950/35 p-3 backdrop-blur-[2px] sm:items-center"
          role="dialog"
        >
          <div className="relative w-full max-w-sm rounded-lg border border-stone-200 bg-white p-3 shadow-[0_24px_70px_rgba(28,25,23,0.28)] dark:border-stone-700 dark:bg-stone-900">
            <div className="absolute top-2 right-2 z-10">
              <button
                aria-label="Close line preview"
                className="flex size-7 items-center justify-center rounded text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-200"
                onClick={() => setDialogOpen(false)}
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>
            <LineCardPreview
              active
              boardOrientation={boardOrientation}
              card={card}
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
  rootFen,
}: {
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  rootFen: string;
}) {
  return (
    <div className="absolute top-full left-1/2 z-50 mt-2 w-72 max-w-[calc(100vw-2rem)] -translate-x-1/2 whitespace-normal rounded-lg border border-stone-200 bg-white p-2.5 text-left shadow-[0_18px_45px_rgba(28,25,23,0.18),0_1px_0_rgba(255,255,255,0.8)_inset] sm:w-80 dark:border-stone-700 dark:bg-stone-900 dark:shadow-[0_18px_45px_rgba(0,0,0,0.4)]">
      <LineCardPreview active boardOrientation={boardOrientation} card={card} rootFen={rootFen} />
    </div>
  );
}

function LineCardPreview({
  active,
  boardOrientation,
  card,
  rootFen,
}: {
  active: boolean;
  boardOrientation: BoardSide | null;
  card: ExplanationLineCard;
  rootFen: string;
}) {
  const prefersReducedMotion = useReducedMotion();
  const [step, setStep] = useState(prefersReducedMotion ? card.moves.length : 0);
  const displayStep = prefersReducedMotion ? card.moves.length : step;
  const currentFen = fenAfterMoves(rootFen, card.moves, displayStep) ?? rootFen;
  const highlightedMove = lineStepSquares(rootFen, card.moves, displayStep);
  const firstMoveSide = sideToMoveFromFen(rootFen);
  const orientation = boardOrientation ?? firstMoveSide;

  useEffect(() => {
    if (!active) {
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
  }, [active, card.moves.length, prefersReducedMotion]);

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
          return (
            <span
              className={cn(
                "inline-flex shrink-0 items-center rounded border px-1 py-0.5 transition-colors",
                activeMove
                  ? "border-amber-300 bg-amber-100 dark:border-amber-700 dark:bg-amber-900/50"
                  : "border-stone-200 bg-white/60 dark:border-stone-700 dark:bg-stone-900/60",
              )}
              key={`${card.id}-${card.moves.slice(0, moveStep).join(" ")}`}
            >
              <SanMove san={move} side={moveSide} />
            </span>
          );
        })}
      </span>
    </div>
  );
}

function lineCardTone(
  marker: AnalysisMoveMarker,
  segment: ExplanationSegment,
  card: ExplanationLineCard,
): LineCardTone {
  const cardText = `${card.id} ${card.title}`.toLowerCase();
  const segmentText = segment.text.toLowerCase();
  const combined = `${cardText} ${segmentText} ${card.why}`.toLowerCase();
  if (
    /\b(better|best|excellent|good|strong|works|defen[sc](?:e|ive)?|saves?|keeps?|calmer)\b/.test(
      combined,
    )
  ) {
    return "good";
  }
  if (
    /\b(blunder|mistake|inaccuracy|missed|bad|allows?|allowed|punish(?:es|ed)?|loses?|fails?|problem)\b/.test(
      combined,
    )
  ) {
    return "bad";
  }
  if (["best", "excellent", "good"].includes(marker.primary_class)) {
    return "good";
  }
  return "bad";
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
        className="inline rounded border border-stone-200 bg-stone-50 px-1 py-0.5 font-mono text-xs font-medium text-stone-700 transition-colors hover:border-stone-300 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300 dark:hover:border-stone-600 dark:hover:bg-stone-700"
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
