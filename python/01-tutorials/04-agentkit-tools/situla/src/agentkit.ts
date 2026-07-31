import { createHash, createHmac, randomUUID } from "node:crypto";
import { SITULA_VERSION } from "./version.ts";

const DEFAULT_REGION = "cn-beijing";
const API_VERSION = "2025-10-30";
const DEFAULT_SERVICE = "agentkit";
const CONTENT_TYPE = "application/json";
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_RETRIES = 2;
const MAX_RETRY_DELAY_MS = 30_000;
const RETRYABLE_HTTP_STATUSES = new Set([429, 503]);
const X_CUSTOM_REQUEST_CONTEXT = `situla/${SITULA_VERSION} (schema=v1; entry=sdk; os=node)`;

export interface AgentkitSessionSummary {
  sessionId: string;
  toolId?: string;
  userSessionId?: string;
  status: string;
  toolType?: string;
  createdAt?: string;
  expireAt?: string;
  endpoint?: string;
  internalEndpoint?: string;
  vncUrl?: string;
  webshellUrl?: string;
}

export interface AgentkitSessionPage {
  data: AgentkitSessionSummary[];
  nextToken?: string;
  requestId?: string;
}

export interface AgentkitToolSummary {
  toolId: string;
  name?: string;
  description?: string;
  status: string;
  toolType?: string;
  projectName?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface AgentkitToolPage {
  data: AgentkitToolSummary[];
  nextToken?: string;
  requestId?: string;
}

export type AgentkitToolSearchField = "Id" | "Name" | "Description";

export interface ListAgentkitToolsInput {
  maxResults?: number;
  nextToken?: string;
  search?: {
    field: AgentkitToolSearchField;
    value: string;
  };
}

export interface CreateAgentkitSessionInput {
  userSessionId?: string;
  ttl?: number;
}

export interface AgentkitToolsOptions {
  accessKey: string;
  secretKey: string;
  sessionToken?: string;
  region?: string;
  service?: string;
  host?: string;
  fetch?: typeof fetch;
  now?: () => Date;
  timeoutMs?: number;
  retries?: number;
  sleep?: (milliseconds: number) => Promise<void>;
}

interface AgentkitResponse {
  ResponseMetadata?: {
    RequestId?: string;
    Action?: string;
    Error?: { Code?: string; Message?: string };
  };
  Result?: Record<string, unknown>;
}

interface InvokeResult {
  result: Record<string, unknown>;
  requestId?: string;
}

interface AgentkitApiErrorDetails {
  action: string;
  code?: string;
  status?: number;
  requestId?: string;
  cause?: unknown;
}

export class AgentkitApiError extends Error {
  readonly action: string;
  readonly code?: string;
  readonly status?: number;
  readonly requestId?: string;

  constructor(message: string, details: AgentkitApiErrorDetails) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause });
    this.name = "AgentkitApiError";
    this.action = details.action;
    this.code = details.code;
    this.status = details.status;
    this.requestId = details.requestId;
  }
}

export class AgentkitToolsClient {
  readonly region: string;
  readonly host: string;
  readonly service: string;

  #accessKey: string;
  #secretKey: string;
  #sessionToken?: string;
  #fetch: typeof fetch;
  #now: () => Date;
  #timeoutMs: number;
  #retries: number;
  #sleep: (milliseconds: number) => Promise<void>;

