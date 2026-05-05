import { ArrowUp, RotateCw, Smile } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  isSupportedChessComAnalysisUrl,
  normalizeChessComImportUrl,
} from "../../lib/analysis-routing";
import { ApiError } from "../../lib/api";
import { cn } from "../../lib/utils";
import type { GameAnalysisImportRequest, SignificanceLabel } from "../../types/api";

export type ImportPanelStatus = "idle" | "submitting" | "polling" | "succeeded" | "failed";

interface AnalysisImportPanelProps {
  status: ImportPanelStatus;
  error: string | null;
  onImport: (request: GameAnalysisImportRequest) => Promise<void>;
  onClearError?: () => void;
}

type Mode = "url" | "pgn";

const DEFAULT_EXPLAIN_SIGNIFICANCE: readonly SignificanceLabel[] = ["critical"];

const FIELD_HEIGHT_URL = 46;
const FIELD_HEIGHT_PGN = 232;
const BUTTON_SIZE = 36;
const BUTTON_INSET = 6;

const PGN_TAG_PATTERN = /\[\s*\w+\s+"[^"]*"\s*\]/;
const PGN_MOVE_PATTERN = /\b\d+\s*\.{1,3}\s*[A-Za-z0-9]/;

const GITHUB_URL = "https://github.com/yahorbarkouski/g6explanation";
const FEEDBACK_URL = "mailto:admin@g6chess.com";

export function AnalysisImportPanel({
  status,
  error,
  onImport,
  onClearError,
}: AnalysisImportPanelProps) {
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [pgn, setPgn] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const isBusy = status === "submitting" || status === "polling";
  const displayedError = localError ?? error;
  const value = mode === "url" ? url : pgn;
  const canSubmit = !isBusy && isValidInput(mode, value);

  function clearErrors() {
    setLocalError(null);
    onClearError?.();
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!canSubmit) {
      return;
    }
    setLocalError(null);
    try {
      await onImport(buildRequest(mode, { url: url.trim(), pgn }));
    } catch (err) {
      setLocalError(importErrorMessage(err));
    }
  }

  function toggleMode() {
    clearErrors();
    setMode((current) => (current === "url" ? "pgn" : "url"));
  }

  function handleFieldChange(next: string) {
    clearErrors();
    if (mode === "url") {
      setUrl(stripNewlines(next));
    } else {
      setPgn(next);
    }
  }

  return (
    <section className="flex w-full flex-col">
      <h1 className="text-balance text-center text-stone-900 text-xl leading-none dark:text-stone-100">
        Paste your game link
      </h1>
      <p className="text-center text-stone-500 text-sm dark:text-stone-500 mt-3">
        or replace chess.com with{" "}
        <span className="text-stone-600 dark:text-stone-400">g6chess.com</span>
      </p>

      <form className="mt-8" onSubmit={handleSubmit}>
        <MorphField
          canSubmit={canSubmit}
          isBusy={isBusy}
          mode={mode}
          onChange={handleFieldChange}
          onSubmit={handleSubmit}
          status={status}
          value={value}
        />
      </form>

      <div className="mt-2 flex items-center justify-between gap-3 px-1">
        <ModeToggle
          alert={mode === "url" && Boolean(localError)}
          mode={mode}
          onToggle={toggleMode}
        />
        <RightStatus error={displayedError} mode={mode} />
      </div>

      <SuggestionCards />
    </section>
  );
}

function RightStatus({ error, mode }: { error: string | null; mode: Mode }) {
  if (!error) {
    return null;
  }
  const text = mode === "url" ? "chess.com import failed" : error;
  return (
    <span className="max-w-[60%] truncate text-right text-rose-600 text-xs dark:text-rose-400">
      {text}
    </span>
  );
}

function SuggestionCards() {
  return (
    <div className="mt-12 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
      <SuggestionCard
        href={GITHUB_URL}
        icon={<GithubIcon className="size-3.5" />}
        subtitle="To contribute to the project"
        title="Star us on GitHub"
      />
      <SuggestionCard
        href={FEEDBACK_URL}
        icon={<Smile className="size-3.5" strokeWidth={2} />}
        subtitle="Suggest or report, we'd love to chat"
        title="Leave feedback"
      />
    </div>
  );
}

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  );
}

function SuggestionCard({
  href,
  icon,
  title,
  subtitle,
}: {
  href: string;
  icon: ReactNode;
  title: string;
  subtitle: string;
}) {
  const isExternal = /^https?:/i.test(href);
  return (
    <a
      className="group flex flex-col -mx-0.5 gap-3 rounded-2xl bg-stone-50 p-4 outline-none hover:bg-stone-100 dark:bg-stone-900/80 dark:hover:bg-stone-800/80"
      href={href}
      rel={isExternal ? "noopener noreferrer" : undefined}
      target={isExternal ? "_blank" : undefined}
    >
      <span className="inline-flex size-[26px] items-center justify-center rounded-lg bg-white text-stone-700 dark:shadow-none shadow-[0_0_0_1px_rgba(28,25,23,0.06)] dark:bg-stone-950 dark:text-stone-200 dark:shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
        {icon}
      </span>
      <div>
        <h3 className="text-sm text-stone-900 leading-tight dark:text-stone-100">{title}</h3>
        <p className="mt-0.5 text-stone-500 text-xs dark:text-stone-500">{subtitle}</p>
      </div>
    </a>
  );
}

