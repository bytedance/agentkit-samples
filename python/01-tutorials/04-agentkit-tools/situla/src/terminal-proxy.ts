import { once } from "node:events";
import type { IncomingMessage, ServerResponse } from "node:http";
import { isIP } from "node:net";
import type { Duplex } from "node:stream";
import {
  WebSocket as ProxyWebSocket,
  WebSocketServer,
  type RawData,
} from "ws";

export interface SandboxTerminalSession {
  sandboxServiceUrl(pathname: string, websocket?: boolean): string;
  safeError(error: unknown): string;
}

interface SandboxTerminalProxyOptions {
  getSession: (sessionId: string) => SandboxTerminalSession | undefined;
}

interface ProxyConnection {
  browser: ProxyWebSocket;
  upstream: ProxyWebSocket;
}

const MAX_PENDING_TERMINAL_BYTES = 64 * 1024;
const COMMON_HEADERS = {
  "cross-origin-resource-policy": "same-origin",
  "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff",
};

export class SandboxTerminalProxy {
  readonly #getSession: SandboxTerminalProxyOptions["getSession"];
  readonly #webSocketServer = new WebSocketServer({ noServer: true });
  readonly #connections = new Map<string, Set<ProxyConnection>>();
  readonly #terminalHosts = new Map<string, string>();

  constructor(options: SandboxTerminalProxyOptions) {
    this.#getSession = options.getSession;
  }

  async terminalUrl(
    requestHost: string | undefined,
    sessionId: string,
    shellSessionId?: string,
  ): Promise<{ url: string; shellSessionId: string }> {
    if (!requestHost) throw httpError(400, "terminal request is missing Host");
    const session = this.#getSession(sessionId);
    if (!session) throw httpError(404, "session not found");

    const resolvedShellSessionId = shellSessionId?.trim() ||
      await createShellSession(session);
    const url = isolatedLoopbackUrl(requestHost, "terminal");
    url.pathname = `/terminal/${encodeURIComponent(sessionId)}/terminal`;
    url.searchParams.set("session_id", resolvedShellSessionId);
    this.#terminalHosts.set(sessionId, url.host);
    return { url: url.toString(), shellSessionId: resolvedShellSessionId };
  }

  handleHttp(
    request: IncomingMessage,
    response: ServerResponse,
    url: URL,
  ): Promise<boolean> {
    if (!url.pathname.startsWith("/terminal/")) return Promise.resolve(false);
    return this.#handleHttp(request, response, url)
      .then(() => true)
      .catch((error: unknown) => {
        if (!response.headersSent) sendJson(response, 500, { error: errorText(error) });
        else response.end();
        return true;
      });
  }

  handleUpgrade(request: IncomingMessage, socket: Duplex, head: Buffer): boolean {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    if (!url.pathname.startsWith("/terminal/")) return false;
    this.#handleUpgrade(request, socket, head, url);
    return true;
  }

  closeSession(sessionId: string): void {
    this.#terminalHosts.delete(sessionId);
    const connections = this.#connections.get(sessionId);
    if (!connections) return;
    this.#connections.delete(sessionId);
    for (const { browser, upstream } of connections) {
      browser.close();
      upstream.close();
    }
  }

