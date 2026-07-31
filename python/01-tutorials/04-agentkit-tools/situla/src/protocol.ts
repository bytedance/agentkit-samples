export const APP_SERVER_PATH = "/v1/codex/app-server/";

export type RpcId = number | string;

export interface RpcRequest {
  id: RpcId;
  method: string;
  params?: Record<string, unknown>;
}

export interface RpcNotification {
  method: string;
  params?: Record<string, unknown>;
}

export interface RpcErrorBody {
  code: number | string;
  message: string;
  data?: unknown;
}

export interface RpcResponse {
  id: RpcId;
  result?: unknown;
  error?: RpcErrorBody | unknown;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function parseSandboxUrl(input: string): URL {
  const value = input.trim();
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError("sandbox URL is invalid");
  }

  if (!["http:", "https:", "ws:", "wss:"].includes(url.protocol)) {
    throw new TypeError("sandbox URL must use http, https, ws, or wss");
  }
  if (!url.hostname) {
    throw new TypeError("sandbox URL must include a host");
  }
  if (url.username || url.password) {
    throw new TypeError(
      "userinfo credentials are not supported; keep gateway credentials in the URL query",
    );
  }
  if (url.hash) {
    throw new TypeError("sandbox URL must not include a fragment");
  }

  const normalizedPath = url.pathname.replace(/\/+$/, "");
  if (normalizedPath !== "" && normalizedPath !== APP_SERVER_PATH.slice(0, -1)) {
    throw new TypeError(
      `sandbox URL path must be / or ${APP_SERVER_PATH}; got ${JSON.stringify(url.pathname)}`,
    );
  }
  return url;
}

/** Convert an AgentKit public sandbox URL into its Codex app-server URL. */
export function appServerWebSocketUrl(input: string): string {
  const url = parseSandboxUrl(input);
  url.protocol = url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
  url.pathname = APP_SERVER_PATH;
  url.hash = "";
  return url.toString();
}

/** Build a sandbox data-plane URL without exposing its auth query to the browser. */
export function sandboxServiceUrl(
  input: string,
  pathname: string,
  websocket = false,
): string {
  if (!pathname.startsWith("/")) throw new TypeError("sandbox service path must start with /");
  const url = parseSandboxUrl(input);
  if (websocket) {
    url.protocol = url.protocol === "https:" || url.protocol === "wss:" ? "wss:" : "ws:";
  } else {
    url.protocol = url.protocol === "https:" || url.protocol === "wss:" ? "https:" : "http:";
  }
  const currentPath = url.pathname.replace(/\/+$/, "");
  const basePath = currentPath === APP_SERVER_PATH.slice(0, -1) ? "" : currentPath;
  url.pathname = `${basePath}${pathname}`;
  url.hash = "";
  return url.toString();
}

/** Keep a URL useful in logs without exposing its gateway query credentials. */
export function redactedUrl(input: string): string {
  const url = parseSandboxUrl(input);
  const hadQuery = url.search.length > 0;
  url.search = "";
  return `${url.toString()}${hadQuery ? "?<redacted>" : ""}`;
}

/** Redact full URLs and non-trivial query values if an upstream error echoes them. */
export function redactSensitiveText(text: string, inputs: readonly string[]): string {
  const replacements = new Map<string, string>();
  for (const input of inputs) {
    if (!input) continue;
    try {
      const url = parseSandboxUrl(input);
      const replacement = redactedUrl(input);
      replacements.set(input.trim(), replacement);
      replacements.set(url.toString(), replacement);
      for (const value of url.searchParams.values()) {
        if (value.length < 8) continue;
        replacements.set(value, "<redacted>");
        replacements.set(encodeURIComponent(value), "<redacted>");
      }
    } catch {
      // Ignore invalid candidates; their parse errors never include a query string.
    }
  }
  let result = text;
  for (const [sensitive, replacement] of [...replacements].sort(
    ([left], [right]) => right.length - left.length,
  )) {
    result = result.replaceAll(sensitive, replacement);
  }
  return result;
}
