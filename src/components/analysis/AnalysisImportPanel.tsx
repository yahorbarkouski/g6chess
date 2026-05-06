import { ArrowUp, Dices, RotateCw, Smile } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  type ExternalGameTarget,
  extractGameImportTarget,
  isSupportedGameAnalysisUrl,
  normalizeGameImportUrl,
} from "../../lib/analysis-routing";
import { ApiError } from "../../lib/api";
import { cn } from "../../lib/utils";
import type { GameAnalysisImportRequest, SignificanceLabel } from "../../types/api";

export type ImportPanelStatus = "idle" | "submitting" | "polling" | "succeeded" | "failed";

interface AnalysisImportPanelProps {
  status: ImportPanelStatus;
  error: string | null;
  initialUrl?: string | null;
  onImport: (
    request: GameAnalysisImportRequest,
    hintedTarget?: ExternalGameTarget | null,
  ) => Promise<void>;
  onClearError?: () => void;
  turnstileToken?: string | null;
  turnstileResetKey?: number;
  turnstileRequired?: boolean;
  onTurnstileToken?: (token: string | null) => void;
  onTurnstileReset?: () => void;
}

type Mode = "url" | "pgn";

interface PendingTurnstileImport {
  request: GameAnalysisImportRequest;
  hintedTarget: ExternalGameTarget | null;
}

const DEFAULT_EXPLAIN_SIGNIFICANCE: readonly SignificanceLabel[] = ["critical"];
function turnstileSiteKey(): string {
  return String(import.meta.env.VITE_G6_TURNSTILE_SITE_KEY ?? "").trim();
}

export function isTurnstileEnabled(): boolean {
  return turnstileSiteKey().length > 0;
}

const FIELD_HEIGHT_URL = 46;
const FIELD_HEIGHT_PGN = 232;
const BUTTON_SIZE = 36;
const BUTTON_INSET = 6;

const PGN_TAG_PATTERN = /\[\s*\w+\s+"[^"]*"\s*\]/;
const PGN_MOVE_PATTERN = /\b\d+\s*\.{1,3}\s*[A-Za-z0-9]/;

const GITHUB_URL = "https://github.com/yahorbarkouski/g6chess";
const FEEDBACK_URL = "mailto:admin@g6chess.com";

interface RandomGame {
  label: string;
  pgn: string;
}