  constructor(options: AgentkitToolsOptions) {
    this.#accessKey = required(options.accessKey, "Volcengine access key");
    this.#secretKey = required(options.secretKey, "Volcengine secret key");
    this.#sessionToken = options.sessionToken?.trim() || undefined;
    this.region = normalizeRegion(options.region ?? DEFAULT_REGION);
    this.service = normalizeService(options.service ?? DEFAULT_SERVICE);
    this.host = normalizeHost(options.host ?? agentkitHost(this.region));
    this.#fetch = options.fetch ?? fetch;
    this.#now = options.now ?? (() => new Date());
    this.#timeoutMs = positiveInteger(options.timeoutMs ?? DEFAULT_TIMEOUT_MS, "request timeout");
    this.#retries = nonNegativeInteger(options.retries ?? DEFAULT_RETRIES, "request retries");
    this.#sleep = options.sleep ?? ((milliseconds) =>
      new Promise((resolve) => setTimeout(resolve, milliseconds)));
  }

  async listTools(input: ListAgentkitToolsInput = {}): Promise<AgentkitToolPage> {
    const maxResults = input.maxResults ?? 10;
    if (!Number.isSafeInteger(maxResults) || maxResults < 1 || maxResults > 100) {
      throw new TypeError("tool page size must be an integer between 1 and 100");
    }
    const searchValue = input.search?.value.trim();
    const { result, requestId } = await this.#invoke("ListTools", {
      MaxResults: maxResults,
      ...(input.nextToken ? { NextToken: input.nextToken } : {}),
      ...(input.search && searchValue
        ? { Filters: [{ NameContains: input.search.field, Values: [searchValue] }] }
        : {}),
    });
    if (result.Tools !== undefined && !Array.isArray(result.Tools)) {
      throw invalidResponse("ListTools", "Result.Tools is not an array", requestId);
    }
    const data = ((result.Tools ?? []) as unknown[]).map((rawTool, index) => {
      const tool = parseTool(rawTool);
      if (!tool) {
        throw invalidResponse(
          "ListTools",
          `Result.Tools[${index}] is missing ToolId`,
          requestId,
        );
      }
      return tool;
    });
    if (result.NextToken !== undefined && typeof result.NextToken !== "string") {
      throw invalidResponse("ListTools", "Result.NextToken is not a string", requestId);
    }
    return {
      data,
      ...(typeof result.NextToken === "string" && result.NextToken
        ? { nextToken: result.NextToken }
        : {}),
      ...(requestId ? { requestId } : {}),
    };
  }

  async listAllTools(
    input: Omit<ListAgentkitToolsInput, "nextToken"> = {},
    maxPages = 100,
  ): Promise<AgentkitToolSummary[]> {
    positiveInteger(maxPages, "maximum tool page count");
    const tools = new Map<string, AgentkitToolSummary>();
    const seenTokens = new Set<string>();
    let nextToken: string | undefined;

    for (let pageNumber = 0; pageNumber < maxPages; pageNumber += 1) {
      const page = await this.listTools({ ...input, ...(nextToken ? { nextToken } : {}) });
      for (const tool of page.data) tools.set(tool.toolId, tool);
      if (!page.nextToken) return [...tools.values()];
      if (seenTokens.has(page.nextToken)) {
        throw invalidResponse(
          "ListTools",
          "response repeated NextToken and would cause a pagination loop",
          page.requestId,
        );
      }
      seenTokens.add(page.nextToken);
      nextToken = page.nextToken;
    }

    throw invalidResponse(
      "ListTools",
      `response exceeded the ${maxPages}-page safety limit`,
    );
  }

  async listSessions(toolId: string, nextToken?: string): Promise<AgentkitSessionPage> {
    const normalizedToolId = required(toolId, "AgentKit Tool ID");
    const { result, requestId } = await this.#invoke("ListSessions", {
      ToolId: normalizedToolId,
      MaxResults: 100,
      ...(nextToken ? { NextToken: nextToken } : {}),
    });
    if (result.SessionInfos !== undefined && !Array.isArray(result.SessionInfos)) {
      throw invalidResponse("ListSessions", "Result.SessionInfos is not an array", requestId);
    }
    const rawSessions = (result.SessionInfos ?? []) as unknown[];
    const data = rawSessions.map((rawSession, index) => {
      const session = parseSession(rawSession, "Unknown");
      if (!session) {
        throw invalidResponse(
          "ListSessions",
          `Result.SessionInfos[${index}] is missing SessionId`,
          requestId,
        );
      }
      return { ...session, toolId: session.toolId ?? normalizedToolId };
    }).sort(compareSessions);
    if (result.NextToken !== undefined && typeof result.NextToken !== "string") {
      throw invalidResponse("ListSessions", "Result.NextToken is not a string", requestId);
    }
    return {
      data,
      ...(typeof result.NextToken === "string" && result.NextToken
        ? { nextToken: result.NextToken }
        : {}),
      ...(requestId ? { requestId } : {}),
    };
  }

  async listAllSessions(toolId: string, maxPages = 100): Promise<AgentkitSessionSummary[]> {
    const normalizedToolId = required(toolId, "AgentKit Tool ID");
    positiveInteger(maxPages, "maximum session page count");
    const sessions = new Map<string, AgentkitSessionSummary>();
    const seenTokens = new Set<string>();
    let nextToken: string | undefined;

    for (let pageNumber = 0; pageNumber < maxPages; pageNumber += 1) {
      const page = await this.listSessions(normalizedToolId, nextToken);
      for (const session of page.data) sessions.set(session.sessionId, session);
      if (!page.nextToken) return [...sessions.values()].sort(compareSessions);
      if (seenTokens.has(page.nextToken)) {
        throw invalidResponse(
          "ListSessions",
          "response repeated NextToken and would cause a pagination loop",
          page.requestId,
        );
      }
      seenTokens.add(page.nextToken);
      nextToken = page.nextToken;
    }

    throw invalidResponse(
      "ListSessions",
      `response exceeded the ${maxPages}-page safety limit`,
    );
  }

  async getSession(toolId: string, sessionId: string): Promise<AgentkitSessionSummary> {
    const normalizedToolId = required(toolId, "AgentKit Tool ID");
    const { result, requestId } = await this.#invoke("GetSession", {
      ToolId: normalizedToolId,
      SessionId: required(sessionId, "AgentKit Session ID"),
    });
    const session = parseSession(result, "Unknown");
    if (!session) {
      throw invalidResponse("GetSession", "Result is missing SessionId", requestId);
    }
    return { ...session, toolId: session.toolId ?? normalizedToolId };
  }

  async createSession(
    toolId: string,
    input: CreateAgentkitSessionInput = {},
  ): Promise<AgentkitSessionSummary> {
    const normalizedToolId = required(toolId, "AgentKit Tool ID");
    const ttl = input.ttl ?? 28_800;
    if (!Number.isInteger(ttl) || ttl < 60 || ttl > 604_800) {
      throw new TypeError("session TTL must be an integer between 60 and 604800 seconds");
    }
    const userSessionId = input.userSessionId?.trim() || `situla-${randomUUID()}`;
    if (userSessionId.length > 128) {
      throw new TypeError("UserSessionId must not exceed 128 characters");
    }
    const { result, requestId } = await this.#invoke("CreateSession", {
      ToolId: normalizedToolId,
      UserSessionId: userSessionId,
      Ttl: ttl,
      TtlUnit: "second",
    });
    const session = parseSession(
      { ...result, UserSessionId: result.UserSessionId ?? userSessionId },
      "Creating",
    );
    if (!session) {
      throw invalidResponse("CreateSession", "Result is missing SessionId", requestId);
    }
    return { ...session, toolId: session.toolId ?? normalizedToolId };
  }

  async #invoke(action: string, payload: Record<string, unknown>): Promise<InvokeResult> {
    const body = JSON.stringify(payload);
    const url = `https://${this.host}/?${canonicalQuery({
      Action: action,
      Version: API_VERSION,
    })}`;

    for (let attempt = 0; attempt <= this.#retries; attempt += 1) {
      const headers = signAgentkitRequest({
        action,
        body,
        accessKey: this.#accessKey,
        secretKey: this.#secretKey,
        region: this.region,
        service: this.service,
        host: this.host,
        date: this.#now(),
        ...(this.#sessionToken ? { sessionToken: this.#sessionToken } : {}),
      });
      let response: Response;
      try {
        response = await this.#fetch(url, {
          method: "POST",
          headers,
          body,
          signal: AbortSignal.timeout(this.#timeoutMs),
        });
      } catch (error) {
        if (attempt < this.#retries && isIdempotentAction(action)) {
          await this.#sleep(backoffMilliseconds(attempt));
          continue;
        }
        throw new AgentkitApiError(
          `AgentKit ${action} request failed: ${errorText(error)}`,
          { action, code: "NetworkError", cause: error },
        );
      }

      let text: string;
      try {
        text = await response.text();
      } catch (error) {
        if (attempt < this.#retries && isIdempotentAction(action)) {
          await this.#sleep(backoffMilliseconds(attempt));
          continue;
        }
        throw new AgentkitApiError(
          `AgentKit ${action} response could not be read (HTTP ${response.status})`,
          { action, code: "NetworkError", status: response.status, cause: error },
        );
      }

      let parsed: AgentkitResponse | undefined;
      if (text) {
        try {
          const value: unknown = JSON.parse(text);
          if (isRecord(value)) parsed = value as AgentkitResponse;
        } catch {
          // Report a sanitized protocol error below; never echo the response body.
        }
      }
      const metadata = isRecord(parsed?.ResponseMetadata)
        ? parsed.ResponseMetadata
        : undefined;
      const requestId = typeof metadata?.RequestId === "string" && metadata.RequestId
        ? metadata.RequestId
        : undefined;

      if (RETRYABLE_HTTP_STATUSES.has(response.status) && attempt < this.#retries) {
        await this.#sleep(retryDelayMilliseconds(response.headers, attempt));
        continue;
      }
      if (!parsed) {
        throw new AgentkitApiError(
          `AgentKit ${action} returned invalid JSON (HTTP ${response.status})`,
          { action, code: "InvalidResponse", status: response.status, requestId },
        );
      }

      const apiError = isRecord(metadata?.Error) ? metadata.Error : undefined;
      if (apiError) {
        const code = typeof apiError.Code === "string" && apiError.Code
          ? apiError.Code
          : undefined;
        const message = typeof apiError.Message === "string" && apiError.Message
          ? apiError.Message
          : "unknown error";
        const errorStatus = response.ok ? undefined : response.status;
        throw new AgentkitApiError(
          formatApiError(action, message, { code, status: errorStatus, requestId }),
          { action, code, status: errorStatus, requestId },
        );
      }
      if (!response.ok) {
        throw new AgentkitApiError(
          formatApiError(action, "request failed", { status: response.status, requestId }),
          { action, status: response.status, requestId },
        );
      }
      if (!isRecord(parsed.Result)) {
        throw invalidResponse(action, "response is missing object Result", requestId, response.status);
      }
      return { result: parsed.Result, ...(requestId ? { requestId } : {}) };
    }

    throw new AgentkitApiError(`AgentKit ${action} exhausted its retry budget`, {
      action,
      code: "RetryExhausted",
    });
  }
}

