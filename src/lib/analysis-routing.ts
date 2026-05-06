const CHESS_COM_HOSTS = new Set(["chess.com", "www.chess.com"]);
const LICHESS_HOSTS = new Set(["lichess.org", "www.lichess.org"]);
const G6_HOSTS = new Set(["g6chess.com", "www.g6chess.com"]);
const ANALYSIS_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const NUMERIC_ID_PATTERN = /^\d+$/;
const LICHESS_ID_PATTERN = /^[A-Za-z0-9]{8}$/;

export type ExternalGameSource = "chess_com_live_url" | "lichess_game_url";

export interface ExternalGameTarget {
  source: ExternalGameSource;
  externalGameId: string;
}

export interface AnalysisRouteState {
  kind: "home" | "chess_com_live" | "lichess_game" | "analysis";
  externalSource: ExternalGameSource | null;
  externalGameId: string | null;
  analysisId: string | null;
  ply: number | null;
  canonicalPath: string | null;
}

export interface SharedAnalysisTarget {
  analysisId: string;
  externalSource: ExternalGameSource | null;
  externalGameId: string | null;
}

export function readAnalysisRoute(): AnalysisRouteState {
  if (typeof window === "undefined") {
    return homeRoute();
  }
  return parseAnalysisRoute(window.location.pathname, window.location.search);
}

export function parseAnalysisRoute(pathname: string, search = ""): AnalysisRouteState {
  const params = new URLSearchParams(search);
  const ply = parsePly(params.get("ply"));
  const queryAnalysisId = parseAnalysisId(params.get("analysis"));
  const parts = pathParts(pathname);
  const chessComGameId = matchChessComRouteParts(parts);

  if (chessComGameId !== null) {
    return {
      kind: "chess_com_live",
      externalSource: "chess_com_live_url",
      externalGameId: chessComGameId,
      analysisId: queryAnalysisId,
      ply,
      canonicalPath: canonicalPathForRoute({
        analysisId: queryAnalysisId,
        externalSource: "chess_com_live_url",
        externalGameId: chessComGameId,
        ply,
      }),
    };
  }

  const lichessGameId = matchLichessRouteParts(parts);
  if (lichessGameId !== null) {
    return {
      kind: "lichess_game",
      externalSource: "lichess_game_url",
      externalGameId: lichessGameId,
      analysisId: queryAnalysisId,
      ply,
      canonicalPath: canonicalPathForRoute({
        analysisId: queryAnalysisId,
        externalSource: "lichess_game_url",
        externalGameId: lichessGameId,
        ply,
      }),
    };
  }

  if (parts[0] === "analysis") {
    const analysisId = parseAnalysisId(parts[1]);
    if (analysisId !== null) {
      return {
        kind: "analysis",
        externalSource: null,
        externalGameId: null,
        analysisId,
        ply,
        canonicalPath: canonicalPathForRoute({
          analysisId,
          externalSource: null,
          externalGameId: null,
          ply,
        }),
      };
    }
  }

  return homeRoute();
}

export function extractChessComLiveGameId(value: string): string | null {
  const target = extractGameImportTarget(value);
  return target?.source === "chess_com_live_url" ? target.externalGameId : null;
}

export function extractLichessGameId(value: string): string | null {
  const target = extractGameImportTarget(value);
  return target?.source === "lichess_game_url" ? target.externalGameId : null;
}

export function extractGameImportTarget(value: string): ExternalGameTarget | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = parseUrlLike(trimmed);
  if (parsed === null) {
    return null;
  }

  const host = parsed.hostname.toLowerCase();
  if (CHESS_COM_HOSTS.has(host)) {
    return targetFromId("chess_com_live_url", matchChessComPath(parsed.pathname));
  }
  if (LICHESS_HOSTS.has(host)) {
    return targetFromId("lichess_game_url", matchLichessPath(parsed.pathname));
  }
  if (G6_HOSTS.has(host)) {
    const parts = pathParts(parsed.pathname);
    return (
      targetFromId("lichess_game_url", matchLichessRouteParts(parts)) ??
      targetFromId("chess_com_live_url", matchChessComRouteParts(parts))
    );
  }
  return null;
}

export function isSupportedChessComAnalysisUrl(value: string): boolean {
  return extractChessComLiveGameId(value) !== null;
}

export function isSupportedGameAnalysisUrl(value: string): boolean {
  return extractGameImportTarget(value) !== null;
}

export function normalizeChessComImportUrl(value: string): string {
  const externalGameId = extractChessComLiveGameId(value);
  return externalGameId === null ? value.trim() : chessComLiveGameUrl(externalGameId);
}

export function normalizeGameImportUrl(value: string): string {
  const target = extractGameImportTarget(value);
  if (target === null) {
    return value.trim();
  }
  return target.source === "lichess_game_url"
    ? lichessGameUrl(target.externalGameId)
    : chessComLiveGameUrl(target.externalGameId);
}

export function chessComLiveGameUrl(externalGameId: string): string {
  return `https://www.chess.com/game/live/${externalGameId}`;
}

