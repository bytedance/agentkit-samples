import { randomBytes } from "node:crypto";
import { once } from "node:events";
import type { IncomingMessage, ServerResponse } from "node:http";
import { isIP } from "node:net";
import type { Duplex } from "node:stream";
import {
  WebSocket as ProxyWebSocket,
  WebSocketServer,
  type RawData,
} from "ws";
import { redactSensitiveText, sandboxServiceUrl } from "./protocol.ts";
import type { ExternalWorkspaceType } from "./runtime.ts";

interface WorkspaceBinding {
  sandboxUrl: string;
  toolType: ExternalWorkspaceType;
  touchedAt: number;
}

interface ProxyConnection {
  browser: ProxyWebSocket;
  upstream: ProxyWebSocket;
}

const WORKSPACE_DESCRIPTORS: Record<ExternalWorkspaceType, {
  cookie: string;
  path: string;
}> = {
  Hermes: { cookie: "situla_hermes_workspace", path: "/hermes" },
  OpenClaw: { cookie: "situla_openclaw_workspace", path: "/openclaw" },
};
const BINDING_TTL_MS = 24 * 60 * 60_000;
const MAX_BINDINGS = 64;
const MAX_PENDING_WEBSOCKET_BYTES = 1024 * 1024;
const COMMON_HEADERS = {
  "cross-origin-resource-policy": "same-origin",
  "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff",
};

export class SandboxWorkspaceProxy {
  readonly #bindings = new Map<string, WorkspaceBinding>();
  readonly #connections = new Set<ProxyConnection>();
  readonly #webSocketServer = new WebSocketServer({ noServer: true });

  createLaunch(toolType: ExternalWorkspaceType, sandboxUrl: string): {
    url: string;
    setCookie: string;
  } {
    const descriptor = WORKSPACE_DESCRIPTORS[toolType];
    sandboxServiceUrl(sandboxUrl, descriptor.path);
    this.#pruneBindings();
    const token = randomBytes(32).toString("base64url");
    this.#bindings.set(token, { sandboxUrl, toolType, touchedAt: Date.now() });
    return {
      url: descriptor.path,
      setCookie: `${descriptor.cookie}=${token}; Path=${descriptor.path}; HttpOnly; SameSite=Strict`,
    };
  }

  handleHttp(
    request: IncomingMessage,
    response: ServerResponse,
    url: URL,
  ): Promise<boolean> {
    const toolType = workspaceTypeFromPath(url.pathname);
    if (!toolType) return Promise.resolve(false);
    return this.#handleHttp(request, response, url, toolType)
      .then(() => true)
      .catch((error: unknown) => {
        if (!response.headersSent) sendJson(response, 500, { error: errorText(error) });
        else response.end();
        return true;
      });
  }

  handleUpgrade(request: IncomingMessage, socket: Duplex, head: Buffer): boolean {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    const toolType = workspaceTypeFromPath(url.pathname);
    if (!toolType) return false;
    this.#handleUpgrade(request, socket, head, url, toolType);
    return true;
  }

  close(): void {
    for (const connection of this.#connections) {
      connection.browser.close();
      connection.upstream.close();
    }
    this.#connections.clear();
    this.#bindings.clear();
    this.#webSocketServer.close();
  }

