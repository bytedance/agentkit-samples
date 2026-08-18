import { once } from "node:events";
import type { IncomingMessage, ServerResponse } from "node:http";
import { isIP } from "node:net";
import type { Duplex } from "node:stream";
import {
  WebSocket as ProxyWebSocket,
  WebSocketServer,
  type RawData,
} from "ws";

export interface SandboxBrowserSession {
  sandboxServiceUrl(pathname: string, websocket?: boolean): string;
  safeError(error: unknown): string;
}

interface SandboxBrowserProxyOptions {
  getSession: (sessionId: string) => SandboxBrowserSession | undefined;
}

interface ProxyConnection {
  browser: ProxyWebSocket;
  upstream: ProxyWebSocket;
}

const MAX_PENDING_CDP_BYTES = 64 * 1024;
const CDP_COMMAND_TIMEOUT_MS = 10_000;
const COMMON_HEADERS = {
  "cross-origin-resource-policy": "same-origin",
  "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff",
};

export class SandboxBrowserProxy {
  readonly #getSession: SandboxBrowserProxyOptions["getSession"];
  readonly #webSocketServer = new WebSocketServer({ noServer: true });
  readonly #connections = new Map<string, Set<ProxyConnection>>();
  readonly #browserHosts = new Map<string, string>();

  constructor(options: SandboxBrowserProxyOptions) {
    this.#getSession = options.getSession;
  }

  handleHttp(
    request: IncomingMessage,
    response: ServerResponse,
    url: URL,
  ): Promise<boolean> {
    if (!url.pathname.startsWith("/browser/")) return Promise.resolve(false);
    return this.#handleHttp(request, response, url)
      .then(() => true)
      .catch((error: unknown) => {
        if (!response.headersSent) sendJson(response, 500, { error: errorText(error) });
        else response.end();
        return true;
      });
  }

  browserUrl(requestHost: string | undefined, sessionId: string): string {
    if (!requestHost) throw httpError(400, "browser request is missing Host");
    const url = new URL(`http://${requestHost}`);
    const hostname = url.hostname.replace(/^\[|\]$/g, "");
    if (hostname === "localhost") {
      url.hostname = "127.0.0.1";
    } else if (isLoopbackHostname(hostname)) {
      url.hostname = "localhost";
    } else {
      throw httpError(403, "sandbox browser requires a loopback Host");
    }
    url.pathname = `/browser/${encodeURIComponent(sessionId)}/browser-ui`;
    url.search = "";
    url.hash = "";
    this.#browserHosts.set(sessionId, url.host);
    return url.toString();
  }

  async navigate(sessionId: string, targetUrl: string): Promise<void> {
    const session = this.#getSession(sessionId);
    if (!session) throw httpError(404, "session not found");
    const infoResponse = await fetch(session.sandboxServiceUrl("/v1/browser/info"), {
      signal: AbortSignal.timeout(CDP_COMMAND_TIMEOUT_MS),
    });
    if (!infoResponse.ok) {
      throw new Error(`sandbox browser info returned HTTP ${infoResponse.status}`);
    }
    const cdpPath = browserCdpPath(await infoResponse.json());
    const socket = new ProxyWebSocket(session.sandboxServiceUrl(cdpPath, true));
    socket.on("error", () => undefined);
    try {
      await waitForWebSocketOpen(socket);
      const targetsResult = await sendCdpCommand(socket, 1, "Target.getTargets");
      let targetId = firstPageTargetId(targetsResult);
      let commandId = 2;
      if (!targetId) {
        const createResult = await sendCdpCommand(
          socket,
          commandId++,
          "Target.createTarget",
          { url: "about:blank" },
        );
        targetId = stringProperty(createResult, "targetId", "CDP create target result");
      }
      const attachResult = await sendCdpCommand(
        socket,
        commandId++,
        "Target.attachToTarget",
        { targetId, flatten: true },
      );
      const cdpSessionId = stringProperty(attachResult, "sessionId", "CDP attach result");
      await sendCdpCommand(
        socket,
        commandId++,
        "Page.navigate",
        { url: targetUrl },
        cdpSessionId,
      );
      await sendCdpCommand(
        socket,
        commandId,
        "Target.activateTarget",
        { targetId },
      );
    } finally {
      socket.close();
    }
  }

  closeSession(sessionId: string): void {
    this.#browserHosts.delete(sessionId);
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
    this.#browserHosts.clear();
    this.#webSocketServer.close();
  }