const RANDOM_GAMES: ReadonlyArray<RandomGame> = [
  {
    label: "Opera Game (Morphy, 1858)",
    pgn: `[Event "Casual Game"]
[Site "Paris FRA"]
[Date "1858.??.??"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]
[WhiteElo "2500"]
[BlackElo "1600"]

1.e4 e5 2.Nf3 d6 3.d4 Bg4 4.dxe5 Bxf3 5.Qxf3 dxe5 6.Bc4 Nf6 7.Qb3 Qe7
8.Nc3 c6 9.Bg5 b5 10.Nxb5 cxb5 11.Bxb5+ Nbd7 12.O-O-O Rd8 13.Rxd7 Rxd7
14.Rd1 Qe6 15.Bxd7+ Nxd7 16.Qb8+ Nxb8 17.Rd8# 1-0
`,
  },
  {
    label: "Immortal Game (Anderssen, 1851)",
    pgn: `[Event "Casual Game"]
[Site "London ENG"]
[Date "1851.06.21"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]
[WhiteElo "2500"]
[BlackElo "2400"]

1.e4 e5 2.f4 exf4 3.Bc4 Qh4+ 4.Kf1 b5 5.Bxb5 Nf6 6.Nf3 Qh6 7.d3 Nh5
8.Nh4 Qg5 9.Nf5 c6 10.g4 Nf6 11.Rg1 cxb5 12.h4 Qg6 13.h5 Qg5 14.Qf3 Ng8
15.Bxf4 Qf6 16.Nc3 Bc5 17.Nd5 Qxb2 18.Bd6 Bxg1 19.e5 Qxa1+ 20.Ke2 Na6
21.Nxg7+ Kd8 22.Qf6+ Nxf6 23.Be7# 1-0
`,
  },
  {
    label: "Evergreen Game (Anderssen, 1852)",
    pgn: `[Event "Casual Game"]
[Site "Berlin GER"]
[Date "1852.??.??"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]
[WhiteElo "2500"]
[BlackElo "2200"]

1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4 Bxb4 5.c3 Ba5 6.d4 exd4 7.O-O d3 8.Qb3 Qf6
9.e5 Qg6 10.Re1 Nge7 11.Ba3 b5 12.Qxb5 Rb8 13.Qa4 Bb6 14.Nbd2 Bb7 15.Ne4 Qf5
16.Bxd3 Qh5 17.Nf6+ gxf6 18.exf6 Rg8 19.Rad1 Qxf3 20.Rxe7+ Nxe7 21.Qxd7+ Kxd7
22.Bf5+ Ke8 23.Bd7+ Kf8 24.Bxe7# 1-0
`,
  },
  {
    label: "Réti vs Tartakower (Vienna, 1910)",
    pgn: `[Event "Vienna"]
[Site "Vienna AUT"]
[Date "1910.??.??"]
[White "Richard Réti"]
[Black "Saviely Tartakower"]
[Result "1-0"]
[WhiteElo "2500"]
[BlackElo "2500"]

1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Nf6 5.Qd3 e5 6.dxe5 Qa5+ 7.Bd2 Qxe5
8.O-O-O Nxe4 9.Qd8+ Kxd8 10.Bg5+ Kc7 11.Bd8# 1-0
`,
  },
  {
    label: "Game of the Century (Byrne vs Fischer, 1956)",
    pgn: `[Event "Third Rosenwald Trophy"]
[Site "New York, NY USA"]
[Date "1956.10.17"]
[White "Donald Byrne"]
[Black "Robert James Fischer"]
[Result "0-1"]
[WhiteElo "2400"]
[BlackElo "2300"]

1.Nf3 Nf6 2.c4 g6 3.Nc3 Bg7 4.d4 O-O 5.Bf4 d5 6.Qb3 dxc4 7.Qxc4 c6
8.e4 Nbd7 9.Rd1 Nb6 10.Qc5 Bg4 11.Bg5 Na4 12.Qa3 Nxc3 13.bxc3 Nxe4
14.Bxe7 Qb6 15.Bc4 Nxc3 16.Bc5 Rfe8+ 17.Kf1 Be6 18.Bxb6 Bxc4+ 19.Kg1 Ne2+
20.Kf1 Nxd4+ 21.Kg1 Ne2+ 22.Kf1 Nc3+ 23.Kg1 axb6 24.Qb4 Ra4 25.Qxb6 Nxd1
26.h3 Rxa2 27.Kh2 Nxf2 28.Re1 Rxe1 29.Qd8+ Bf8 30.Nxe1 Bd5 31.Nf3 Ne4
32.Qb8 b5 33.h4 h5 34.Ne5 Kg7 35.Kg1 Bc5+ 36.Kf1 Ng3+ 37.Ke1 Bb4+ 38.Kd1 Bb3+
39.Kc1 Ne2+ 40.Kb1 Nc3+ 41.Kc1 Rc2# 0-1
`,
  },
];

function pickRandomGameIndex(exclude: number | null): number {
  if (RANDOM_GAMES.length <= 1) {
    return 0;
  }
  const next = Math.floor(Math.random() * RANDOM_GAMES.length);
  return next === exclude ? (next + 1) % RANDOM_GAMES.length : next;
}

