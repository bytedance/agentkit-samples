#!/usr/bin/env -S node --disable-warning=ExperimentalWarning --experimental-strip-types

import { randomBytes, timingSafeEqual } from "node:crypto";
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { isIP } from "node:net";
import { dirname, extname, resolve, sep } from "node:path";
import {
  AgentkitToolsClient,
  AgentkitApiError,
  type AgentkitSessionSnapshotSummary,
  type AgentkitSessionSummary,
  type AgentkitToolSearchField,
  type AgentkitToolSummary,
} from "./agentkit.ts";
import { ConsoleLoginManager } from "./console-login.ts";
import { loadSitulaConfiguration } from "./config.ts";
import {
  BridgeSession,
  SkillSelectionError,
  type BridgeEvent,
} from "./bridge.ts";
import type { SessionPermissionSettings } from "./app-server-data.ts";
import { SandboxBrowserProxy } from "./browser-proxy.ts";
import {
  CodexAppServerError,
  type ApprovalDecision,
} from "./client.ts";
import { errorText } from "./protocol.ts";
import {
  parsePrivateRuntimeType,
  runtimeWorkspaceForToolType,
} from "./runtime.ts";
import { SandboxTerminalProxy } from "./terminal-proxy.ts";
import { embeddedWebAssets } from "./web-assets.ts";
import { SandboxWorkspaceProxy } from "./workspace-proxy.ts";

const webRoot = resolve(dirname(process.argv[1] ?? "."), "../dist/web");
const sessions = new Map<string, BridgeSession>();
const bridgeAgentkitSessions = new Map<string, AgentkitSessionSummary>();
const eventStreams = new Set<ServerResponse>();
const sessionStreamCounts = new Map<string, number>();
const orphanTimers = new Map<string, ReturnType<typeof setTimeout>>();
const MAX_BODY_BYTES = 64 * 1024;
const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
const runtimeSettings = loadSitulaConfiguration().values;
const privateRuntimeType = parsePrivateRuntimeType(process.env.SITULA_PRIVATE_TYPE);
const SESSION_ORPHAN_GRACE_MS = Number(runtimeSettings.SITULA_ORPHAN_GRACE_MS);
const CAPABILITY_COOKIE = "situla_capability";
const capabilityToken = randomBytes(32).toString("base64url");
const COMMON_HEADERS = {
  "cross-origin-resource-policy": "same-origin",
  "referrer-policy": "no-referrer",
  "x-content-type-options": "nosniff",
  "x-frame-options": "DENY",
};
const consoleLogin = new ConsoleLoginManager();

interface JsonBody {
  [key: string]: unknown;
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    ...COMMON_HEADERS,
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(value));
}

async function readJson(request: IncomingMessage): Promise<JsonBody> {
  if (!request.headers["content-type"]?.toLowerCase().startsWith("application/json")) {
    throw httpError(415, "content-type must be application/json");
  }
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > MAX_BODY_BYTES) throw httpError(413, "request body is too large");
    chunks.push(buffer);
  }
  if (chunks.length === 0) return {};
  let value: unknown;
  try {
    value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw httpError(400, "request body must be valid JSON");
  }
  if (!isRecord(value)) throw httpError(400, "request body must be a JSON object");
  return value;
}

async function readBody(request: IncomingMessage, limit: number): Promise<Buffer> {
  const declaredSize = Number(request.headers["content-length"] ?? 0);
  if (Number.isFinite(declaredSize) && declaredSize > limit) {
    throw httpError(413, "request body is too large");
  }
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > limit) throw httpError(413, "request body is too large");
    chunks.push(buffer);
  }
  return Buffer.concat(chunks);
}

function sessionOr404(id: string, response: ServerResponse): BridgeSession | undefined {
  const session = sessions.get(id);
  if (!session) sendJson(response, 404, { error: "session not found" });
  return session;
}

function sessionTag(sessionId: string): string {
  return sessionId.slice(0, 8);
}

function snapshotBody(snapshot: Awaited<ReturnType<BridgeSession["newThread"]>>) {
  return {
    threadId: snapshot.thread.id,
    thread: snapshot.thread,
    messages: snapshot.messages,
    ...(snapshot.model ? { model: snapshot.model } : {}),
    ...(snapshot.cwd ? { cwd: snapshot.cwd } : {}),
    ...threadRuntimeSettings(snapshot),
  };
}