  handleUpgrade(request: IncomingMessage, socket: Duplex, head: Buffer): boolean {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    if (!url.pathname.startsWith("/browser/")) return false;
    this.#handleUpgrade(request, socket, head);
    return true;
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
    const match = url.pathname.match(/^\/browser\/([^/]+)\/(.*)$/);
    if (!match) {
      sendJson(response, 404, { error: "sandbox browser route not found" });
      return;
    }
    let sessionId: string;
    try {
      sessionId = decodeURIComponent(match[1]);
    } catch {
      sendJson(response, 400, { error: "invalid session id" });
      return;
    }
    const session = this.#getSession(sessionId);
    if (!session) {
      sendJson(response, 404, { error: "session not found" });
      return;
    }
    if (this.#browserHosts.get(sessionId) !== request.headers.host) {
      sendJson(response, 403, { error: "sandbox browser Host does not match its window URL" });
      return;
    }
    const action = match[2];
    const upstreamPath = browserUpstreamPath(action);
    if (!upstreamPath) {
      sendJson(response, 404, { error: "sandbox browser route not found" });
      return;
    }
    const prefix = `/browser/${encodeURIComponent(sessionId)}`;
    let upstream: Response;
    try {
      upstream = await fetch(session.sandboxServiceUrl(upstreamPath), {
        method: request.method,
        headers: browserForwardHeaders(request, prefix),
        signal: AbortSignal.timeout(30_000),
      });
    } catch (error) {
      sendJson(response, 502, { error: session.safeError(error) });
      return;
    }
    if (!upstream.ok) {
      sendJson(response, 502, {
        error: `sandbox browser service returned HTTP ${upstream.status}`,
      });
      return;
    }

    if (action === "v1/browser/info") {
      let value: unknown;
      try {
        value = localBrowserInfo(await upstream.json(), request, prefix);
      } catch (error) {
        sendJson(response, 502, {
          error: `sandbox browser service returned invalid browser info: ${session.safeError(error)}`,
        });
        return;
      }
      sendJson(response, 200, value);
      return;
    }

    response.writeHead(upstream.status, {
      ...COMMON_HEADERS,
      ...(action === "browser-ui"
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

  #handleUpgrade(request: IncomingMessage, socket: Duplex, head: Buffer): void {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    const match = url.pathname.match(
      /^\/browser\/([^/]+)\/(cdp\/devtools\/(?:browser|page)\/[^/]+)$/,
    );
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
    if (this.#browserHosts.get(sessionId) !== request.headers.host) {
      rejectUpgrade(socket, 403, "Forbidden");
      return;
    }
    this.#webSocketServer.handleUpgrade(request, socket, head, (browser) => {
      let upstream: ProxyWebSocket;
      try {
        upstream = new ProxyWebSocket(session.sandboxServiceUrl(`/${match[2]}`, true));
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
          if (pendingBytes > MAX_PENDING_CDP_BYTES) {
            browser.close(1009, "too much pending CDP data");
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

function browserUpstreamPath(action: string): string | undefined {
  if (action === "browser-ui") return "/browser-ui";
  if (action === "v1/browser/info") return "/v1/browser/info";
  if (
    action.startsWith("static/") &&
    action.split("/").every((segment) => segment !== "" && segment !== "." && segment !== "..")
  ) {
    return `/${action}`;
  }
  return undefined;
}

function browserForwardHeaders(request: IncomingMessage, prefix: string): Headers {
  const headers = new Headers();
  for (const name of ["accept", "accept-language", "user-agent"] as const) {
    const value = request.headers[name];
    if (typeof value === "string") headers.set(name, value);
  }
  headers.set("x-forwarded-host", request.headers.host ?? "localhost");
  headers.set("x-forwarded-proto", "http");
  headers.set("x-forwarded-prefix", prefix);
  return headers;
}

function localBrowserInfo(value: unknown, request: IncomingMessage, prefix: string): unknown {
  if (!isRecord(value) || !isRecord(value.data) || typeof value.data.cdp_url !== "string") {
    throw new TypeError("browser info is missing data.cdp_url");
  }
  const cdpPath = browserCdpPath(value);
  const host = request.headers.host;
  if (!host) throw new TypeError("browser proxy request is missing Host");
  const localCdp = new URL(`ws://${host}`);
  localCdp.pathname = `${prefix}${cdpPath}`;
  localCdp.search = "";
  const localPage = new URL(`http://${host}`);
  localPage.pathname = `${prefix}/browser-ui`;
  const data: Record<string, unknown> = {
    ...value.data,
    cdp_url: localCdp.toString(),
    cdp_ui_url: localPage.toString(),
  };
  delete data.vnc_url;
  return { ...value, data };
}

function browserCdpPath(value: unknown): string {
  if (!isRecord(value) || !isRecord(value.data) || typeof value.data.cdp_url !== "string") {
    throw new TypeError("browser info is missing data.cdp_url");
  }
  const upstreamCdp = new URL(value.data.cdp_url);
  const markerIndex = upstreamCdp.pathname.lastIndexOf("/cdp/devtools/");
  if (markerIndex < 0) throw new TypeError("browser info returned an invalid CDP URL");
  return upstreamCdp.pathname.slice(markerIndex);
}

function waitForWebSocketOpen(socket: ProxyWebSocket): Promise<void> {
  if (socket.readyState === ProxyWebSocket.OPEN) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("sandbox browser CDP connection timed out"));
    }, CDP_COMMAND_TIMEOUT_MS);
    const cleanup = () => {
      clearTimeout(timer);
      socket.off("open", onOpen);
      socket.off("error", onError);
      socket.off("close", onClose);
    };
    const onOpen = () => {
      cleanup();
      resolve();
    };
    const onError = (error: Error) => {
      cleanup();
      reject(error);
    };
    const onClose = () => {
      cleanup();
      reject(new Error("sandbox browser CDP closed before connecting"));
    };
    socket.on("open", onOpen);
    socket.on("error", onError);
    socket.on("close", onClose);
  });
}

function sendCdpCommand(
  socket: ProxyWebSocket,
  id: number,
  method: string,
  params?: Record<string, unknown>,
  sessionId?: string,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(`sandbox browser CDP ${method} timed out`));
    }, CDP_COMMAND_TIMEOUT_MS);
    const cleanup = () => {
      clearTimeout(timer);
      socket.off("message", onMessage);
      socket.off("close", onClose);
    };
    const onMessage = (raw: RawData) => {
      let response: unknown;
      try {
        response = JSON.parse(raw.toString());
      } catch {
        return;
      }
      if (!isRecord(response) || response.id !== id) return;
      cleanup();
      if (isRecord(response.error)) {
        reject(new Error(
          typeof response.error.message === "string"
            ? response.error.message
            : `sandbox browser CDP ${method} failed`,
        ));
        return;
      }
      resolve(response.result);
    };
    const onClose = () => {
      cleanup();
      reject(new Error(`sandbox browser CDP closed during ${method}`));
    };
    socket.on("message", onMessage);
    socket.on("close", onClose);
    try {
      socket.send(JSON.stringify({
        id,
        method,
        ...(params ? { params } : {}),
        ...(sessionId ? { sessionId } : {}),
      }));
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}