interface SignInput {
  action: string;
  body: string;
  accessKey: string;
  secretKey: string;
  region: string;
  service?: string;
  host: string;
  date: Date;
  sessionToken?: string;
}

export function signAgentkitRequest(input: SignInput): Record<string, string> {
  const service = normalizeService(input.service ?? DEFAULT_SERVICE);
  const xDate = input.date.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const shortDate = xDate.slice(0, 8);
  const contentHash = sha256(input.body);
  const signedHeaders = ["content-type", "host", "x-content-sha256", "x-date"];
  const canonicalHeaders = [
    `content-type:${CONTENT_TYPE}`,
    `host:${input.host}`,
    `x-content-sha256:${contentHash}`,
    `x-date:${xDate}`,
  ];
  if (input.sessionToken) {
    signedHeaders.push("x-security-token");
    canonicalHeaders.push(`x-security-token:${input.sessionToken}`);
  }
  const signedHeadersText = signedHeaders.join(";");
  const canonicalRequest = [
    "POST",
    "/",
    canonicalQuery({ Action: input.action, Version: API_VERSION }),
    canonicalHeaders.join("\n"),
    "",
    signedHeadersText,
    contentHash,
  ].join("\n");
  const credentialScope = `${shortDate}/${input.region}/${service}/request`;
  const stringToSign = [
    "HMAC-SHA256",
    xDate,
    credentialScope,
    sha256(canonicalRequest),
  ].join("\n");
  const dateKey = hmac(Buffer.from(input.secretKey), shortDate);
  const regionKey = hmac(dateKey, input.region);
  const serviceKey = hmac(regionKey, service);
  const signingKey = hmac(serviceKey, "request");
  const signature = createHmac("sha256", signingKey).update(stringToSign).digest("hex");
  return {
    Accept: "application/json",
    Host: input.host,
    "Content-Type": CONTENT_TYPE,
    "X-Content-Sha256": contentHash,
    "X-Custom-Request-Context": X_CUSTOM_REQUEST_CONTEXT,
    "X-Date": xDate,
    ...(input.sessionToken ? { "X-Security-Token": input.sessionToken } : {}),
    Authorization: `HMAC-SHA256 Credential=${input.accessKey}/${credentialScope}, SignedHeaders=${signedHeadersText}, Signature=${signature}`,
  };
}