export function AnalysisImportPanel({
  status,
  error,
  initialUrl = null,
  onImport,
  onClearError,
  turnstileToken: controlledTurnstileToken,
  turnstileResetKey: controlledTurnstileResetKey,
  turnstileRequired = false,
  onTurnstileToken,
  onTurnstileReset,
}: AnalysisImportPanelProps) {
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState(() => initialUrl ?? "");
  const [pgn, setPgn] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [localTurnstileToken, setLocalTurnstileToken] = useState<string | null>(null);
  const [localTurnstileResetKey, setLocalTurnstileResetKey] = useState(0);
  const [pendingTurnstileImport, setPendingTurnstileImport] =
    useState<PendingTurnstileImport | null>(null);
  const [turnstilePrompted, setTurnstilePrompted] = useState(false);
  const lastRandomGameIndexRef = useRef<number | null>(null);

  const isBusy = status === "submitting" || status === "polling";
  const siteKey = turnstileSiteKey();
  const needsTurnstile = siteKey.length > 0;
  const turnstileToken =
    controlledTurnstileToken === undefined ? localTurnstileToken : controlledTurnstileToken;
  const turnstileResetKey = controlledTurnstileResetKey ?? localTurnstileResetKey;
  const isAwaitingTurnstile = needsTurnstile && pendingTurnstileImport !== null;
  const shouldShowTurnstile =
    needsTurnstile && turnstileToken === null && (turnstilePrompted || turnstileRequired);
  const displayedError = localError ?? error;
  const value = mode === "url" ? url : pgn;
  const canSubmit = !isBusy && !isAwaitingTurnstile && isValidInput(mode, value);
  const setTurnstileToken = useCallback(
    (token: string | null) => {
      if (controlledTurnstileToken === undefined) {
        setLocalTurnstileToken(token);
      }
      onTurnstileToken?.(token);
    },
    [controlledTurnstileToken, onTurnstileToken],
  );
  const resetTurnstile = useCallback(() => {
    setTurnstileToken(null);
    if (controlledTurnstileResetKey === undefined) {
      setLocalTurnstileResetKey((current) => current + 1);
    }
    onTurnstileReset?.();
  }, [controlledTurnstileResetKey, onTurnstileReset, setTurnstileToken]);
  const handleTurnstileExpire = useCallback(() => setTurnstileToken(null), [setTurnstileToken]);

  const promptForTurnstile = useCallback(
    (request: GameAnalysisImportRequest, hintedTarget: ExternalGameTarget | null) => {
      setPendingTurnstileImport({
        request: withoutTurnstileToken(request),
        hintedTarget,
      });
      setTurnstilePrompted(true);
    },
    [],
  );

  useEffect(() => {
    if (!needsTurnstile || pendingTurnstileImport === null || turnstileToken === null || isBusy) {
      return;
    }
    const request = {
      ...pendingTurnstileImport.request,
      turnstile_token: turnstileToken,
    };
    const { hintedTarget } = pendingTurnstileImport;
    setPendingTurnstileImport(null);
    setLocalError(null);
    void importWithOptionalHint(onImport, request, hintedTarget).catch((err: unknown) => {
      if (isTurnstileFailure(err)) {
        promptForTurnstile(request, hintedTarget);
        resetTurnstile();
        return;
      }
      setLocalError(importErrorMessage(err));
      setTurnstilePrompted(false);
      resetTurnstile();
    });
  }, [
    isBusy,
    needsTurnstile,
    onImport,
    pendingTurnstileImport,
    promptForTurnstile,
    resetTurnstile,
    turnstileToken,
  ]);

  function clearErrors() {
    setLocalError(null);
    onClearError?.();
  }

  function clearPendingVerification() {
    setPendingTurnstileImport(null);
    setTurnstilePrompted(false);
    if (needsTurnstile) {
      resetTurnstile();
    }
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!canSubmit) {
      return;
    }
    setLocalError(null);
    const hintedTarget = orientationHintForTarget(
      mode === "url" ? extractGameImportTarget(url.trim()) : null,
    );
    const request = buildRequest(mode, { url: url.trim(), pgn, turnstileToken });
    if (needsTurnstile && turnstileToken === null) {
      promptForTurnstile(request, hintedTarget);
      return;
    }
    try {
      await importWithOptionalHint(onImport, request, hintedTarget);
    } catch (err) {
      if (needsTurnstile && isTurnstileFailure(err)) {
        promptForTurnstile(request, hintedTarget);
        return;
      }
      setLocalError(importErrorMessage(err));
      if (needsTurnstile) {
        setTurnstilePrompted(false);
        resetTurnstile();
      }
    }
  }

  async function handleRandomGame() {
    if (isBusy || RANDOM_GAMES.length === 0) {
      return;
    }
    const index = pickRandomGameIndex(lastRandomGameIndexRef.current);
    const picked = RANDOM_GAMES[index];
    if (!picked) {
      return;
    }
    lastRandomGameIndexRef.current = index;
    clearErrors();
    const request = buildRequest("pgn", { url: "", pgn: picked.pgn, turnstileToken });
    if (needsTurnstile && turnstileToken === null) {
      promptForTurnstile(request, null);
      if (mode !== "pgn") {
        setMode("pgn");
      }
      setPgn(picked.pgn);
      return;
    }
    try {
      await onImport(request);
    } catch (err) {
      if (needsTurnstile && isTurnstileFailure(err)) {
        promptForTurnstile(request, null);
        if (mode !== "pgn") {
          setMode("pgn");
        }
        setPgn(picked.pgn);
        return;
      }
      setLocalError(importErrorMessage(err));
      if (needsTurnstile) {
        setTurnstilePrompted(false);
        resetTurnstile();
      }
    }
  }

  function toggleMode() {
    clearErrors();
    clearPendingVerification();
    setMode((current) => (current === "url" ? "pgn" : "url"));
  }

  function handleFieldChange(next: string) {
    clearErrors();
    if (pendingTurnstileImport !== null) {
      clearPendingVerification();
    }
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
        or simply add <span className="text-stone-600 dark:text-stone-400">g6</span> before your
        chess.com / lichess.org game url and press enter
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

      <div className="mt-2 flex items-center justify-between gap-3 px-1 pl-0">
        <ModeToggle
          alert={mode === "url" && Boolean(localError)}
          mode={mode}
          onToggle={toggleMode}
        />
        {displayedError ? (
          <RightStatus error={displayedError} mode={mode} />
        ) : RANDOM_GAMES.length > 0 ? (
          <RandomGameLink disabled={isBusy} onClick={handleRandomGame} />
        ) : null}
      </div>

      <SuggestionCards />

      {shouldShowTurnstile ? (
        <div className="mt-8 flex justify-center">
          <TurnstileWidget
            key={turnstileResetKey}
            onExpire={handleTurnstileExpire}
            onToken={setTurnstileToken}
            siteKey={siteKey}
          />
        </div>
      ) : null}
    </section>
  );
}