function firstPageTargetId(value: unknown): string | undefined {
  if (!isRecord(value) || !Array.isArray(value.targetInfos)) return undefined;
  for (const target of value.targetInfos) {
    if (isRecord(target) && target.type === "page" && typeof target.targetId === "string") {
      return target.targetId;
    }
  }
  return undefined;
}

function stringProperty(value: unknown, key: string, description: string): string {
  if (!isRecord(value) || typeof value[key] !== "string") {
    throw new TypeError(`${description} is missing ${key}`);
  }
  return value[key];
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
  return (
    hostname === "localhost" ||
    hostname === "::1" ||
    (isIP(hostname) === 4 && hostname.split(".")[0] === "127")
  );
}

function rawDataByteLength(data: RawData): number {
  if (Array.isArray(data)) {
    return data.reduce((total, chunk) => total + chunk.byteLength, 0);
  }
  return data.byteLength;
}

function safeWebSocketCloseCode(code: number): number {
  const reserved = code === 1004 || code === 1005 || code === 1006;
  return !reserved && ((code >= 1000 && code <= 1014) || (code >= 3000 && code <= 4999))
    ? code
    : 1011;
}

function rejectUpgrade(socket: Duplex, status: number, reason: string): void {
  socket.write(`HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\n\r\n`);
  socket.destroy();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function httpError(status: number, message: string): Error & { status: number } {
  const error = new Error(message) as Error & { status: number };
  error.status = status;
  return error;
}