function agentkitHost(region: string): string {
  return `agentkit.${region}.volcengineapi.com`;
}

function normalizeHost(value: string): string {
  const host = required(value, "Volcengine host");
  if (!/^[a-z0-9.-]+(?::\d{1,5})?$/i.test(host)) {
    throw new TypeError("Volcengine host must be a hostname, optionally followed by a port");
  }
  try {
    const url = new URL(`https://${host}`);
    if (!url.hostname || url.pathname !== "/") throw new Error("invalid host");
  } catch (error) {
    throw new TypeError("Volcengine host is invalid", { cause: error });
  }
  return host;
}

function normalizeService(value: string): string {
  const service = required(value, "Volcengine service");
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(service)) {
    throw new TypeError("Volcengine service contains invalid characters");
  }
  return service;
}

function parseTool(value: unknown): AgentkitToolSummary | undefined {
  if (!isRecord(value) || typeof value.ToolId !== "string" || !value.ToolId) {
    return undefined;
  }
  return {
    toolId: value.ToolId,
    status: typeof value.Status === "string" && value.Status ? value.Status : "Unknown",
    ...(typeof value.Name === "string" && value.Name ? { name: value.Name } : {}),
    ...(typeof value.Description === "string" && value.Description
      ? { description: value.Description }
      : {}),
    ...(typeof value.ToolType === "string" && value.ToolType
      ? { toolType: value.ToolType }
      : {}),
    ...(typeof value.ProjectName === "string" && value.ProjectName
      ? { projectName: value.ProjectName }
      : {}),
    ...(typeof value.CreatedAt === "string" && value.CreatedAt
      ? { createdAt: value.CreatedAt }
      : {}),
    ...(typeof value.UpdatedAt === "string" && value.UpdatedAt
      ? { updatedAt: value.UpdatedAt }
      : {}),
  };
}

