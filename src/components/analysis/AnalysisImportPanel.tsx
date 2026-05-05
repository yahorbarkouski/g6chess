import { ClipboardPaste, Link2, Play, RotateCw } from "lucide-react";
import { type FormEvent, useState } from "react";
import { ApiError } from "../../lib/api";
import { cn } from "../../lib/utils";
import type {
  GameAnalysisImportRequest,
  GameAnalysisSnapshot,
  ImportedGameMetadata,
} from "../../types/api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

export type ImportPanelStatus = "idle" | "submitting" | "polling" | "succeeded" | "failed";

interface AnalysisImportPanelProps {
  status: ImportPanelStatus;
  snapshot: GameAnalysisSnapshot | null;
  source: ImportedGameMetadata | null;
  error: string | null;
  onImport: (request: GameAnalysisImportRequest) => Promise<void>;
  variant?: "panel" | "hero";
}

const DEFAULT_EXPLAIN_SIGNIFICANCE = ["critical"] as const;

export function AnalysisImportPanel({
  status,
  snapshot,
  source,
  error,
  onImport,
  variant = "panel",
}: AnalysisImportPanelProps) {
  const [url, setUrl] = useState("");
  const [pgn, setPgn] = useState("");
  const [rating, setRating] = useState(1500);
  const [showPgnFallback, setShowPgnFallback] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const isBusy = status === "submitting" || status === "polling";
  const displayedError = localError ?? error;
  const isHero = variant === "hero";
  const sourceLabel = source?.title ?? "Chess.com URL or PGN";
  const inputClassName = cn(
    "w-full border border-stone-200 bg-white font-mono text-sm text-stone-800 outline-none shadow-[0_1px_0_rgba(255,255,255,0.7)_inset] transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-stone-400 focus:border-stone-400 focus:shadow-[0_0_0_3px_rgba(120,113,108,0.14)] dark:border-stone-700 dark:bg-stone-950 dark:text-stone-100 dark:focus:border-stone-500 dark:focus:shadow-[0_0_0_3px_rgba(214,211,209,0.12)]",
    isHero ? "h-11 rounded-md" : "h-10 rounded",
  );
  const fieldLabelClassName = cn(
    "mb-1 block text-xs font-medium text-stone-500 dark:text-stone-400",
    isHero && "text-stone-600 dark:text-stone-300",
  );

  async function submitUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    try {
      await onImport(baseRequest({ source: "chess_com_live_url", url: url.trim() }));
    } catch (err) {
      setLocalError(importErrorMessage(err));
      setShowPgnFallback(true);
    }
  }

  async function submitPgn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    try {
      await onImport(baseRequest({ source: "pgn", pgn }));
    } catch (err) {
      setLocalError(importErrorMessage(err));
    }
  }

  function baseRequest(
    sourceFields: Pick<GameAnalysisImportRequest, "source" | "url" | "pgn">,
  ): GameAnalysisImportRequest {
    return {
      ...sourceFields,
      player_level: { kind: "rating", value: rating, system: "frontend-default" },
      explain_significance: [...DEFAULT_EXPLAIN_SIGNIFICANCE],
      include_context: true,
      use_baseline_fallback: false,
    };
  }

  return (
    <section
      className={cn(
        "w-full rounded-md text-left",
        isHero
          ? "bg-stone-50/95 px-4 py-4 shadow-[0_24px_80px_rgba(28,25,23,0.12),0_8px_28px_rgba(28,25,23,0.08),0_1px_0_rgba(255,255,255,0.72)_inset] ring-1 ring-stone-950/5 sm:px-5 sm:py-5 dark:bg-stone-900/85 dark:shadow-[0_24px_80px_rgba(0,0,0,0.34)] dark:ring-white/10"
          : "mb-5 border border-stone-200 bg-stone-50/80 px-3 py-3 dark:border-stone-800 dark:bg-stone-900/50",
      )}
    >
      <div
        className={cn(
          "mb-3 flex flex-wrap items-center justify-between gap-2",
          isHero && "mb-5 items-start gap-3",
        )}
      >
        <div className="min-w-0">
          <h2
            className={cn(
              "font-serif text-lg text-stone-900 dark:text-stone-100",
              isHero && "text-balance text-3xl leading-none sm:text-4xl",
            )}
          >
            Import game
          </h2>
          <p
            className={cn(
              "truncate text-xs text-stone-500 dark:text-stone-500",
              isHero && "mt-2 max-w-[34rem] text-pretty text-sm text-stone-600 dark:text-stone-400",
            )}
          >
            {sourceLabel}
          </p>
        </div>
        <StatusBadge status={status} />
      </div>

      <form
        className={cn(
          "grid gap-2",
          isHero
            ? "gap-3 md:grid-cols-[minmax(0,1fr)_116px_auto]"
            : "lg:grid-cols-[minmax(0,1fr)_112px_auto]",
        )}
        onSubmit={submitUrl}
      >
        <label className="min-w-0">
          <span className={fieldLabelClassName}>Chess.com URL</span>
          <div className="relative">
            <Link2 className="-translate-y-1/2 absolute top-1/2 left-3 size-4 text-stone-400" />
            <input
              className={cn(inputClassName, "pr-3 pl-9")}
              disabled={isBusy}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.chess.com/game/168239961236"
              type="url"
              value={url}
            />
          </div>
        </label>

        <label>
          <span className={fieldLabelClassName}>Level</span>
          <input
            className={cn(inputClassName, "px-3 tabular-nums")}
            disabled={isBusy}
            max={3200}
            min={100}
            onChange={(event) => setRating(Number(event.target.value))}
            type="number"
            value={rating}
          />
        </label>

        <div className="flex items-end gap-2">
          <Button
            className={cn(isHero ? "h-11 px-4" : "h-10")}
            disabled={isBusy || !url.trim()}
            size="sm"
            type="submit"
          >
            {status === "failed" ? <RotateCw className="size-4" /> : <Play className="size-4" />}
            Analyze
          </Button>
          <Button
            aria-expanded={showPgnFallback}
            className={cn(isHero ? "size-11" : "h-10")}
            disabled={status === "submitting"}
            onClick={() => setShowPgnFallback((value) => !value)}
            size="icon"
            title="PGN fallback"
            type="button"
            variant="outline"
          >
            <ClipboardPaste className="size-4" />
          </Button>
        </div>
      </form>

      {showPgnFallback ? (
        <form className={cn("mt-3 grid gap-2", isHero && "mt-4 gap-3")} onSubmit={submitPgn}>
          <label>
            <span className={fieldLabelClassName}>PGN fallback</span>
            <textarea
              className={cn(
                inputClassName,
                "min-h-32 resize-y px-3 py-2 text-xs leading-relaxed",
                isHero && "min-h-36",
              )}
              disabled={isBusy}
              onChange={(event) => setPgn(event.target.value)}
              placeholder='[Event "My game"]&#10;&#10;1. e4 e5 2. Nf3 Nc6 *'
              value={pgn}
            />
          </label>
          <div className="flex justify-end">
            <Button
              className={cn(isHero && "h-11 px-4")}
              disabled={isBusy || !pgn.trim()}
              size="sm"
              type="submit"
            >
              <ClipboardPaste className="size-4" />
              Analyze PGN
            </Button>
          </div>
        </form>
      ) : null}

      {displayedError ? (
        <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
          {displayedError}
        </div>
      ) : null}

      <ImportProgress snapshot={snapshot} status={status} />
    </section>
  );
}