function Spokes({ className, ...props }: ComponentProps<"svg">) {
  return (
    <svg
      aria-hidden="true"
      className={cn("animate-spin", className)}
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        d="M12 2V6M16.2 7.8L19.1 4.9M18 12H22M16.2 16.2L19.1 19.1M12 18V22M4.9 19.1L7.8 16.2M2 12H6M4.9 4.9L7.8 7.8"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}

interface MorphFieldProps {
  mode: Mode;
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  isBusy: boolean;
  canSubmit: boolean;
  status: ImportPanelStatus;
}

function MorphField({
  mode,
  value,
  onChange,
  onSubmit,
  isBusy,
  canSubmit,
  status,
}: MorphFieldProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: refocus when mode toggles
  useEffect(() => {
    const node = textareaRef.current;
    if (!node) {
      return;
    }
    node.focus();
    const caret = node.value.length;
    node.setSelectionRange(caret, caret);
  }, [mode]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter") {
      return;
    }
    const wantsSubmit = mode === "url" ? !event.shiftKey : event.metaKey || event.ctrlKey;
    if (!wantsSubmit) {
      return;
    }
    event.preventDefault();
    if (canSubmit) {
      onSubmit();
    }
  }

  const targetHeight = mode === "url" ? FIELD_HEIGHT_URL : FIELD_HEIGHT_PGN;
  const targetButtonTop =
    mode === "url"
      ? (FIELD_HEIGHT_URL - BUTTON_SIZE) / 2 - 1
      : FIELD_HEIGHT_PGN - BUTTON_SIZE - BUTTON_INSET;

  return (
    <div
      className="relative w-full rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900"
      style={{ height: targetHeight }}
    >
      <textarea
        aria-label={mode === "url" ? "Chess.com URL" : "PGN fallback"}
        autoCapitalize="off"
        autoComplete="off"
        autoCorrect="off"
        className={cn(
          "block h-full w-full resize-none bg-transparent px-3 py-2.5 pr-14 text-stone-900 outline-none ring-0 [box-shadow:none!important] placeholder:text-stone-400 focus:[box-shadow:none!important] focus-visible:[box-shadow:none!important] disabled:opacity-60 dark:text-stone-100 dark:placeholder:text-stone-500",
          mode === "url" ? "font-sans text-[15px] leading-6" : "font-mono text-xs leading-relaxed",
        )}
        data-1p-ignore="true"
        data-enable-grammarly="false"
        data-form-type="other"
        data-gramm="false"
        data-gramm_editor="false"
        data-lpignore="true"
        disabled={isBusy}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          mode === "url"
            ? "https://chess.com/game/..."
            : '[Event "My game"]\n\n1. e4 e5 2. Nf3 Nc6 *'
        }
        ref={textareaRef}
        rows={1}
        spellCheck={false}
        value={value}
      />
      <div className="absolute right-1" style={{ top: targetButtonTop }}>
        <SubmitCircle disabled={!canSubmit} isBusy={isBusy} mode={mode} status={status} />
      </div>
    </div>
  );
}

function SubmitCircle({
  disabled,
  isBusy,
  mode,
  status,
}: {
  disabled: boolean;
  isBusy: boolean;
  mode: Mode;
  status: ImportPanelStatus;
}) {
  const Icon = status === "failed" ? RotateCw : ArrowUp;
  return (
    <button
      aria-label={mode === "url" ? "Analyze" : "Analyze PGN"}
      className={cn(
        "flex size-9 items-center justify-center rounded-xl bg-stone-900 text-white outline-none [box-shadow:none!important] dark:bg-stone-100 dark:text-stone-900",
        isBusy
          ? "cursor-default"
          : "cursor-pointer hover:bg-stone-800 disabled:cursor-default disabled:opacity-25 dark:hover:bg-stone-200 dark:disabled:opacity-30",
      )}
      disabled={disabled}
      type="submit"
    >
      {isBusy ? <Spokes className="size-5" /> : <Icon className="size-4" strokeWidth={2.25} />}
    </button>
  );
}

function ModeToggle({
  alert,
  mode,
  onToggle,
}: {
  alert: boolean;
  mode: Mode;
  onToggle: () => void;
}) {
  const label = mode === "url" ? "or paste PGN" : "use a link instead";
  return (
    <button
      aria-expanded={mode === "pgn"}
      className={cn(
        "cursor-pointer rounded-full px-2 text-xs outline-none",
        alert
          ? "font-medium text-stone-800 hover:text-stone-950 dark:text-stone-200 dark:hover:text-stone-50"
          : "text-stone-400 hover:text-stone-600 dark:text-stone-500 dark:hover:text-stone-300",
      )}
      onClick={onToggle}
      title="PGN fallback"
      type="button"
    >
      {label}
    </button>
  );
}

function stripNewlines(value: string): string {
  return value.replace(/[\r\n]+/g, "");
}

function isValidInput(mode: Mode, value: string): boolean {
  return mode === "url" ? isValidChessComUrl(value) : isValidPgn(value);
}

function isValidChessComUrl(value: string): boolean {
  return isSupportedChessComAnalysisUrl(value);
}

function isValidPgn(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed.length < 4) {
    return false;
  }
  return PGN_TAG_PATTERN.test(trimmed) || PGN_MOVE_PATTERN.test(trimmed);
}

function buildRequest(mode: Mode, values: { url: string; pgn: string }): GameAnalysisImportRequest {
  const sourceFields =
    mode === "url"
      ? ({ source: "chess_com_live_url", url: normalizeChessComImportUrl(values.url) } as const)
      : ({ source: "pgn", pgn: values.pgn } as const);
  return {
    ...sourceFields,
    explain_significance: [...DEFAULT_EXPLAIN_SIGNIFICANCE],
    include_context: true,
    use_baseline_fallback: false,
  };
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