  close(): void {
    for (const sessionId of this.#connections.keys()) this.closeSession(sessionId);
    this.#terminalHosts.clear();
    this.#webSocketServer.close();
  }

  async #handleHttp(
    request: IncomingMessage,
    response: ServerResponse,
    url: URL,
  ): Promise<void> {
    if (!isTrustedBrowserRequest(request)) {
      sendJson(response, 403, { error: "untrusted Host or Origin" });
      return;
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      sendJson(response, 405, { error: "method not allowed" });
      return;
    }
    const match = url.pathname.match(/^\/terminal\/([^/]+)\/(.*)$/);
    if (!match) {
      sendJson(response, 404, { error: "sandbox terminal route not found" });
      return;
    }
    const sessionId = decodeSessionId(match[1], response);
    if (!sessionId) return;
    const session = this.#getSession(sessionId);
    if (!session) {
      sendJson(response, 404, { error: "session not found" });
      return;
    }
    if (this.#terminalHosts.get(sessionId) !== request.headers.host) {
      sendJson(response, 403, { error: "sandbox terminal Host does not match its window URL" });
      return;
    }
    const action = match[2];
    const upstreamPath = terminalUpstreamPath(action);
    if (!upstreamPath) {
      sendJson(response, 404, { error: "sandbox terminal route not found" });
      return;
    }

    let upstream: Response;
    try {
      upstream = await fetch(session.sandboxServiceUrl(upstreamPath), {
        method: request.method,
        headers: terminalForwardHeaders(request),
        signal: AbortSignal.timeout(30_000),
      });
    } catch (error) {
      sendJson(response, 502, { error: session.safeError(error) });
      return;
    }
    if (!upstream.ok) {
      sendJson(response, 502, {
        error: `sandbox terminal service returned HTTP ${upstream.status}`,
      });
      return;
    }

    response.writeHead(upstream.status, {
      ...COMMON_HEADERS,
      ...(action === "terminal"
        ? { "cross-origin-resource-policy": "cross-origin" }
        : {}),
      "content-type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "cache-control": action.startsWith("static/")
        ? "private, max-age=3600"
        : "no-store",
    });
    if (request.method === "HEAD" || !upstream.body) {
      response.end();
      return;
    }
    try {
      const reader = upstream.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (response.destroyed) return;
        if (!response.write(Buffer.from(value))) await once(response, "drain");
      }
      response.end();
    } catch (error) {
      if (!response.destroyed) response.destroy(new Error(session.safeError(error)));
    }
  }

  #handleUpgrade(
    request: IncomingMessage,
    socket: Duplex,
    head: Buffer,
    url: URL,
  ): void {
    const match = url.pathname.match(/^\/terminal\/([^/]+)\/v1\/shell\/ws$/);
    if (!match || !isTrustedBrowserRequest(request)) {
      rejectUpgrade(socket, 401, "Unauthorized");
      return;
    }
    let sessionId: string;
    try {
      sessionId = decodeURIComponent(match[1]);
    } catch {
      rejectUpgrade(socket, 400, "Bad Request");
      return;
    }
    const session = this.#getSession(sessionId);
    if (!session) {
      rejectUpgrade(socket, 404, "Not Found");
      return;
    }
    if (this.#terminalHosts.get(sessionId) !== request.headers.host) {
      rejectUpgrade(socket, 403, "Forbidden");
      return;
    }

    this.#webSocketServer.handleUpgrade(request, socket, head, (browser) => {
      let upstream: ProxyWebSocket;
      try {
        const upstreamUrl = new URL(session.sandboxServiceUrl("/v1/shell/ws", true));
        const shellSessionId = url.searchParams.get("session_id")?.trim();
        if (shellSessionId) upstreamUrl.searchParams.set("session_id", shellSessionId);
        upstream = new ProxyWebSocket(upstreamUrl);
      } catch (error) {
        browser.close(1011, session.safeError(error).slice(0, 120));
        return;
      }
      const pair = { browser, upstream };
      const connections = this.#connections.get(sessionId) ?? new Set();
      connections.add(pair);
      this.#connections.set(sessionId, connections);
      let cleanedUp = false;
      const cleanup = () => {
        if (cleanedUp) return;
        cleanedUp = true;
        connections.delete(pair);
        if (connections.size === 0) this.#connections.delete(sessionId);
      };
      const pending: Array<{ data: RawData; isBinary: boolean }> = [];
      let pendingBytes = 0;

      browser.on("message", (data, isBinary) => {
        if (upstream.readyState === ProxyWebSocket.OPEN) {
          upstream.send(data, { binary: isBinary });
        } else if (upstream.readyState === ProxyWebSocket.CONNECTING) {
          pendingBytes += rawDataByteLength(data);
          if (pendingBytes > MAX_PENDING_TERMINAL_BYTES) {
            browser.close(1009, "too much pending terminal data");
            upstream.close();
            return;
          }
          pending.push({ data, isBinary });
        }
      });
      upstream.on("open", () => {
        for (const message of pending.splice(0)) {
          upstream.send(message.data, { binary: message.isBinary });
        }
        pendingBytes = 0;
      });
      upstream.on("message", (data, isBinary) => {
        if (browser.readyState === ProxyWebSocket.OPEN) {
          browser.send(data, { binary: isBinary });
        }
      });
      upstream.on("error", (error) => {
        if (browser.readyState === ProxyWebSocket.OPEN) {
          browser.close(1011, session.safeError(error).slice(0, 120));
        }
      });
      browser.on("close", () => {
        upstream.close();
        cleanup();
      });
      upstream.on("close", (code, reason) => {
        if (browser.readyState === ProxyWebSocket.OPEN) {
          browser.close(safeWebSocketCloseCode(code), reason.toString().slice(0, 120));
        }
        cleanup();
      });
      browser.on("error", () => upstream.close());
    });
  }
}

