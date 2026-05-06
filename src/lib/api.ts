import type {
  GameAnalysisImportRequest,
  GameAnalysisImportResponse,
  GameAnalysisSnapshot,
} from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_G6_API_BASE_URL ?? "http://127.0.0.1:8001").replace(
  /\/$/,
  "",
);

export async function startImportedGameAnalysis(
  request: GameAnalysisImportRequest,
  signal?: AbortSignal,
): Promise<GameAnalysisImportResponse> {
  return postJson<GameAnalysisImportResponse>("/api/game-analysis/import", request, signal);
}

export async function getCachedChessComLiveGameAnalysis(
  externalGameId: string,
  signal?: AbortSignal,
): Promise<GameAnalysisImportResponse> {
  return getJson<GameAnalysisImportResponse>(
    `/api/game-analysis/import/chess-com/live/${encodeURIComponent(externalGameId)}`,
    signal,
  );
}

export async function getCachedLichessGameAnalysis(
  externalGameId: string,
  signal?: AbortSignal,
): Promise<GameAnalysisImportResponse> {
  return getJson<GameAnalysisImportResponse>(
    `/api/game-analysis/import/lichess/${encodeURIComponent(externalGameId)}`,
    signal,
  );
}

export async function pollGameAnalysis(
  statusUrl: string,
  signal?: AbortSignal,
): Promise<GameAnalysisSnapshot> {
  return getJson<GameAnalysisSnapshot>(statusUrl, signal);
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly code: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    detail: string,
    options: { code?: string | null; retryAfterSeconds?: number | null } = {},
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = options.code ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const requestInit: RequestInit = signal === undefined ? {} : { signal };
  const response = await fetch(apiUrl(path), requestInit);
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...(signal === undefined ? {} : { signal }),
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
}

function apiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }
  const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  return `${API_BASE_URL}${path}`;
}

async function apiError(response: Response): Promise<ApiError> {
  const fallback = `API request failed with ${response.status}`;
  const retryAfterSeconds = retryAfterSecondsFromHeader(response.headers.get("Retry-After"));
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      code?: unknown;
      message?: unknown;
    };
    const parsed = parseApiErrorPayload(payload, fallback);
    return new ApiError(response.status, parsed.detail, {
      code: parsed.code,
      retryAfterSeconds,
    });
  } catch {
    return new ApiError(response.status, fallback, { retryAfterSeconds });
  }
}

function parseApiErrorPayload(
  payload: { detail?: unknown; code?: unknown; message?: unknown },
  fallback: string,
): { detail: string; code: string | null } {
  if (typeof payload.detail === "string") {
    return {
      detail: payload.detail,
      code: typeof payload.code === "string" ? payload.code : null,
    };
  }
  if (isObject(payload.detail)) {
    const detail = payload.detail as { code?: unknown; message?: unknown };
    return {
      detail: typeof detail.message === "string" ? detail.message : fallback,
      code: typeof detail.code === "string" ? detail.code : null,
    };
  }
  return {
    detail: typeof payload.message === "string" ? payload.message : fallback,
    code: typeof payload.code === "string" ? payload.code : null,
  };
}

function retryAfterSecondsFromHeader(value: string | null): number | null {
  if (value === null) {
    return null;
  }
  const seconds = Number.parseInt(value, 10);
  if (Number.isFinite(seconds) && seconds > 0) {
    return seconds;
  }
  const date = Date.parse(value);
  if (Number.isNaN(date)) {
    return null;
  }
  return Math.max(1, Math.ceil((date - Date.now()) / 1000));
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