async function handleApi(
  request: IncomingMessage,
  response: ServerResponse,
  url: URL,
): Promise<boolean> {
  if (!url.pathname.startsWith("/api/")) return false;

  if (request.method === "GET" && url.pathname === "/api/health") {
    sendJson(response, 200, { ok: true });
    return true;
  }

  if (request.method === "GET" && url.pathname === "/api/capability") {
    if (!isTrustedBrowserRequest(request)) {
      sendJson(response, 403, { error: "untrusted Host or Origin" });
      return true;
    }
    response.setHeader(
      "set-cookie",
      `${CAPABILITY_COOKIE}=${capabilityToken}; Path=/api; HttpOnly; SameSite=Strict`,
    );
    sendJson(response, 200, { ok: true });
    return true;
  }

  if (!isTrustedBrowserRequest(request)) {
    sendJson(response, 403, { error: "untrusted Host or Origin" });
    return true;
  }
  if (!hasCapability(request)) {
    sendJson(response, 401, { error: "missing or invalid bridge capability" });
    return true;
  }

  if (request.method === "POST" && url.pathname === "/api/auth/start") {
    const body = await readJson(request);
    const region = typeof body.region === "string" ? body.region : undefined;
    sendJson(response, 200, consoleLogin.start(region));
    return true;
  }

  const remoteLoginMatch = url.pathname.match(/^\/api\/auth\/([^/]+)\/remote$/);
  if (request.method === "POST" && remoteLoginMatch) {
    const body = await readJson(request);
    if (typeof body.authorizationResponse !== "string") {
      throw httpError(400, "authorizationResponse is required");
    }
    await consoleLogin.completeRemote(decodeURIComponent(remoteLoginMatch[1]), body.authorizationResponse);
    sendJson(response, 200, { ok: true });
    return true;
  }

  if (request.method === "POST" && url.pathname === "/api/auth/logout") {
    const loggedOut = consoleLogin.logout();
    sendJson(response, 200, { ok: true, loggedOut });
    return true;
  }

  if (request.method === "GET" && url.pathname === "/api/agentkit/config") {
    const client = await optionalAgentkit();
    const consoleLoginActive = consoleLogin.active;
    const recentToolsScope = client
      ? consoleLogin.recentToolsScope(client.region, client.service, client.host)
      : undefined;
    sendJson(response, 200, client
      ? {
          configured: true,
          region: client.region,
          consoleLogin: consoleLoginActive,
          ...(privateRuntimeType ? { privateType: privateRuntimeType } : {}),
          ...(recentToolsScope ? { recentToolsScope } : {}),
        }
      : {
          configured: false,
          consoleLogin: consoleLoginActive,
          ...(privateRuntimeType ? { privateType: privateRuntimeType } : {}),
        });
    return true;
  }

  if (request.method === "GET" && url.pathname === "/api/agentkit/tools") {
    const client = await requireAgentkit();
    const maxResults = queryInteger(url, "maxResults", 10, 1, 100);
    const search = url.searchParams.get("search")?.trim();
    if (search && search.length > 256) throw httpError(400, "search must not exceed 256 characters");
    if (search) {
      const offset = decodeToolSearchCursor(url.searchParams.get("nextToken"), search);
      const tools = await searchAgentkitTools(client, search);
      const data = tools.slice(offset, offset + maxResults);
      const nextOffset = offset + data.length;
      sendJson(response, 200, {
        data: data.map(publicAgentkitTool),
        ...(nextOffset < tools.length
          ? { nextToken: encodeToolSearchCursor(search, nextOffset) }
          : {}),
      });
      return true;
    }
    const page = await client.listTools({
      maxResults,
      ...(url.searchParams.get("nextToken")
        ? { nextToken: url.searchParams.get("nextToken")! }
        : {}),
    });
    sendJson(response, 200, {
      data: page.data.map(publicAgentkitTool),
      ...(page.nextToken ? { nextToken: page.nextToken } : {}),
    });
    return true;
  }

  const agentkitToolMatch = url.pathname.match(/^\/api\/agentkit\/tools\/([^/]+)$/);
  if (request.method === "GET" && agentkitToolMatch) {
    const tool = await (await requireAgentkit()).getTool(
      decodeURIComponent(agentkitToolMatch[1]),
    );
    sendJson(response, 200, publicAgentkitTool(tool));
    return true;
  }

  const agentkitSessionsMatch = url.pathname.match(
    /^\/api\/agentkit\/tools\/([^/]+)\/sessions$/,
  );
  if (request.method === "GET" && agentkitSessionsMatch) {
    const toolId = decodeURIComponent(agentkitSessionsMatch[1]);
    const data = await (await requireAgentkit()).listAllSessions(toolId);
    sendJson(response, 200, { data: data.map(publicAgentkitSession) });
    return true;
  }

  if (request.method === "POST" && agentkitSessionsMatch) {
    const body = await readJson(request);
    const client = await requireAgentkit();
    const toolId = decodeURIComponent(agentkitSessionsMatch[1]);
    const created = await client.createSession(toolId, {
      ...(typeof body.userSessionId === "string" && body.userSessionId.trim()
        ? { userSessionId: body.userSessionId.trim() }
        : {}),
      ...(typeof body.ttl === "number" ? { ttl: body.ttl } : {}),
    });
    const ready = await waitForAgentkitSession(client, toolId, created);
    sendJson(response, 201, publicAgentkitSession(ready));
    return true;
  }

  const agentkitSnapshotsMatch = url.pathname.match(
    /^\/api\/agentkit\/tools\/([^/]+)\/snapshots$/,
  );
  if (request.method === "GET" && agentkitSnapshotsMatch) {
    const toolId = decodeURIComponent(agentkitSnapshotsMatch[1]);
    const data = await (await requireAgentkit()).listAllSessionSnapshots(toolId);
    sendJson(response, 200, { data: data.map(publicAgentkitSessionSnapshot) });
    return true;
  }

  const agentkitSnapshotResumeMatch = url.pathname.match(
    /^\/api\/agentkit\/tools\/([^/]+)\/snapshots\/([^/]+)\/resume$/,
  );
  if (request.method === "POST" && agentkitSnapshotResumeMatch) {
    const body = await readJson(request);
    const client = await requireAgentkit();
    const toolId = decodeURIComponent(agentkitSnapshotResumeMatch[1]);
    const snapshotId = decodeURIComponent(agentkitSnapshotResumeMatch[2]);
    const userSessionId = typeof body.userSessionId === "string"
      ? body.userSessionId.trim()
      : "";
    const current = userSessionId
      ? await client.findSessionByUserSessionId(toolId, userSessionId)
      : undefined;
    const resumed = current ?? await client.resumeSessionFromSnapshot(
      toolId,
      snapshotId,
      typeof body.ttl === "number" ? body.ttl : undefined,
    );
    const ready = await waitForAgentkitSession(client, toolId, resumed);
    sendJson(response, 201, publicAgentkitSession(ready));
    return true;
  }

  const agentkitSessionMatch = url.pathname.match(
    /^\/api\/agentkit\/tools\/([^/]+)\/sessions\/([^/]+)$/,
  );
  if (request.method === "GET" && agentkitSessionMatch) {
    const item = await (await requireAgentkit()).getSession(
      decodeURIComponent(agentkitSessionMatch[1]),
      decodeURIComponent(agentkitSessionMatch[2]),
    );
    sendJson(response, 200, publicAgentkitSession(item));
    return true;
  }

  const agentkitWorkspaceMatch = url.pathname.match(
    /^\/api\/agentkit\/tools\/([^/]+)\/sessions\/([^/]+)\/workspace$/,
  );
  if (request.method === "POST" && agentkitWorkspaceMatch) {
    const session = await (await requireAgentkit()).getSession(
      decodeURIComponent(agentkitWorkspaceMatch[1]),
      decodeURIComponent(agentkitWorkspaceMatch[2]),
    );
    if (session.status.toLowerCase() !== "ready" || !session.endpoint) {
      sendJson(response, 409, {
        error: `AgentKit Session is not ready (status: ${session.status})`,
      });
      return true;
    }
    const workspace = runtimeWorkspaceForToolType(session.toolType, privateRuntimeType);
    if (workspace === "Codex") {
      sendJson(response, 409, { error: "CodeEnv sessions use the built-in /codex workspace" });
      return true;
    }
    if (!workspace) {
      sendJson(response, 409, {
        error: `AgentKit Tool type ${session.toolType ?? "Unknown"} has no Runtime Workspace`,
      });
      return true;
    }
    const launch = workspaceProxy.createLaunch(workspace, session.endpoint);
    response.setHeader("set-cookie", launch.setCookie);
    sendJson(response, 201, { url: launch.url });
    return true;
  }

  if (request.method === "POST" && url.pathname === "/api/sessions") {
    const body = await readJson(request);
    let sandboxUrl: string;
    let agentkitSession: AgentkitSessionSummary | undefined;
    if (typeof body.agentkitSessionId === "string" && body.agentkitSessionId.trim()) {
      if (typeof body.agentkitToolId !== "string" || !body.agentkitToolId.trim()) {
        sendJson(response, 400, { error: "agentkitToolId is required with agentkitSessionId" });
        return true;
      }
      agentkitSession = await (await requireAgentkit()).getSession(
        body.agentkitToolId.trim(),
        body.agentkitSessionId.trim(),
      );
      if (agentkitSession.status.toLowerCase() !== "ready" || !agentkitSession.endpoint) {
        sendJson(response, 409, {
          error: `AgentKit Session is not ready (status: ${agentkitSession.status})`,
        });
        return true;
      }
      const workspace = runtimeWorkspaceForToolType(
        agentkitSession.toolType,
        privateRuntimeType,
      );
      if (workspace !== "Codex") {
        sendJson(response, 409, {
          error: workspace
            ? `${agentkitSession.toolType ?? "AgentKit"} sessions use the /${workspace.toLowerCase()} workspace`
            : `AgentKit Tool type ${agentkitSession.toolType ?? "Unknown"} has no Runtime Workspace`,
        });
        return true;
      }
      sandboxUrl = agentkitSession.endpoint;
    } else if (typeof body.sandboxUrl === "string" && body.sandboxUrl.trim()) {
      sandboxUrl = body.sandboxUrl;
    } else {
      sendJson(response, 400, { error: "agentkitSessionId or sandboxUrl is required" });
      return true;
    }
    const session = new BridgeSession({
      sandboxUrl,
      ...(typeof body.cwd === "string" && body.cwd ? { cwd: body.cwd } : {}),
      ...(typeof body.model === "string" && body.model ? { model: body.model } : {}),
      ...(typeof body.threadId === "string" && body.threadId
        ? { resumeThreadId: body.threadId }
        : {}),
    });
    sessions.set(session.id, session);
    if (agentkitSession) bridgeAgentkitSessions.set(session.id, agentkitSession);
    response.once("close", () => {
      if (response.writableEnded) return;
      sessions.delete(session.id);
      bridgeAgentkitSessions.delete(session.id);
      session.close();
    });
    console.info(`[session ${sessionTag(session.id)}] connecting to ${session.displayUrl}`);
    session.subscribe((event) => {
      if (event.type === "turn_completed") {
        console.info(
          `[session ${sessionTag(session.id)}] turn ${event.turnId} completed (${event.status})`,
        );
      } else if (event.type === "turn_error") {
        console.error(
          `[session ${sessionTag(session.id)}] turn failed: ${event.message}`,
        );
      } else if (event.type === "approval_requested") {
        console.info(
          `[session ${sessionTag(session.id)}] waiting for ${event.approval.kind} approval`,
        );
      } else if (event.type === "closed") {
        sessions.delete(session.id);
        bridgeAgentkitSessions.delete(session.id);
        terminalProxy.closeSession(session.id);
        browserProxy.closeSession(session.id);
        cancelOrphanCleanup(session.id);
        sessionStreamCounts.delete(session.id);
        if (event.reason) {
          console.info(`[session ${sessionTag(session.id)}] remote connection closed`);
        }
      }
    });
    try {
      const threadId = await session.connect();
      console.info(
        `[session ${sessionTag(session.id)}] connected, thread ${threadId}`,
      );
      scheduleOrphanCleanup(session);
      sendJson(response, 201, {
        id: session.id,
        threadId,
        endpoint: session.displayUrl,
        messages: session.messages,
        ...(session.model ? { model: session.model } : {}),
        ...(session.cwd ? { cwd: session.cwd } : {}),
        ...sessionRuntimeSettings(session),
        ...(agentkitSession
          ? { agentkitSession: publicAgentkitSession(agentkitSession) }
          : {}),
      });
    } catch (error) {
      sessions.delete(session.id);
      bridgeAgentkitSessions.delete(session.id);
      const message = session.safeError(error);
      console.error(`[session ${sessionTag(session.id)}] connection failed: ${message}`);
      session.close();
      sendJson(response, 502, { error: message });
    }
    return true;
  }

  const match = url.pathname.match(/^\/api\/sessions\/([^/]+)(?:\/(.*))?$/);
  if (!match) {
    sendJson(response, 404, { error: "API route not found" });
    return true;
  }
  const sessionId = decodeURIComponent(match[1]);
  const action = match[2] ?? "";
  const session = sessionOr404(sessionId, response);
  if (!session) return true;

  if (request.method === "GET" && action === "browser") {
    sendJson(response, 200, { url: browserProxy.browserUrl(request.headers.host, sessionId) });
    return true;
  }

  if (request.method === "POST" && action === "browser/navigate") {
    const targetUrl = browserPreviewUrlFromBody(await readJson(request));
    try {
      await browserProxy.navigate(sessionId, targetUrl);
    } catch (error) {
      throw httpError(502, session.safeError(error));
    }
    sendJson(response, 200, { ok: true, url: targetUrl });
    return true;
  }

  if (request.method === "GET" && action === "terminal") {
    const shellSessionId = url.searchParams.get("shellSessionId") ?? undefined;
    sendJson(
      response,
      200,
      await terminalProxy.terminalUrl(request.headers.host, sessionId, shellSessionId),
    );
    return true;
  }

  if (request.method === "GET" && action === "directories") {
    const path = url.searchParams.get("path")?.trim();
    if (!path) {
      sendJson(response, 400, { error: "path is required" });
      return true;
    }
    if (path.length > 4_096) {
      sendJson(response, 400, { error: "path is too long" });
      return true;
    }
    sendJson(response, 200, await session.listDirectories(path));
    return true;
  }

  if (request.method === "GET" && action === "events") {
    response.writeHead(200, {
      ...COMMON_HEADERS,
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    });
    response.write(": connected\n\n");
    eventStreams.add(response);
    cancelOrphanCleanup(sessionId);
    sessionStreamCounts.set(sessionId, (sessionStreamCounts.get(sessionId) ?? 0) + 1);
    console.info(`[session ${sessionTag(sessionId)}] browser event stream attached`);
    const lastEventId = parseLastEventId(request.headers["last-event-id"]);
    const unsubscribe = session.subscribe(
      (event, eventId) => {
        writeSse(response, eventId, event);
        if (event.type === "closed") response.end();
      },
      lastEventId,
    );
    const heartbeat = setInterval(() => response.write(": heartbeat\n\n"), 15_000);
    let cleanedUp = false;
    const cleanup = () => {
      if (cleanedUp) return;
      cleanedUp = true;
      clearInterval(heartbeat);
      unsubscribe();
      eventStreams.delete(response);
      const remainingStreams = Math.max((sessionStreamCounts.get(sessionId) ?? 1) - 1, 0);
      if (remainingStreams === 0) {
        sessionStreamCounts.delete(sessionId);
        if (sessions.get(sessionId) === session) scheduleOrphanCleanup(session);
      } else {
        sessionStreamCounts.set(sessionId, remainingStreams);
      }
      console.info(`[session ${sessionTag(sessionId)}] browser event stream detached`);
    };
    request.once("close", cleanup);
    response.once("close", cleanup);
    return true;
  }

  if (request.method === "POST" && action === "turns") {
    const body = await readJson(request);
    if (typeof body.text !== "string" || !body.text.trim()) {
      sendJson(response, 400, { error: "text is required" });
      return true;
    }
    if (
      body.skillIds !== undefined &&
      (
        !Array.isArray(body.skillIds) ||
        body.skillIds.length > 20 ||
        body.skillIds.some((id) =>
          typeof id !== "string" ||
          !id ||
          id.length > 128 ||
          id.trim() !== id)
      )
    ) {
      sendJson(response, 400, { error: "skillIds must contain at most 20 Skill IDs" });
      return true;
    }
    if (session.active) {
      sendJson(response, 409, { error: "a turn is already running" });
      return true;
    }
    let requestId: string;
    try {
      requestId = await session.startTurn(
        body.text,
        body.skillIds === undefined ? [] : [...new Set(body.skillIds as string[])],
      );
    } catch (error) {
      if (!(error instanceof SkillSelectionError)) throw error;
      sendJson(response, 400, { error: error.message });
      return true;
    }
    console.info(
      `[session ${sessionTag(sessionId)}] turn accepted (${requestId.slice(0, 8)})`,
    );
    sendJson(response, 202, { requestId });
    return true;
  }

  if (request.method === "POST" && action === "interrupt") {
    if (!session.active) {
      sendJson(response, 409, { error: "there is no active turn" });
      return true;
    }
    try {
      await session.interrupt();
    } catch (error) {
      if (error instanceof CodexAppServerError) throw error;
      sendJson(response, 409, { error: errorText(error) });
      return true;
    }
    sendJson(response, 200, { ok: true });
    return true;
  }

  if (request.method === "POST" && action === "threads") {
    if (session.active) {
      sendJson(response, 409, { error: "cannot start a new thread while a turn is running" });
      return true;
    }
    const snapshot = await session.newThread();
    console.info(`[session ${sessionTag(sessionId)}] new thread ${snapshot.thread.id}`);
    sendJson(response, 201, snapshotBody(snapshot));
    return true;
  }

  if (request.method === "GET" && action === "threads") {
    const cursor = url.searchParams.get("cursor") || undefined;
    const searchTerm = url.searchParams.get("search")?.trim() || undefined;
    const page = await session.listThreads({ cursor, searchTerm, archived: false });
    sendJson(response, 200, page);
    return true;
  }

  if (request.method === "POST" && action === "threads/resume") {
    if (session.active) {
      sendJson(response, 409, { error: "cannot switch threads while a turn is running" });
      return true;
    }
    const body = await readJson(request);
    if (typeof body.threadId !== "string" || !body.threadId.trim()) {
      sendJson(response, 400, { error: "threadId is required" });
      return true;
    }
    const snapshot = await session.switchThread(body.threadId);
    console.info(`[session ${sessionTag(sessionId)}] resumed thread ${snapshot.thread.id}`);
    sendJson(response, 200, snapshotBody(snapshot));
    return true;
  }

  if (request.method === "POST" && action === "threads/fork") {
    const snapshot = await session.forkThread();
    console.info(`[session ${sessionTag(sessionId)}] forked thread ${snapshot.thread.id}`);
    sendJson(response, 201, snapshotBody(snapshot));
    return true;
  }

  if (request.method === "POST" && action === "threads/archive") {
    const body = await readJson(request);
    if (typeof body.threadId !== "string" || !body.threadId.trim()) {
      sendJson(response, 400, { error: "threadId is required" });
      return true;
    }
    const snapshot = await session.archiveThread(body.threadId);
    console.info(`[session ${sessionTag(sessionId)}] archived thread ${body.threadId}`);
    sendJson(response, 200, {
      archived: true,
      ...(snapshot ? snapshotBody(snapshot) : {}),
    });
    return true;
  }

  if (request.method === "POST" && action === "threads/compact") {
    await session.compactThread();
    sendJson(response, 202, { ok: true });
    return true;
  }

  if (request.method === "GET" && action === "models") {
    sendJson(response, 200, { data: await session.listModels() });
    return true;
  }

  if (request.method === "GET" && action === "skills") {
    sendJson(response, 200, { data: await session.listSkills() });
    return true;
  }

  if (request.method === "POST" && action === "models") {
    const body = await readJson(request);
    if (typeof body.model !== "string" || !body.model.trim()) {
      sendJson(response, 400, { error: "model is required" });
      return true;
    }
    await session.setModel(body.model);
    sendJson(response, 200, { model: body.model });
    return true;
  }

  if (request.method === "POST" && action === "permissions") {
    if (session.active) {
      sendJson(response, 409, {
        error: "cannot change permissions while a turn is running",
      });
      return true;
    }
    const settings = permissionSettingsFromBody(await readJson(request));
    const updated = await session.updateSessionPermissions(settings);
    sendJson(response, 200, updated);
    return true;
  }

  if (request.method === "POST" && action === "workspace") {
    if (session.workspaceLocked) {
      sendJson(response, 409, {
        error: "cannot change workspace after the thread has started",
      });
      return true;
    }
    const cwd = workspaceDirectoryFromBody(await readJson(request));
    const updated = await session.updateWorkspaceDirectory(cwd);
    sendJson(response, 200, updated);
    return true;
  }

  if (request.method === "GET" && action === "status") {
    sendJson(response, 200, {
      threadId: session.threadId,
      endpoint: session.displayUrl,
      ...(session.model ? { model: session.model } : {}),
      ...(session.cwd ? { cwd: session.cwd } : {}),
      ...sessionRuntimeSettings(session),
      active: session.active,
      ...(bridgeAgentkitSessions.get(sessionId)
        ? { agentkitSession: publicAgentkitSession(bridgeAgentkitSessions.get(sessionId)!) }
        : {}),
    });
    return true;
  }

  if (request.method === "POST" && action === "files/upload") {
    const contentType = request.headers["content-type"];
    if (!contentType?.toLowerCase().startsWith("multipart/form-data")) {
      throw httpError(415, "content-type must be multipart/form-data");
    }
    const body = await readBody(request, MAX_UPLOAD_BYTES);
    let upstream: Response;
    try {
      upstream = await fetch(session.sandboxServiceUrl("/v1/file/upload"), {
        method: "POST",
        headers: { "content-type": contentType },
        body: body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength) as ArrayBuffer,
        signal: AbortSignal.timeout(5 * 60_000),
      });
    } catch (uploadError) {
      throw httpError(502, session.safeError(uploadError));
    }
    let result: unknown;
    try {
      result = await upstream.json();
    } catch {
      throw httpError(502, `sandbox upload returned invalid JSON (${upstream.status})`);
    }
    if (!upstream.ok || (isRecord(result) && result.success === false)) {
      const detail = isRecord(result) && typeof result.error === "string"
        ? result.error
        : `sandbox upload failed (${upstream.status})`;
      throw httpError(502, session.safeError(detail));
    }
    sendJson(response, 200, { ok: true });
    return true;
  }

  const approvalMatch = action.match(/^approvals\/([^/]+)$/);
  if (request.method === "POST" && approvalMatch) {
    const body = await readJson(request);
    if (!isApprovalDecision(body.decision)) {
      sendJson(response, 400, { error: "invalid approval decision" });
      return true;
    }
    try {
      session.resolveApproval(decodeURIComponent(approvalMatch[1]), body.decision);
    } catch (error) {
      sendJson(response, 409, { error: errorText(error) });
      return true;
    }
    sendJson(response, 200, { ok: true });
    return true;
  }

  if (request.method === "DELETE" && action === "") {
    session.close();
    sessions.delete(sessionId);
    bridgeAgentkitSessions.delete(sessionId);
    console.info(`[session ${sessionTag(sessionId)}] closed`);
    response.writeHead(204);
    response.end();
    return true;
  }

  sendJson(response, 404, { error: "API route not found" });
  return true;
}

