/**
 * Coastal Ledger integration layer: one typed, trace-aware client for the White Bird Django Ninja API.
 * All feature pages must use this module rather than constructing ad hoc requests.
 */

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api/site-management/v1").replace(/\/$/, "");

export type ApiFieldErrors = Record<string, string[] | string>;

export class ApiError extends Error {
  status: number;
  code: string;
  traceId?: string;
  fields?: ApiFieldErrors;

  constructor(input: { status: number; code: string; message: string; traceId?: string; fields?: ApiFieldErrors }) {
    super(input.message);
    this.name = "ApiError";
    this.status = input.status;
    this.code = input.code;
    this.traceId = input.traceId;
    this.fields = input.fields;
  }
}

export interface AuthUser {
  id: number;
  email: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  role: string;
  avatar?: string | null;
  timezone?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: AuthUser;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown; skipAuth?: boolean };

class WhiteBirdApiClient {
  private accessToken: string | null = null;

  setAccessToken(token: string | null) { this.accessToken = token; }
  getAccessToken() { return this.accessToken; }
  private endpoint(path: string) { return path.startsWith("http") ? path : `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`; }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: suppliedHeaders, skipAuth, ...rest } = options;
    const headers = new Headers(suppliedHeaders);
    const requestId = crypto.randomUUID?.();
    if (requestId) headers.set("X-Request-ID", requestId);
    if (!skipAuth && this.accessToken) headers.set("Authorization", `Bearer ${this.accessToken}`);
    let requestBody: BodyInit | undefined;
    if (body instanceof FormData || body instanceof Blob || typeof body === "string") requestBody = body;
    else if (body !== undefined) { headers.set("Content-Type", "application/json"); requestBody = JSON.stringify(body); }
    let response: Response;
    try { response = await fetch(this.endpoint(path), { ...rest, headers, body: requestBody, credentials: "include", cache: "no-store" }); }
    catch { throw new ApiError({ status: 0, code: "network_error", message: "The operations service could not be reached. Check the API origin and your connection." }); }
    const traceId = response.headers.get("X-Request-ID") || undefined;
    const contentType = response.headers.get("content-type") || "";
    const payload = response.status === 204 ? null : contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const error = typeof payload === "object" && payload && "error" in payload ? (payload as { error: Record<string, unknown> }).error : {};
      throw new ApiError({ status: response.status, code: String(error.code || `http_${response.status}`), message: String(error.message || "The request could not be completed."), traceId: String(error.trace_id || traceId || "") || undefined, fields: (error.fields as ApiFieldErrors | undefined) || undefined });
    }
    return payload as T;
  }
  get<T>(path: string) { return this.request<T>(path, { method: "GET" }); }
  post<T>(path: string, body?: unknown) { return this.request<T>(path, { method: "POST", body }); }
  put<T>(path: string, body?: unknown) { return this.request<T>(path, { method: "PUT", body }); }
  patch<T>(path: string, body?: unknown) { return this.request<T>(path, { method: "PATCH", body }); }
  delete<T>(path: string) { return this.request<T>(path, { method: "DELETE" }); }
}

export const api = new WhiteBirdApiClient();
export function queryString(values: Record<string, string | number | undefined | null>) { const query = new URLSearchParams(); Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== "") query.set(key, String(value)); }); const output = query.toString(); return output ? `?${output}` : ""; }
export function asPaginated(value: unknown): Paginated<Record<string, unknown>> { if (value && typeof value === "object" && "results" in value && Array.isArray((value as Paginated<Record<string, unknown>>).results)) return value as Paginated<Record<string, unknown>>; return { count: Array.isArray(value) ? value.length : 0, next: null, previous: null, results: Array.isArray(value) ? value : [] }; }
export function readableApiError(error: unknown) { return error instanceof ApiError ? error : new ApiError({ status: 0, code: "unexpected_error", message: "An unexpected error interrupted this operation." }); }