function parseSession(
  value: unknown,
  fallbackStatus: string,
): AgentkitSessionSummary | undefined {
  if (!isRecord(value) || typeof value.SessionId !== "string" || !value.SessionId) {
    return undefined;
  }
  const meta = isRecord(value.SessionMeta) ? value.SessionMeta : {};
  return {
    sessionId: value.SessionId,
    status: typeof value.Status === "string" && value.Status ? value.Status : fallbackStatus,
    ...(typeof value.ToolId === "string" && value.ToolId ? { toolId: value.ToolId } : {}),
    ...(typeof value.UserSessionId === "string" && value.UserSessionId
      ? { userSessionId: value.UserSessionId }
      : {}),
    ...(typeof value.ToolType === "string" && value.ToolType
      ? { toolType: value.ToolType }
      : {}),
    ...(typeof value.CreatedAt === "string" && value.CreatedAt
      ? { createdAt: value.CreatedAt }
      : {}),
    ...(typeof value.ExpireAt === "string" && value.ExpireAt
      ? { expireAt: value.ExpireAt }
      : {}),
    ...(typeof value.Endpoint === "string" && value.Endpoint
      ? { endpoint: value.Endpoint }
      : {}),
    ...(typeof value.InternalEndpoint === "string" && value.InternalEndpoint
      ? { internalEndpoint: value.InternalEndpoint }
      : {}),
    ...(typeof meta.VncUrl === "string" && meta.VncUrl ? { vncUrl: meta.VncUrl } : {}),
    ...(typeof meta.WebshellUrl === "string" && meta.WebshellUrl
      ? { webshellUrl: meta.WebshellUrl }
      : {}),
  };
}