function permissionSettingsFromBody(body: JsonBody): SessionPermissionSettings {
  if (
    body.approvalPolicy !== "untrusted" &&
    body.approvalPolicy !== "on-request" &&
    body.approvalPolicy !== "never"
  ) {
    throw httpError(400, "invalid approvalPolicy");
  }
  if (body.approvalsReviewer !== "user" && body.approvalsReviewer !== "auto_review") {
    throw httpError(400, "invalid approvalsReviewer");
  }
  if (
    body.sandboxMode !== "read-only" &&
    body.sandboxMode !== "workspace-write" &&
    body.sandboxMode !== "danger-full-access"
  ) {
    throw httpError(400, "invalid sandboxMode");
  }
  if (typeof body.networkAccess !== "boolean") {
    throw httpError(400, "networkAccess must be a boolean");
  }
  return {
    approvalPolicy: body.approvalPolicy,
    approvalsReviewer: body.approvalsReviewer,
    sandboxMode: body.sandboxMode,
    networkAccess: body.sandboxMode === "danger-full-access"
      ? true
      : body.networkAccess,
  };
}

function workspaceDirectoryFromBody(body: JsonBody): string {
  if (
    typeof body.cwd !== "string" ||
    !body.cwd.startsWith("/") ||
    body.cwd.includes("\0") ||
    body.cwd.length > 4_096
  ) {
    throw httpError(400, "cwd must be an absolute path");
  }
  return body.cwd;
}