  async #handleHttp(
    request: IncomingMessage,
    response: ServerResponse,
    url: URL,
    toolType: ExternalWorkspaceType,
  ): Promise<void> {
    if (!isTrustedBrowserRequest(request)) {
      sendJson(response, 403, { error: "untrusted Host or Origin" });
      return;
    }
    const binding = this.#bindingForRequest(request, toolType);
    if (!binding) {
      sendJson(response, 401, { error: `${toolType} workspace is not launched` });
      return;
    }
    const upstreamUrl = workspaceUpstreamUrl(binding.sandboxUrl, url, false);
    const method = request.method ?? "GET";
    const init: RequestInit & { duplex?: "half" } = {
      method,
      headers: workspaceForwardHeaders(request, upstreamUrl),
      redirect: "manual",
      signal: AbortSignal.timeout(300_000),
    };
    if (method !== "GET" && method !== "HEAD") {
      init.body = request as unknown as BodyInit;
      init.duplex = "half";
    }
    let upstream: Response;
    try {
      upstream = await fetch(upstreamUrl, init);
    } catch (error) {
      sendJson(response, 502, { error: safeWorkspaceError(error, binding.sandboxUrl) });
      return;
    }

    const headers: Record<string, string | string[]> = { ...COMMON_HEADERS };
    for (const name of [
      "accept-ranges",
      "cache-control",
      "content-disposition",
      "content-language",
      "content-range",
      "content-security-policy",
      "content-type",
      "etag",
      "last-modified",
    ]) {
      const value = upstream.headers.get(name);
      if (value) headers[name] = value;
    }
    const location = upstream.headers.get("location");
    if (location) {
      headers.location = localWorkspaceLocation(location, upstreamUrl, binding.sandboxUrl);
    }
    const setCookies = upstreamSetCookies(upstream.headers)
      .map((value) => localWorkspaceCookie(value, WORKSPACE_DESCRIPTORS[toolType].path));
    if (setCookies.length) headers["set-cookie"] = setCookies;
    response.writeHead(upstream.status, headers);
    if (method === "HEAD" || !upstream.body) {
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
      if (!response.destroyed) {
        response.destroy(new Error(safeWorkspaceError(error, binding.sandboxUrl)));
      }
    }
  }

  #handleUpgrade(
    request: IncomingMessage,
    socket: Duplex,
    head: Buffer,
    url: URL,
    toolType: ExternalWorkspaceType,
  ): void {
    if (!isTrustedBrowserRequest(request)) {
      rejectUpgrade(socket, 403, "Forbidden");
      return;
    }
    const binding = this.#bindingForRequest(request, toolType);
    if (!binding) {
      rejectUpgrade(socket, 401, "Unauthorized");
      return;
    }
    this.#webSocketServer.handleUpgrade(request, socket, head, (browser) => {
      let upstream: ProxyWebSocket;
      try {
        const upstreamUrl = workspaceUpstreamUrl(binding.sandboxUrl, url, true);
        const protocols = websocketProtocols(request.headers["sec-websocket-protocol"]);
        const options = { headers: workspaceWebSocketHeaders(request, upstreamUrl) };
        upstream = protocols.length
          ? new ProxyWebSocket(upstreamUrl, protocols, options)
          : new ProxyWebSocket(upstreamUrl, options);
      } catch (error) {
        browser.close(1011, safeWorkspaceError(error, binding.sandboxUrl).slice(0, 120));
        return;
      }
      const connection = { browser, upstream };
      this.#connections.add(connection);
      const pending: Array<{ data: RawData; isBinary: boolean }> = [];
      let pendingBytes = 0;
      let cleanedUp = false;
      const cleanup = () => {
        if (cleanedUp) return;
        cleanedUp = true;
        this.#connections.delete(connection);
      };
      browser.on("message", (data, isBinary) => {
        if (upstream.readyState === ProxyWebSocket.OPEN) {
          upstream.send(data, { binary: isBinary });
        } else if (upstream.readyState === ProxyWebSocket.CONNECTING) {
          pendingBytes += rawDataByteLength(data);
          if (pendingBytes > MAX_PENDING_WEBSOCKET_BYTES) {
            browser.close(1009, "too much pending workspace data");
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
      });
      upstream.on("message", (data, isBinary) => {
        if (browser.readyState === ProxyWebSocket.OPEN) {
          browser.send(data, { binary: isBinary });
        }
      });
      upstream.on("error", (error) => {
        if (browser.readyState === ProxyWebSocket.OPEN) {
          browser.close(1011, safeWorkspaceError(error, binding.sandboxUrl).slice(0, 120));
        }
        cleanup();
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
      browser.on("error", () => {
        upstream.close();
        cleanup();
      });
    });
  }

  #bindingForRequest(
    request: IncomingMessage,
    toolType: ExternalWorkspaceType,
  ): WorkspaceBinding | undefined {
    const descriptor = WORKSPACE_DESCRIPTORS[toolType];
    const token = requestCookie(request, descriptor.cookie);
    if (!token) return undefined;
    const binding = this.#bindings.get(token);
    if (!binding || binding.toolType !== toolType) return undefined;
    if (Date.now() - binding.touchedAt > BINDING_TTL_MS) {
      this.#bindings.delete(token);
      return undefined;
    }
    binding.touchedAt = Date.now();
    return binding;
  }

  #pruneBindings(): void {
    const now = Date.now();
    for (const [token, binding] of this.#bindings) {
      if (now - binding.touchedAt > BINDING_TTL_MS) this.#bindings.delete(token);
    }
    if (this.#bindings.size < MAX_BINDINGS) return;
    const oldest = [...this.#bindings.entries()]
      .sort((left, right) => left[1].touchedAt - right[1].touchedAt);
    for (const [token] of oldest.slice(0, this.#bindings.size - MAX_BINDINGS + 1)) {
      this.#bindings.delete(token);
    }
  }
}

function workspaceTypeFromPath(pathname: string): ExternalWorkspaceType | undefined {
  for (const toolType of ["Hermes", "OpenClaw"] as const) {
    const path = WORKSPACE_DESCRIPTORS[toolType].path;
    if (pathname === path || pathname.startsWith(`${path}/`)) return toolType;
  }
  return undefined;
}

function workspaceUpstreamUrl(sandboxUrl: string, localUrl: URL, websocket: boolean): URL {
  const upstream = new URL(sandboxServiceUrl(sandboxUrl, localUrl.pathname, websocket));
  for (const [name, value] of localUrl.searchParams) upstream.searchParams.append(name, value);
  return upstream;
}

function workspaceForwardHeaders(
  request: IncomingMessage,
  upstreamUrl: URL,
): Headers {
  const headers = new Headers();
  for (const name of [
    "accept",
    "accept-language",
    "authorization",
    "content-type",
    "if-modified-since",
    "if-none-match",
    "range",
    "user-agent",
    "x-hermes-session-token",
  ] as const) {
    const value = request.headers[name];
    if (typeof value === "string") headers.set(name, value);
  }
  const cookie = upstreamCookie(request);
  if (cookie) headers.set("cookie", cookie);
  if (request.headers.origin) headers.set("origin", upstreamUrl.origin);
  if (request.headers.referer) headers.set("referer", `${upstreamUrl.origin}${upstreamUrl.pathname}`);
  headers.set("x-forwarded-host", request.headers.host ?? "localhost");
  headers.set("x-forwarded-proto", "http");
  return headers;
}

function workspaceWebSocketHeaders(
  request: IncomingMessage,
  upstreamUrl: URL,
): Record<string, string> {
  const upstreamOrigin = new URL(upstreamUrl);
  upstreamOrigin.protocol = upstreamOrigin.protocol === "wss:" ? "https:" : "http:";
  const headers: Record<string, string> = { origin: upstreamOrigin.origin };
  const cookie = upstreamCookie(request);
  if (cookie) headers.cookie = cookie;
  if (typeof request.headers["user-agent"] === "string") {
    headers["user-agent"] = request.headers["user-agent"];
  }
  return headers;
}

function requestCookie(request: IncomingMessage, name: string): string | undefined {
  return request.headers.cookie
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function upstreamCookie(request: IncomingMessage): string | undefined {
  const cookies = request.headers.cookie
    ?.split(";")
    .map((part) => part.trim())
    .filter((part) => part && !part.startsWith("situla_"));
  return cookies?.length ? cookies.join("; ") : undefined;
}

function upstreamSetCookies(headers: Headers): string[] {
  const extended = headers as Headers & { getSetCookie?: () => string[] };
  if (extended.getSetCookie) return extended.getSetCookie();
  const value = headers.get("set-cookie");
  return value ? [value] : [];
}

function localWorkspaceCookie(value: string, path: string): string {
  const withoutDomain = value.replace(/;\s*Domain=[^;]*/gi, "");
  const withoutSecure = withoutDomain.replace(/;\s*Secure/gi, "");
  return /;\s*Path=/i.test(withoutSecure)
    ? withoutSecure.replace(/;\s*Path=[^;]*/i, `; Path=${path}`)
    : `${withoutSecure}; Path=${path}`;
}

function localWorkspaceLocation(location: string, upstreamUrl: URL, sandboxUrl: string): string {
  const target = new URL(location, upstreamUrl);
  if (target.origin !== upstreamUrl.origin) return location;
  const sensitiveNames = new Set([...new URL(sandboxUrl).searchParams.keys()]);
  for (const name of sensitiveNames) target.searchParams.delete(name);
  return `${target.pathname}${target.search}${target.hash}`;
}

function websocketProtocols(value: string | string[] | undefined): string[] {
  const text = Array.isArray(value) ? value.join(",") : value;
  return text?.split(",").map((protocol) => protocol.trim()).filter(Boolean) ?? [];
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
  return hostname === "localhost" || hostname === "::1" ||
    (isIP(hostname) === 4 && hostname.split(".")[0] === "127");
}

function rawDataByteLength(data: RawData): number {
  if (Array.isArray(data)) return data.reduce((total, chunk) => total + chunk.byteLength, 0);
  return data.byteLength;
}

function safeWebSocketCloseCode(code: number): number {
  const reserved = code === 1004 || code === 1005 || code === 1006;
  return !reserved && ((code >= 1000 && code <= 1014) || (code >= 3000 && code <= 4999))
    ? code
    : 1011;
}

function safeWorkspaceError(error: unknown, sandboxUrl: string): string {
  return redactSensitiveText(errorText(error), [sandboxUrl]);
}

function rejectUpgrade(socket: Duplex, status: number, reason: string): void {
  socket.write(`HTTP/1.1 ${status} ${reason}\r\nConnection: close\r\n\r\n`);
  socket.destroy();
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    ...COMMON_HEADERS,
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(value));
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
