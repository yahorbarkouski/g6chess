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

export async function pollGameAnalysis(
  statusUrl: string,
  signal?: AbortSignal,
): Promise<GameAnalysisSnapshot> {
  return getJson<GameAnalysisSnapshot>(statusUrl, signal);
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
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
  try {
    const payload = (await response.json()) as { detail?: unknown };
    const detail = typeof payload.detail === "string" ? payload.detail : fallback;
    return new ApiError(response.status, detail);
  } catch {
    return new ApiError(response.status, fallback);
  }
}