function browserPreviewUrlFromBody(body: JsonBody): string {
  if (typeof body.url !== "string" || body.url.length > 2_048) {
    throw httpError(400, "browser preview URL is required and must not exceed 2048 characters");
  }
  let url: URL;
  try {
    url = new URL(body.url.trim());
  } catch {
    throw httpError(400, "browser preview URL is invalid");
  }
  if (!["http:", "https:"].includes(url.protocol)) {
    throw httpError(400, "browser preview URL must use http or https");
  }
  if (url.username || url.password) {
    throw httpError(400, "browser preview URL must not include credentials");
  }
  const hostname = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (hostname === "0.0.0.0") {
    url.hostname = "127.0.0.1";
  } else if (!isLoopbackHostname(hostname)) {
    throw httpError(400, "browser preview URL must target the sandbox loopback interface");
  }
  return url.toString();
}

function sessionRuntimeSettings(session: BridgeSession) {
  return {
    ...(session.approvalPolicy ? { approvalPolicy: session.approvalPolicy } : {}),
    ...(session.approvalsReviewer
      ? { approvalsReviewer: session.approvalsReviewer }
      : {}),
    ...(session.sandboxMode ? { sandboxMode: session.sandboxMode } : {}),
    ...(session.networkAccess !== undefined
      ? { networkAccess: session.networkAccess }
      : {}),
  };
}