async function createShellSession(session: SandboxTerminalSession): Promise<string> {
  let response: Response;
  try {
    response = await fetch(session.sandboxServiceUrl("/v1/shell/terminal-url"), {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(30_000),
    });
  } catch (error) {
    throw httpError(502, session.safeError(error));
  }
  if (!response.ok) {
    throw httpError(502, `sandbox terminal service returned HTTP ${response.status}`);
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw httpError(502, "sandbox terminal service returned invalid JSON");
  }
  if (!isRecord(value) || typeof value.data !== "string") {
    throw httpError(502, "sandbox terminal service did not return a terminal URL");
  }
  let terminalUrl: URL;
  try {
    terminalUrl = new URL(value.data);
  } catch {
    throw httpError(502, "sandbox terminal service returned an invalid terminal URL");
  }
  const shellSessionId = terminalUrl.searchParams.get("session_id")?.trim();
  if (!shellSessionId) {
    throw httpError(502, "sandbox terminal service did not return a shell session ID");
  }
  return shellSessionId;
}

function isolatedLoopbackUrl(requestHost: string, label: string): URL {
  const url = new URL(`http://${requestHost}`);
  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  if (hostname === "localhost") {
    url.hostname = "127.0.0.1";
  } else if (isLoopbackHostname(hostname)) {
    url.hostname = "localhost";
  } else {
    throw httpError(403, `sandbox ${label} requires a loopback Host`);
  }
  return url;
}

function terminalUpstreamPath(action: string): string | undefined {
  if (action === "terminal") return "/terminal";
  if (
    action.startsWith("static/sandbox/") &&
    action.split("/").every((segment) => segment !== "" && segment !== "." && segment !== "..")
  ) {
    return `/${action}`;
  }
  return undefined;
}

function terminalForwardHeaders(request: IncomingMessage): Headers {
  const headers = new Headers();
  for (const name of ["accept", "accept-language", "user-agent"] as const) {
    const value = request.headers[name];
    if (typeof value === "string") headers.set(name, value);
  }
  return headers;
}

function decodeSessionId(value: string, response: ServerResponse): string | undefined {
  try {
    return decodeURIComponent(value);
  } catch {
    sendJson(response, 400, { error: "invalid session id" });
    return undefined;
  }
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    ...COMMON_HEADERS,
    "x-frame-options": "DENY",
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(value));
}

function rejectUpgrade(socket: Duplex, status: number, reason: string): void {
  socket.write(
    `HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\nContent-Type: text/plain\r\n\r\n${reason}`,
  );
  socket.destroy();
}

function isTrustedBrowserRequest(request: IncomingMessage): boolean {
  const host = request.headers.host;
  if (!host || !isLoopbackHostname(hostnameFromHost(host))) return false;
  const origin = request.headers.origin;
  if (!origin) return true;
  try {
    const originUrl = new URL(origin);
    return originUrl.protocol === "http:" && originUrl.host === host;
  } catch {
    return false;
  }
}

function hostnameFromHost(host: string): string {
  try {
    return new URL(`http://${host}`).hostname.replace(/^\[|\]$/g, "");
  } catch {
    return "";
  }
}

function isLoopbackHostname(hostname: string): boolean {
  if (hostname === "localhost") return true;
  const ipVersion = isIP(hostname);
  return (ipVersion === 4 && hostname.startsWith("127.")) ||
    (ipVersion === 6 && (hostname === "::1" || hostname === "0:0:0:0:0:0:0:1"));
}

function rawDataByteLength(data: RawData): number {
  if (Array.isArray(data)) return data.reduce((total, chunk) => total + chunk.byteLength, 0);
  return data.byteLength;
}

function safeWebSocketCloseCode(code: number): number {
  return code >= 1000 && code <= 4999 && ![1004, 1005, 1006, 1015].includes(code)
    ? code
    : 1000;
}

function httpError(status: number, message: string): Error & { status: number } {
  return Object.assign(new Error(message), { status });
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