function StatusBadge({ status }: { status: ImportPanelStatus }) {
  const label = {
    idle: "Ready",
    submitting: "Starting",
    polling: "Running",
    succeeded: "Imported",
    failed: "Error",
  }[status];
  const tone = status === "failed" ? "red" : status === "succeeded" ? "green" : "neutral";
  return <Badge tone={tone}>{label}</Badge>;
}

function ImportProgress({
  snapshot,
  status,
}: {
  snapshot: GameAnalysisSnapshot | null;
  status: ImportPanelStatus;
}) {
  if (status === "idle" && snapshot === null) {
    return null;
  }
  const total = snapshot?.total_plies ?? 0;
  const completed = snapshot?.context_completed ?? 0;
  const explanationCompleted = snapshot?.explanation_completed ?? 0;
  const explanationRequired = snapshot?.explanation_required ?? 0;
  const percent =
    total > 0
      ? Math.min(100, Math.round((completed / total) * 100))
      : status === "succeeded"
        ? 100
        : 8;

  return (
    <div className="mt-3 space-y-1.5">
      <div className="flex items-center justify-between gap-2 font-mono text-[11px] text-stone-500 tabular-nums dark:text-stone-400">
        <span>
          {total > 0
            ? `${completed}/${total} plies`
            : status === "submitting"
              ? "starting"
              : status}
        </span>
        <span>
          {explanationRequired > 0
            ? `${explanationCompleted}/${explanationRequired} explanations`
            : (snapshot?.status ?? "")}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded bg-stone-200 dark:bg-stone-800">
        <div
          className={cn(
            "h-full rounded transition-[width,background-color] duration-300",
            status === "failed" ? "bg-rose-500" : "bg-emerald-700 dark:bg-emerald-500",
          )}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function importErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Import failed.";
}