function threadRuntimeSettings(
  snapshot: Awaited<ReturnType<BridgeSession["newThread"]>>,
) {
  return {
    ...(snapshot.approvalPolicy ? { approvalPolicy: snapshot.approvalPolicy } : {}),
    ...(snapshot.approvalsReviewer
      ? { approvalsReviewer: snapshot.approvalsReviewer }
      : {}),
    ...(snapshot.sandboxMode ? { sandboxMode: snapshot.sandboxMode } : {}),
    ...(snapshot.networkAccess !== undefined
      ? { networkAccess: snapshot.networkAccess }
      : {}),
  };
}

async function optionalAgentkit(): Promise<AgentkitToolsClient | undefined> {
  const credentials = await consoleLogin.credentials();
  if (credentials) {
    const settings = loadSitulaConfiguration().values;
    return new AgentkitToolsClient({
      accessKey: credentials.accessKey,
      secretKey: credentials.secretKey,
      sessionToken: credentials.sessionToken,
      region: settings.VOLCENGINE_REGION,
      service: settings.VOLCENGINE_SERVICE,
      host: settings.VOLCENGINE_HOST,
      timeoutMs: Number(settings.AGENTKIT_HTTP_TIMEOUT) * 1000,
      retries: Number(settings.AGENTKIT_HTTP_RETRIES),
    });
  }
  return undefined;
}