export function lichessGameUrl(externalGameId: string): string {
  return `https://lichess.org/${externalGameId}`;
}

export function analysisStatusUrl(analysisId: string): string {
  return `/api/game-analysis/${encodeURIComponent(analysisId)}`;
}

export function canonicalPathForRoute({
  analysisId,
  externalSource,
  externalGameId,
  ply,
}: {
  analysisId: string | null;
  externalSource?: ExternalGameSource | null;
  externalGameId: string | null;
  ply: number | null;
}): string | null {
  if (externalGameId !== null) {
    const source = externalSource ?? "chess_com_live_url";
    const path =
      source === "lichess_game_url"
        ? `/lichess/${encodeURIComponent(externalGameId)}`
        : `/game/live/${externalGameId}`;
    return withAnalysisQuery(path, analysisId, ply);
  }
  if (analysisId !== null) {
    return withAnalysisQuery(`/analysis/${encodeURIComponent(analysisId)}`, null, ply);
  }
  return null;
}

export function replaceAnalysisUrl(target: SharedAnalysisTarget, ply: number | null): void {
  if (typeof window === "undefined") {
    return;
  }
  const path = canonicalPathForRoute({
    analysisId: target.analysisId,
    externalSource: target.externalSource,
    externalGameId: target.externalGameId,
    ply,
  });
  if (path === null || path === `${window.location.pathname}${window.location.search}`) {
    return;
  }
  window.history.replaceState(null, "", path);
}

export function pushWithPath(path: string): void {
  if (typeof window === "undefined") {
    return;
  }
  if (path === currentBrowserPath()) {
    return;
  }
  window.history.pushState(null, "", path);
}

export function replaceWithPath(path: string): void {
  if (typeof window === "undefined") {
    return;
  }
  if (path === currentBrowserPath()) {
    return;
  }
  window.history.replaceState(null, "", path);
}

export function currentBrowserPath(): string {
  if (typeof window === "undefined") {
    return "/";
  }
  return `${window.location.pathname}${window.location.search}`;
}

function homeRoute(): AnalysisRouteState {
  return {
    kind: "home",
    externalSource: null,
    externalGameId: null,
    analysisId: null,
    ply: null,
    canonicalPath: null,
  };
}

function withAnalysisQuery(
  basePath: string,
  analysisId: string | null,
  ply: number | null,
): string {
  const params = new URLSearchParams();
  if (analysisId !== null) {
    params.set("analysis", analysisId);
  }
  if (ply !== null && ply > 1) {
    params.set("ply", String(ply));
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

function parseUrlLike(value: string): URL | null {
  if (value.startsWith("/")) {
    try {
      return new URL(value, "https://g6chess.com");
    } catch {
      return null;
    }
  }

  if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) {
    try {
      return new URL(`https://${value}`);
    } catch {
      return null;
    }
  }

  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function pathParts(pathname: string): string[] {
  return pathname
    .split("/")
    .filter(Boolean)
    .map((part) => {
      try {
        return decodeURIComponent(part);
      } catch {
        return part;
      }
    });
}

function matchChessComRouteParts(parts: string[]): string | null {
  if (parts[0] === "analysis" && parts[1] === "game" && parts[2] === "live") {
    return normalizeNumericId(parts[3]);
  }
  if (parts[0] === "game" && parts[1] === "live") {
    return normalizeNumericId(parts[2]);
  }
  if (parts[0] === "game") {
    return normalizeNumericId(parts[1]);
  }
  if (parts[0] === "live") {
    return normalizeNumericId(parts[1]);
  }
  return null;
}

function matchLichessRouteParts(parts: string[]): string | null {
  if (parts[0] === "lichess") {
    return normalizeLichessId(parts[1]);
  }
  return null;
}

function matchChessComPath(pathname: string): string | null {
  const parts = pathParts(pathname);
  return matchChessComRouteParts(parts);
}

function matchLichessPath(pathname: string): string | null {
  const parts = pathParts(pathname);
  if (parts[0] === "game" && parts[1] === "export") {
    return normalizeLichessId(parts[2]);
  }
  return normalizeLichessId(parts[0]);
}

function targetFromId(source: ExternalGameSource, externalGameId: string | null) {
  return externalGameId === null ? null : { source, externalGameId };
}

function parsePly(value: string | null): number | null {
  if (value === null) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

function parseAnalysisId(value: string | undefined | null): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  const trimmed = value.trim();
  return ANALYSIS_ID_PATTERN.test(trimmed) ? trimmed : null;
}

function normalizeNumericId(value: string | undefined): string | null {
  if (value === undefined) {
    return null;
  }
  const trimmed = value.trim();
  return NUMERIC_ID_PATTERN.test(trimmed) ? trimmed : null;
}

function normalizeLichessId(value: string | undefined): string | null {
  if (value === undefined) {
    return null;
  }
  const trimmed = value.trim();
  return LICHESS_ID_PATTERN.test(trimmed) ? trimmed : null;
}