function RightStatus({ error, mode }: { error: string | null; mode: Mode }) {
  if (!error) {
    return null;
  }
  const text = mode === "url" ? "link import failed" : error;
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
    if (event.key !== "Enter" || event.shiftKey) {
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
        aria-label={mode === "url" ? "Game URL" : "PGN fallback"}
        autoCapitalize="off"
        autoComplete="off"
        autoCorrect="off"
        className={cn(
          "block h-full w-full resize-none bg-transparent px-3 py-2.5 pr-14 text-stone-900 outline-none ring-0 [box-shadow:none!important] placeholder:text-stone-400 focus:[box-shadow:none!important] focus-visible:[box-shadow:none!important] disabled:opacity-60 dark:text-stone-100 dark:placeholder:text-stone-500",
          mode === "url"
            ? "font-sans text-base leading-6 sm:text-[15px]"
            : "font-mono text-base leading-relaxed sm:text-xs",
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

function RandomGameLink({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button
      aria-label="Analyze a random iconic game"
      className={cn(
        "inline-flex items-center gap-1 rounded-full text-xs outline-none transition-colors",
        disabled
          ? "cursor-default text-stone-300 dark:text-stone-600"
          : "cursor-pointer text-stone-400 hover:text-stone-600 dark:text-stone-500 dark:hover:text-stone-300",
      )}
      disabled={disabled}
      onClick={onClick}
      title="Analyze a random iconic game"
      type="button"
    >
      <Dices aria-hidden="true" className="size-3.5" strokeWidth={2} />
      try random
    </button>
  );
}

function stripNewlines(value: string): string {
  return value.replace(/[\r\n]+/g, "");
}

function isValidInput(mode: Mode, value: string): boolean {
  return mode === "url" ? isValidGameUrl(value) : isValidPgn(value);
}

function isValidGameUrl(value: string): boolean {
  return isSupportedGameAnalysisUrl(value);
}

function isValidPgn(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed.length < 4) {
    return false;
  }
  return PGN_TAG_PATTERN.test(trimmed) || PGN_MOVE_PATTERN.test(trimmed);
}

function buildRequest(
  mode: Mode,
  values: { url: string; pgn: string; turnstileToken: string | null },
): GameAnalysisImportRequest {
  const target = mode === "url" ? extractGameImportTarget(values.url) : null;
  const sourceFields =
    mode === "url"
      ? ({
          source: target?.source ?? "chess_com_live_url",
          url: normalizeGameImportUrl(values.url),
        } as const)
      : ({ source: "pgn", pgn: values.pgn } as const);
  const request: GameAnalysisImportRequest = {
    ...sourceFields,
    explain_significance: [...DEFAULT_EXPLAIN_SIGNIFICANCE],
    include_context: false,
    use_baseline_fallback: false,
  };
  if (values.turnstileToken !== null) {
    request.turnstile_token = values.turnstileToken;
  }
  return request;
}

function withoutTurnstileToken(request: GameAnalysisImportRequest): GameAnalysisImportRequest {
  const { turnstile_token: _turnstileToken, ...nextRequest } = request;
  return nextRequest;
}

function orientationHintForTarget(target: ExternalGameTarget | null): ExternalGameTarget | null {
  return target !== null && target.boardOrientation !== null ? target : null;
}

function importWithOptionalHint(
  onImport: AnalysisImportPanelProps["onImport"],
  request: GameAnalysisImportRequest,
  hintedTarget: ExternalGameTarget | null,
): Promise<void> {
  return hintedTarget === null ? onImport(request) : onImport(request, hintedTarget);
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

function isTurnstileFailure(error: unknown): boolean {
  return error instanceof ApiError && error.code === "turnstile_failed";
}

interface TurnstileApi {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
      theme: "auto";
    },
  ) => string;
  remove?: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
    __g6TurnstileScriptLoading?: boolean;
  }
}

function TurnstileWidget({
  siteKey,
  onToken,
  onExpire,
}: {
  siteKey: string;
  onToken: (token: string) => void;
  onExpire: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let widgetId: string | null = null;
    let timer: number | undefined;
    ensureTurnstileScript();

    function renderWhenReady() {
      const container = containerRef.current;
      if (!container || widgetId !== null || !window.turnstile) {
        return;
      }
      widgetId = window.turnstile.render(container, {
        sitekey: siteKey,
        callback: onToken,
        "expired-callback": onExpire,
        "error-callback": onExpire,
        theme: "auto",
      });
      if (timer !== undefined) {
        window.clearInterval(timer);
        timer = undefined;
      }
    }

    renderWhenReady();
    if (widgetId === null) {
      timer = window.setInterval(renderWhenReady, 100);
    }

    return () => {
      if (timer !== undefined) {
        window.clearInterval(timer);
      }
      if (widgetId !== null && window.turnstile?.remove) {
        window.turnstile.remove(widgetId);
      }
    };
  }, [onExpire, onToken, siteKey]);

  return <div ref={containerRef} />;
}

function ensureTurnstileScript() {
  if (typeof window === "undefined" || window.turnstile || window.__g6TurnstileScriptLoading) {
    return;
  }
  window.__g6TurnstileScriptLoading = true;
  const script = document.createElement("script");
  script.async = true;
  script.defer = true;
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  document.head.appendChild(script);
}