async function requireAgentkit(): Promise<AgentkitToolsClient> {
  const client = await optionalAgentkit();
  if (!client) {
    throw httpError(
      503,
      "AgentKit is not authorized; sign in with Console Login",
    );
  }
  return client;
}

async function waitForAgentkitSession(
  client: AgentkitToolsClient,
  toolId: string,
  created: AgentkitSessionSummary,
): Promise<AgentkitSessionSummary> {
  let latest = created;
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      latest = await client.getSession(toolId, created.sessionId);
      if (latest.status.toLowerCase() === "ready" && latest.endpoint) return latest;
      if (["failed", "error", "deleted", "expired"].includes(latest.status.toLowerCase())) {
        throw httpError(
          502,
          `AgentKit Session entered terminal status ${latest.status}`,
        );
      }
    } catch (error) {
      const stillPropagating = error instanceof AgentkitApiError &&
        error.code === "InvalidResource.NotFound";
      if (!stillPropagating || attempt === 11) throw error;
    }
    if (attempt < 11) await new Promise((resolve) => setTimeout(resolve, 5_000));
  }
  throw httpError(
    504,
    `AgentKit Session did not become ready (last status: ${latest.status})`,
  );
}

function publicAgentkitSession(session: AgentkitSessionSummary) {
  return {
    sessionId: session.sessionId,
    ...(session.toolId ? { toolId: session.toolId } : {}),
    status: session.status,
    ...(session.userSessionId ? { userSessionId: session.userSessionId } : {}),
    ...(session.toolType ? { toolType: session.toolType } : {}),
    ...(session.createdAt ? { createdAt: session.createdAt } : {}),
    ...(session.expireAt ? { expireAt: session.expireAt } : {}),
    ...(session.endpoint ? { endpoint: safeDisplayEndpoint(session.endpoint) } : {}),
  };
}