function compareSessions(left: AgentkitSessionSummary, right: AgentkitSessionSummary): number {
  const leftTime = Date.parse(left.createdAt ?? "") || 0;
  const rightTime = Date.parse(right.createdAt ?? "") || 0;
  return rightTime - leftTime;
}

function canonicalQuery(query: Record<string, string>): string {
  return Object.entries(query)
    .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
    .map(([key, value]) => `${rfc3986(key)}=${rfc3986(value)}`)
    .join("&");
}

function rfc3986(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (character) =>
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
  );
}

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function hmac(key: Buffer, value: string): Buffer {
  return createHmac("sha256", key).update(value).digest();
}

function required(value: string, label: string): string {
  const normalized = value.trim();
  if (!normalized) throw new TypeError(`${label} is required`);
  return normalized;
}

function normalizeRegion(value: string): string {
  const region = required(value, "AgentKit region");
  if (!/^[a-z0-9](?:[a-z0-9-]{0,62})$/i.test(region)) {
    throw new TypeError("AgentKit region contains invalid characters");
  }
  return region;
}

function positiveInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new TypeError(`${label} must be a positive integer`);
  }
  return value;
}

function nonNegativeInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new TypeError(`${label} must be a non-negative integer`);
  }
  return value;
}

function parsePositiveSeconds(value: string | undefined, fallbackMs: number): number {
  if (!value?.trim()) return fallbackMs;
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return fallbackMs;
  return Math.max(1, Math.round(seconds * 1_000));
}

function parseNonNegativeInteger(value: string | undefined, fallback: number): number {
  if (!value?.trim()) return fallback;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : fallback;
}

function isIdempotentAction(action: string): boolean {
  return action.startsWith("Get") || action.startsWith("List");
}

function backoffMilliseconds(attempt: number): number {
  return Math.min(500 * 2 ** attempt, MAX_RETRY_DELAY_MS);
}

function retryDelayMilliseconds(headers: Headers, attempt: number): number {
  const retryAfter = headers.get("retry-after")?.trim();
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds >= 0) {
      return Math.min(Math.round(seconds * 1_000), MAX_RETRY_DELAY_MS);
    }
    const timestamp = Date.parse(retryAfter);
    if (Number.isFinite(timestamp)) {
      return Math.min(Math.max(0, timestamp - Date.now()), MAX_RETRY_DELAY_MS);
    }
  }
  return backoffMilliseconds(attempt);
}

function formatApiError(
  action: string,
  message: string,
  details: { code?: string; status?: number; requestId?: string },
): string {
  const code = details.code ? ` [${details.code}]` : "";
  const context = [
    details.status === undefined ? undefined : `HTTP ${details.status}`,
    details.requestId ? `RequestId ${details.requestId}` : undefined,
  ].filter((value): value is string => value !== undefined).join(", ");
  return `AgentKit ${action} failed${code}${context ? ` (${context})` : ""}: ${message}`;
}

function invalidResponse(
  action: string,
  detail: string,
  requestId?: string,
  status?: number,
): AgentkitApiError {
  return new AgentkitApiError(
    formatApiError(action, detail, { code: "InvalidResponse", status, requestId }),
    { action, code: "InvalidResponse", status, requestId },
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