function publicAgentkitSessionSnapshot(snapshot: AgentkitSessionSnapshotSummary) {
  return {
    snapshotId: snapshot.snapshotId,
    ...(snapshot.toolId ? { toolId: snapshot.toolId } : {}),
    ...(snapshot.sessionId ? { sessionId: snapshot.sessionId } : {}),
    ...(snapshot.userSessionId ? { userSessionId: snapshot.userSessionId } : {}),
    ...(snapshot.status ? { status: snapshot.status } : {}),
    ...(snapshot.reason ? { reason: snapshot.reason } : {}),
    ...(snapshot.createdAt ? { createdAt: snapshot.createdAt } : {}),
  };
}

function publicAgentkitTool(tool: AgentkitToolSummary) {
  return {
    toolId: tool.toolId,
    status: tool.status,
    ...(tool.name ? { name: tool.name } : {}),
    ...(tool.description ? { description: tool.description } : {}),
    ...(tool.toolType ? { toolType: tool.toolType } : {}),
    ...(tool.projectName ? { projectName: tool.projectName } : {}),
    ...(tool.createdAt ? { createdAt: tool.createdAt } : {}),
    ...(tool.updatedAt ? { updatedAt: tool.updatedAt } : {}),
    ...(tool.enableSnapshot !== undefined ? { enableSnapshot: tool.enableSnapshot } : {}),
  };
}

async function searchAgentkitTools(
  client: AgentkitToolsClient,
  search: string,
): Promise<AgentkitToolSummary[]> {
  const fields: AgentkitToolSearchField[] = ["Name", "Id", "Description"];
  const pages = await Promise.all(fields.map((field) => client.listAllTools({
    maxResults: 100,
    search: { field, value: search },
  })));
  const merged = new Map<string, AgentkitToolSummary>();
  for (const tools of pages) {
    for (const tool of tools) merged.set(tool.toolId, tool);
  }
  return [...merged.values()].sort(compareAgentkitTools);
}

function compareAgentkitTools(left: AgentkitToolSummary, right: AgentkitToolSummary): number {
  const timeDifference = (Date.parse(right.updatedAt ?? right.createdAt ?? "") || 0) -
    (Date.parse(left.updatedAt ?? left.createdAt ?? "") || 0);
  if (timeDifference) return timeDifference;
  return (left.name ?? left.toolId).localeCompare(right.name ?? right.toolId);
}

function encodeToolSearchCursor(search: string, offset: number): string {
  return Buffer.from(JSON.stringify({ search, offset }), "utf8").toString("base64url");
}

function decodeToolSearchCursor(cursor: string | null, search: string): number {
  if (!cursor) return 0;
  try {
    const value: unknown = JSON.parse(Buffer.from(cursor, "base64url").toString("utf8"));
    if (
      isRecord(value) &&
      value.search === search &&
      typeof value.offset === "number" &&
      Number.isSafeInteger(value.offset) &&
      value.offset >= 0
    ) {
      return value.offset;
    }
  } catch {
    // Report the same bounded client error for malformed JSON/base64 and mismatched searches.
  }
  throw httpError(400, "invalid tool search pagination token");
}

function queryInteger(
  url: URL,
  name: string,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const raw = url.searchParams.get(name);
  if (raw === null || !raw.trim()) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw httpError(400, `${name} must be an integer between ${minimum} and ${maximum}`);
  }
  return value;
}

function safeDisplayEndpoint(endpoint: string): string {
  try {
    const url = new URL(endpoint);
    const hadQuery = Boolean(url.search);
    url.search = "";
    url.hash = "";
    return `${url.toString()}${hadQuery ? "?<redacted>" : ""}`;
  } catch {
    return "<invalid endpoint>";
  }
}

function agentkitHttpStatus(error: AgentkitApiError): number {
  const code = error.code?.toLowerCase() ?? "";
  if (code.includes("notfound") || code.includes("not_found")) return 404;
  if (code.includes("accessdenied") || code.includes("forbidden")) return 403;
  if (code.includes("invalidparameter") || code.includes("invalidrequest")) return 400;
  if (code.includes("throttl") || error.status === 429) return 429;
  if (error.status === 503) return 503;
  return 502;
}

function writeSse(response: ServerResponse, eventId: number, event: BridgeEvent): void {
  response.write(`id: ${eventId}\ndata: ${JSON.stringify(event)}\n\n`);
}

function parseLastEventId(value: string | string[] | undefined): number {
  const parsed = Number(Array.isArray(value) ? value[0] : value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function serveStatic(response: ServerResponse, url: URL): void {
  if (embeddedWebAssets.size) {
    serveEmbeddedStatic(response, url);
    return;
  }
  if (!existsSync(webRoot)) {
    sendJson(response, 503, { error: "web UI is not built; run `npm run build` first" });
    return;
  }
  let requested: string;
  try {
    requested = decodeURIComponent(url.pathname);
  } catch {
    sendJson(response, 400, { error: "invalid URL encoding" });
    return;
  }
  const relativePath = requested === "/" ? "index.html" : requested.replace(/^\/+/, "");
  let filePath = resolve(webRoot, relativePath);
  if (!filePath.startsWith(`${webRoot}${sep}`) && filePath !== webRoot) {
    sendJson(response, 403, { error: "invalid path" });
    return;
  }
  const isFile = existsSync(filePath) && statSync(filePath).isFile();
  if (!isFile || requested.endsWith("/")) {
    if (extname(requested)) {
      sendJson(response, 404, { error: "static asset not found" });
      return;
    }
    filePath = resolve(webRoot, "index.html");
  }
  response.writeHead(200, {
    ...COMMON_HEADERS,
    "content-security-policy": "default-src 'self'; base-uri 'none'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; frame-src 'self' http://127.0.0.1:* http://localhost:*; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self'",
    "content-type": contentType(filePath),
    "cache-control": filePath.endsWith("index.html")
      ? "no-cache"
      : "public, max-age=31536000, immutable",
  });
  createReadStream(filePath).pipe(response);
}

function serveEmbeddedStatic(response: ServerResponse, url: URL): void {
  let requested: string;
  try {
    requested = decodeURIComponent(url.pathname);
  } catch {
    sendJson(response, 400, { error: "invalid URL encoding" });
    return;
  }
  const key = requested === "/" ? "index.html" : requested.replace(/^\/+/, "");
  let asset = embeddedWebAssets.get(key);
  let resolvedKey = key;
  if (!asset && !extname(requested) && !requested.endsWith("/")) {
    asset = embeddedWebAssets.get("index.html");
    resolvedKey = "index.html";
  }
  if (!asset) {
    sendJson(response, 404, { error: "static asset not found" });
    return;
  }
  response.writeHead(200, {
    ...COMMON_HEADERS,
    "content-security-policy": "default-src 'self'; base-uri 'none'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; frame-src 'self' http://127.0.0.1:* http://localhost:*; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self'",
    "content-type": asset.contentType,
    "cache-control": resolvedKey === "index.html"
      ? "no-cache"
      : "public, max-age=31536000, immutable",
  });
  response.end(asset.body);
}

function contentType(path: string): string {
  return (
    {
      ".html": "text/html; charset=utf-8",
      ".js": "text/javascript; charset=utf-8",
      ".css": "text/css; charset=utf-8",
      ".svg": "image/svg+xml",
      ".png": "image/png",
      ".ico": "image/x-icon",
      ".json": "application/json; charset=utf-8",
    }[extname(path)] ?? "application/octet-stream"
  );
}

function isApprovalDecision(value: unknown): value is ApprovalDecision {
  return ["accept", "acceptForSession", "decline", "cancel"].includes(String(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function httpError(status: number, message: string): Error & { status: number } {
  const error = new Error(message) as Error & { status: number };
  error.status = status;
  return error;
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

function hasCapability(request: IncomingMessage): boolean {
  const cookie = request.headers.cookie
    ?.split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${CAPABILITY_COOKIE}=`));
  const supplied = cookie?.slice(CAPABILITY_COOKIE.length + 1);
  if (!supplied) return false;
  const expectedBuffer = Buffer.from(capabilityToken);
  const suppliedBuffer = Buffer.from(supplied);
  return suppliedBuffer.length === expectedBuffer.length && timingSafeEqual(suppliedBuffer, expectedBuffer);
}

function scheduleOrphanCleanup(session: BridgeSession): void {
  cancelOrphanCleanup(session.id);
  const timer = setTimeout(() => {
    orphanTimers.delete(session.id);
    if (sessionStreamCounts.has(session.id) || sessions.get(session.id) !== session) return;
    sessions.delete(session.id);
    session.close();
    console.info(`[session ${sessionTag(session.id)}] closed after browser disconnect grace period`);
  }, SESSION_ORPHAN_GRACE_MS);
  timer.unref();
  orphanTimers.set(session.id, timer);
}

function cancelOrphanCleanup(sessionId: string): void {
  const timer = orphanTimers.get(sessionId);
  if (!timer) return;
  clearTimeout(timer);
  orphanTimers.delete(sessionId);
}

const host = runtimeSettings.SITULA_HOST;
const port = Number(runtimeSettings.SITULA_PORT);
if (!Number.isInteger(port) || port < 0 || port > 65_535) {
  throw new Error("SITULA_PORT must be an integer between 0 and 65535");
}
if (!Number.isFinite(SESSION_ORPHAN_GRACE_MS) || SESSION_ORPHAN_GRACE_MS <= 0) {
  throw new Error("SITULA_ORPHAN_GRACE_MS must be greater than zero");
}

const browserProxy = new SandboxBrowserProxy({
  getSession: (sessionId) => sessions.get(sessionId),
});
const terminalProxy = new SandboxTerminalProxy({
  getSession: (sessionId) => sessions.get(sessionId),
});
const workspaceProxy = new SandboxWorkspaceProxy();

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
  void terminalProxy.handleHttp(request, response, url)
    .then((handled) => handled ? true : browserProxy.handleHttp(request, response, url))
    .then((handled) => handled ? true : workspaceProxy.handleHttp(request, response, url))
    .then((handled) => handled ? true : handleApi(request, response, url))
    .then((handled) => {
      if (!handled) serveStatic(response, url);
    })
    .catch((error: unknown) => {
      const status = isRecord(error) && typeof error.status === "number"
        ? error.status
        : error instanceof URIError
          ? 400
          : error instanceof CodexAppServerError
            ? 502
            : error instanceof AgentkitApiError
              ? agentkitHttpStatus(error)
            : 500;
      if (!response.headersSent) sendJson(response, status, { error: errorText(error) });
      else response.end();
    });
});

server.on("upgrade", (request, socket, head) => {
  if (terminalProxy.handleUpgrade(request, socket, head)) return;
  if (browserProxy.handleUpgrade(request, socket, head)) return;
  if (workspaceProxy.handleUpgrade(request, socket, head)) return;
  socket.write("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n");
  socket.destroy();
});

server.listen(port, host, () => {
  const address = server.address();
  const listeningPort = typeof address === "object" && address ? address.port : port;
  console.log(`Situla web client: http://${host}:${listeningPort}`);
  if (host !== "127.0.0.1" && host !== "localhost" && host !== "::1") {
    console.warn("warning: non-loopback browser requests are rejected by Host validation");
  }
});

function shutdown(): void {
  for (const session of sessions.values()) session.close();
  sessions.clear();
  for (const response of eventStreams) response.end();
  eventStreams.clear();
  for (const timer of orphanTimers.values()) clearTimeout(timer);
  orphanTimers.clear();
  sessionStreamCounts.clear();
  terminalProxy.close();
  browserProxy.close();
  workspaceProxy.close();
  server.close();
}

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);
