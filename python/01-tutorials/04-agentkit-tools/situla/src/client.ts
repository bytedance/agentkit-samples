import {
  appServerWebSocketUrl,
  errorText,
  isRecord,
  type RpcId,
} from "./protocol.ts";
import {
  modelPageFromResult,
  skillsFromResult,
  threadPageFromResult,
  threadSnapshotFromResult,
  type ApprovalPolicy,
  type ApprovalsReviewer,
  type ModelPage,
  type SkillMetadata,
  type SandboxMode,
  type SessionPermissionSettings,
  type ThreadPage,
  type ThreadRuntimeSettings,
  type ThreadSnapshot,
} from "./app-server-data.ts";
import { SITULA_VERSION } from "./version.ts";

export type ApprovalDecision =
  | "accept"
  | "acceptForSession"
  | "decline"
  | "cancel"
  | { acceptWithExecpolicyAmendment: { execpolicy_amendment: unknown } }
  | { applyNetworkPolicyAmendment: { network_policy_amendment: unknown } };

export interface ApprovalRequest {
  method:
    | "item/commandExecution/requestApproval"
    | "item/fileChange/requestApproval";
  params: Record<string, unknown>;
}

export type ApprovalHandler = (
  request: ApprovalRequest,
) => ApprovalDecision | Promise<ApprovalDecision>;

export interface ProtocolEvent {
  direction: "send" | "receive";
  name: string;
}

export interface WebSocketLike {
  readonly readyState: number;
  addEventListener(
    type: string,
    listener: (event: any) => void,
    options?: boolean | { once?: boolean },
  ): void;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

export interface ClientOptions {
  connectTimeoutMs?: number;
  requestTimeoutMs?: number;
  turnTimeoutMs?: number;
  overloadRetries?: number;
  approvalHandler?: ApprovalHandler;
  onProtocolEvent?: (event: ProtocolEvent) => void;
  onDisconnect?: (error: CodexAppServerError) => void;
  webSocketFactory?: (url: string) => WebSocketLike;
}

export interface ThreadOptions {
  cwd?: string;
  model?: string;
}

export interface DirectoryEntry {
  name: string;
  path: string;
}

export interface DirectoryListing {
  path: string;
  parent?: string;
  directories: DirectoryEntry[];
}

export interface ThreadListOptions {
  cursor?: string;
  limit?: number;
  searchTerm?: string;
  archived?: boolean;
}

export interface TurnResult {
  turnId: string;
  status: string;
  text: string;
  error?: string;
}

export interface SkillInput {
  name: string;
  path: string;
}

interface PendingRequest {
  method: string;
  resolve: (value: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

interface TurnCompletion {
  status: string;
  error?: string;
}

interface TurnWaiter {
  resolve: (completion: TurnCompletion) => void;
  reject: (error: Error) => void;
}

interface TurnState {
  chunks: string[];
  finalText?: string;
  completion?: TurnCompletion;
  subscribers: Set<(delta: string) => void>;
  waiters: Set<TurnWaiter>;
}

const DEFAULT_CONNECT_TIMEOUT_MS = 30_000;
const DEFAULT_REQUEST_TIMEOUT_MS = 300_000;
const DEFAULT_TURN_TIMEOUT_MS = 60 * 60_000;
const DEFAULT_OVERLOAD_RETRIES = 3;
const WS_OPEN = 1;
const OVERLOADED_ERROR_CODE = -32001;

export class CodexAppServerError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "CodexAppServerError";
  }
}

export class CodexRpcError extends CodexAppServerError {
  readonly code: number | string;
  readonly data: unknown;

  constructor(method: string, code: number | string, message: string, data?: unknown) {
    super(`${method} failed (${code}): ${message}`);
    this.name = "CodexRpcError";
    this.code = code;
    this.data = data;
  }
}

export class CodexAppServerClient {
  readonly websocketUrl: string;

  #socket?: WebSocketLike;
  #connected = false;
  #closed = false;
  #nextRequestId = 1;
  #threadId?: string;
  #model?: string;
  #cwd?: string;
  #approvalPolicy?: ApprovalPolicy;
  #approvalsReviewer?: ApprovalsReviewer;
  #sandboxMode?: SandboxMode;
  #networkAccess?: boolean;
  #sessionPermissions?: SessionPermissionSettings;
  #pending = new Map<string, PendingRequest>();
  #turnStates = new Map<string, TurnState>();
  #finishedTurnIds = new Set<string>();
  #notificationListeners = new Set<
    (method: string, params: Record<string, unknown>) => void
  >();
  #connectTimeoutMs: number;
  #requestTimeoutMs: number;
  #turnTimeoutMs: number;
  #overloadRetries: number;
  #approvalHandler?: ApprovalHandler;
  #onProtocolEvent?: (event: ProtocolEvent) => void;
  #onDisconnect?: (error: CodexAppServerError) => void;
  #disconnectNotified = false;
  #disconnectError?: CodexAppServerError;
  #webSocketFactory: (url: string) => WebSocketLike;

  constructor(publicSandboxUrl: string, options: ClientOptions = {}) {
    this.websocketUrl = appServerWebSocketUrl(publicSandboxUrl);
    this.#connectTimeoutMs = options.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS;
    this.#requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
    this.#turnTimeoutMs = options.turnTimeoutMs ??
      (options.requestTimeoutMs === undefined
        ? DEFAULT_TURN_TIMEOUT_MS
        : this.#requestTimeoutMs);
    this.#overloadRetries = options.overloadRetries ?? DEFAULT_OVERLOAD_RETRIES;
    this.#approvalHandler = options.approvalHandler;
    this.#onProtocolEvent = options.onProtocolEvent;
    this.#onDisconnect = options.onDisconnect;
    this.#webSocketFactory = options.webSocketFactory ?? defaultWebSocketFactory;

    for (const [name, value] of [
      ["connectTimeoutMs", this.#connectTimeoutMs],
      ["requestTimeoutMs", this.#requestTimeoutMs],
      ["turnTimeoutMs", this.#turnTimeoutMs],
    ] as const) {
      if (!Number.isFinite(value) || value <= 0) {
        throw new TypeError(`${name} must be greater than zero`);
      }
    }
    if (!Number.isInteger(this.#overloadRetries) || this.#overloadRetries < 0) {
      throw new TypeError("overloadRetries must be a non-negative integer");
    }
  }

  get threadId(): string | undefined {
    return this.#threadId;
  }

  get model(): string | undefined {
    return this.#model;
  }

  get cwd(): string | undefined {
    return this.#cwd;
  }

  get approvalPolicy(): ApprovalPolicy | undefined {
    return this.#approvalPolicy;
  }

  get approvalsReviewer(): ApprovalsReviewer | undefined {
    return this.#approvalsReviewer;
  }

  get sandboxMode(): SandboxMode | undefined {
    return this.#sandboxMode;
  }

  get networkAccess(): boolean | undefined {
    return this.#networkAccess;
  }

  get connected(): boolean {
    return this.#connected;
  }

  async connect(): Promise<void> {
    if (this.#connected) return;
    if (this.#closed) throw new CodexAppServerError("client is closed");

    let socket: WebSocketLike;
    try {
      socket = this.#webSocketFactory(this.websocketUrl);
    } catch (error) {
      throw new CodexAppServerError(`could not create WebSocket: ${errorText(error)}`, {
        cause: error,
      });
    }
    this.#socket = socket;
    socket.addEventListener("message", (event) => this.#handleMessage(event.data));
    socket.addEventListener("close", () => this.#handleClose());

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const settle = (action: () => void): void => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        action();
      };
      const timer = setTimeout(() => {
        settle(() => {
          reject(
            new CodexAppServerError(
              `timed out after ${this.#connectTimeoutMs}ms connecting to app-server`,
            ),
          );
          socket.close();
        });
      }, this.#connectTimeoutMs);

      socket.addEventListener(
        "open",
        () => {
          settle(() => {
            this.#connected = true;
            resolve();
          });
        },
        { once: true },
      );
      socket.addEventListener(
        "error",
        () => {
          settle(() => {
            reject(new CodexAppServerError("WebSocket connection failed"));
            socket.close();
          });
        },
        { once: true },
      );
      socket.addEventListener(
        "close",
        () => {
          settle(() =>
            reject(new CodexAppServerError("WebSocket closed before the connection opened")),
          );
        },
        { once: true },
      );
    });

    try {
      await this.request("initialize", {
        clientInfo: {
          // The sandbox's model gateway uses this value as the Responses
          // `originator` header. Keep it aligned with AgentKit's reference
          // client so the same provider compatibility path is selected.
          name: "agentkit_codex_app_server_client",
          title: "AgentKit Codex App Server Client",
          version: SITULA_VERSION,
        },
        capabilities: { experimentalApi: true },
      });
      this.notify("initialized");
    } catch (error) {
      this.close();
      throw error;
    }
  }

  async startThread(options: ThreadOptions = {}): Promise<string> {
    return (await this.startThreadSnapshot(options)).thread.id;
  }

  async startThreadSnapshot(options: ThreadOptions = {}): Promise<ThreadSnapshot> {
    const params = threadParams(options);
    const result = await this.request("thread/start", params);
    return this.#activateThreadSnapshot(
      threadSnapshotFromResult("thread/start", result),
    );
  }

  async resumeThread(threadId: string, options: ThreadOptions = {}): Promise<string> {
    return (await this.resumeThreadSnapshot(threadId, options)).thread.id;
  }

  async resumeThreadSnapshot(
    threadId: string,
    options: ThreadOptions = {},
  ): Promise<ThreadSnapshot> {
    if (!threadId.trim()) throw new TypeError("threadId must not be empty");
    const params = { threadId, ...threadParams(options) };
    const result = await this.request("thread/resume", params);
    return this.#activateThreadSnapshot(
      threadSnapshotFromResult("thread/resume", result),
    );
  }

  async listThreads(options: ThreadListOptions = {}): Promise<ThreadPage> {
    const params: Record<string, unknown> = {
      limit: options.limit ?? 30,
      sortKey: "updated_at",
      sortDirection: "desc",
      archived: options.archived ?? false,
    };
    if (options.cursor) params.cursor = options.cursor;
    if (options.searchTerm) params.searchTerm = options.searchTerm;
    return threadPageFromResult(await this.request("thread/list", params));
  }

  async forkThread(options: ThreadOptions = {}): Promise<ThreadSnapshot> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    const params = { threadId: this.#threadId, ...threadParams(options) };
    const result = await this.request("thread/fork", params);
    return this.#activateThreadSnapshot(
      threadSnapshotFromResult("thread/fork", result),
    );
  }

  async archiveThread(threadId = this.#threadId): Promise<void> {
    if (!threadId) throw new CodexAppServerError("no thread to archive");
    await this.request("thread/archive", { threadId });
  }

  async compactThread(): Promise<void> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    await this.request("thread/compact/start", { threadId: this.#threadId });
  }

  async listModels(cursor?: string): Promise<ModelPage> {
    const params: Record<string, unknown> = { limit: 100, includeHidden: false };
    if (cursor) params.cursor = cursor;
    return modelPageFromResult(await this.request("model/list", params));
  }

  async listSkills(forceReload = false): Promise<SkillMetadata[]> {
    const params: Record<string, unknown> = { forceReload };
    if (this.#cwd) params.cwds = [this.#cwd];
    return skillsFromResult(await this.request("skills/list", params), this.#cwd);
  }

  async setModel(model: string): Promise<void> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    if (!model.trim()) throw new TypeError("model must not be empty");
    await this.request("thread/settings/update", {
      threadId: this.#threadId,
      model,
    });
    this.#model = model;
  }

  async updateThreadSettings(
    settings: ThreadOptions,
  ): Promise<{ cwd?: string; model?: string }> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    const params: Record<string, unknown> = { threadId: this.#threadId };
    if (settings.cwd !== undefined) {
      assertAbsoluteDirectory(settings.cwd);
      params.cwd = settings.cwd;
    }
    if (settings.model !== undefined) {
      if (!settings.model.trim()) throw new TypeError("model must not be empty");
      params.model = settings.model;
    }
    await this.request("thread/settings/update", params);
    if (settings.cwd !== undefined) this.#cwd = settings.cwd;
    if (settings.model !== undefined) this.#model = settings.model;
    return {
      ...(this.#cwd ? { cwd: this.#cwd } : {}),
      ...(this.#model ? { model: this.#model } : {}),
    };
  }

  async updateSessionPermissions(
    settings: SessionPermissionSettings,
  ): Promise<SessionPermissionSettings> {
    const normalized = normalizePermissionSettings(settings);
    const config = await this.request("config/read", { includeLayers: true });
    const expectedVersion = userConfigVersion(config);
    await this.request("config/batchWrite", {
      edits: [
        configEdit("sandbox_mode", normalized.sandboxMode),
        configEdit("approval_policy", normalized.approvalPolicy),
        configEdit("approvals_reviewer", normalized.approvalsReviewer),
        configEdit(
          "sandbox_workspace_write.network_access",
          normalized.networkAccess,
        ),
      ],
      ...(expectedVersion ? { expectedVersion } : {}),
      reloadUserConfig: true,
    });
    this.#sessionPermissions = normalized;
    await this.#syncCurrentThreadPermissions(normalized);
    return normalized;
  }

  async listDirectories(path: string): Promise<DirectoryListing> {
    assertAbsoluteDirectory(path);
    const normalized = normalizeDirectory(path);
    const result = await this.request("fs/readDirectory", { path: normalized });
    if (!Array.isArray(result.entries)) {
      throw new CodexAppServerError("fs/readDirectory response did not contain entries");
    }
    const directories = result.entries.flatMap((value) => {
      if (!isRecord(value) || value.isDirectory !== true || typeof value.fileName !== "string") {
        return [];
      }
      const name = value.fileName;
      if (!name || name === "." || name === ".." || name.includes("/")) return [];
      return [{ name, path: joinDirectory(normalized, name) }];
    }).sort((left, right) => left.name.localeCompare(right.name));
    return {
      path: normalized,
      ...(normalized !== "/" ? { parent: parentDirectory(normalized) } : {}),
      directories,
    };
  }

  async runTurn(
    prompt: string,
    onDelta?: (delta: string) => void,
    onStarted?: (turnId: string) => void,
    skills: readonly SkillInput[] = [],
  ): Promise<TurnResult> {
    if (!this.#threadId) {
      throw new CodexAppServerError("startThread() or resumeThread() must be called first");
    }
    if (!prompt) throw new TypeError("prompt must not be empty");

    const result = await this.request("turn/start", {
      threadId: this.#threadId,
      input: [
        { type: "text", text: prompt },
        ...skills.map((skill) => ({
          type: "skill",
          name: skill.name,
          path: skill.path,
        })),
      ],
      ...(this.#sessionPermissions
        ? runtimePermissionParams(this.#sessionPermissions, this.#cwd)
        : {}),
    });
    const turn = result.turn;
    if (!isRecord(turn) || typeof turn.id !== "string") {
      throw new CodexAppServerError("turn/start response did not contain turn.id");
    }
    safeCall(onStarted, turn.id);

    const state = this.#turnState(turn.id);
    if (onDelta) {
      state.subscribers.add(onDelta);
      for (const chunk of state.chunks) safeCall(onDelta, chunk);
    }

    try {
      const completion =
        state.completion ?? (await this.#waitForTurn(turn.id, state));
      const text = state.finalText ?? state.chunks.join("");
      if (completion.status === "failed") {
        throw new CodexAppServerError(completion.error ?? "turn failed");
      }
      return {
        turnId: turn.id,
        status: completion.status,
        text,
        ...(completion.error ? { error: completion.error } : {}),
      };
    } finally {
      if (onDelta) state.subscribers.delete(onDelta);
      this.#turnStates.delete(turn.id);
      this.#rememberFinishedTurn(turn.id);
    }
  }

  async interruptTurn(turnId: string): Promise<void> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    await this.request("turn/interrupt", {
      threadId: this.#threadId,
      turnId,
    });
  }

  async request(
    method: string,
    params?: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    let attempt = 0;
    while (true) {
      try {
        return await this.#requestOnce(method, params);
      } catch (error) {
        if (
          !(error instanceof CodexRpcError) ||
          Number(error.code) !== OVERLOADED_ERROR_CODE ||
          attempt >= this.#overloadRetries
        ) {
          throw error;
        }
        const delayMs = 100 * 2 ** attempt + Math.floor(Math.random() * 100);
        attempt += 1;
        await delay(delayMs);
      }
    }
  }

  notify(method: string, params?: Record<string, unknown>): void {
    this.#send({ method, ...(params === undefined ? {} : { params }) });
  }

  onNotification(
    listener: (method: string, params: Record<string, unknown>) => void,
  ): () => void {
    this.#notificationListeners.add(listener);
    return () => this.#notificationListeners.delete(listener);
  }

  close(): void {
    if (this.#closed) return;
    this.#closed = true;
    this.#connected = false;
    this.#socket?.close(1000, "client closing");
    this.#rejectOutstanding(new CodexAppServerError("client closed"));
  }

  #requestOnce(
    method: string,
    params?: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const id = this.#nextRequestId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.#pending.delete(requestKey(id));
        reject(
          new CodexAppServerError(
            `${method} timed out after ${this.#requestTimeoutMs}ms`,
          ),
        );
      }, this.#requestTimeoutMs);
      this.#pending.set(requestKey(id), { method, resolve, reject, timer });
      try {
        this.#send({ id, method, ...(params === undefined ? {} : { params }) });
      } catch (error) {
        clearTimeout(timer);
        this.#pending.delete(requestKey(id));
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  #send(message: Record<string, unknown>): void {
    if (!this.#socket || !this.#connected || this.#socket.readyState !== WS_OPEN) {
      throw new CodexAppServerError("WebSocket is not connected");
    }
    safeCall(this.#onProtocolEvent, {
      direction: "send",
      name: typeof message.method === "string" ? message.method : "response",
    });
    this.#socket.send(JSON.stringify(message));
  }

  #handleMessage(raw: unknown): void {
    try {
      if (typeof raw !== "string") {
        throw new CodexAppServerError("app-server sent an unsupported binary frame");
      }
      const message: unknown = JSON.parse(raw);
      if (!isRecord(message)) {
        throw new CodexAppServerError("app-server sent a non-object JSON message");
      }

      const method = typeof message.method === "string" ? message.method : undefined;
      safeCall(this.#onProtocolEvent, {
        direction: "receive",
        name: method ?? "response",
      });

      if (method && hasOwn(message, "id")) {
        if (!isRpcId(message.id)) {
          throw new CodexAppServerError("app-server sent a request with an invalid id");
        }
        void this.#handleServerRequest(message.id, method, message.params);
        return;
      }
      if (hasOwn(message, "id")) {
        if (!isRpcId(message.id)) {
          throw new CodexAppServerError("app-server sent a response with an invalid id");
        }
        this.#handleResponse(message.id, message);
        return;
      }
      if (method) {
        if (message.params !== undefined && !isRecord(message.params)) {
          throw new CodexAppServerError(`app-server sent invalid params for ${method}`);
        }
        const params = message.params ?? {};
        this.#handleNotification(method, params);
        return;
      }
      throw new CodexAppServerError("app-server sent an unrecognized message");
    } catch (error) {
      const wrapped =
        error instanceof CodexAppServerError
          ? error
          : new CodexAppServerError(`invalid app-server message: ${errorText(error)}`, {
              cause: error,
            });
      this.#disconnectError = wrapped;
      this.#rejectOutstanding(wrapped);
      this.#socket?.close(1002, "protocol error");
    }
  }

  #handleResponse(id: RpcId, message: Record<string, unknown>): void {
    const key = requestKey(id);
    const pending = this.#pending.get(key);
    if (!pending) return;
    this.#pending.delete(key);
    clearTimeout(pending.timer);

    if (hasOwn(message, "error")) {
      const error = message.error;
      if (isRecord(error)) {
        const code =
          typeof error.code === "number" || typeof error.code === "string"
            ? error.code
            : "unknown";
        const detail = typeof error.message === "string" ? error.message : "unknown error";
        pending.reject(new CodexRpcError(pending.method, code, detail, error.data));
      } else {
        pending.reject(new CodexAppServerError(`${pending.method} failed: ${String(error)}`));
      }
      return;
    }

    if (!isRecord(message.result)) {
      pending.reject(
        new CodexAppServerError(`${pending.method} returned a non-object result`),
      );
      return;
    }
    pending.resolve(message.result);
  }

  async #handleServerRequest(id: RpcId, method: string, rawParams: unknown): Promise<void> {
    if (
      method !== "item/commandExecution/requestApproval" &&
      method !== "item/fileChange/requestApproval" &&
      method !== "item/permissions/requestApproval"
    ) {
      this.#trySend({
        id,
        error: { code: -32601, message: `unsupported server request: ${method}` },
      });
      return;
    }
    if (!isRecord(rawParams)) {
      this.#trySend({ id, error: { code: -32602, message: `invalid params for ${method}` } });
      return;
    }
    const params = rawParams;
    if (
      (method === "item/commandExecution/requestApproval" ||
        method === "item/fileChange/requestApproval") &&
      !hasApprovalIdentity(params)
    ) {
      this.#trySend({ id, error: { code: -32602, message: `invalid params for ${method}` } });
      return;
    }
    try {
      let result: Record<string, unknown> = {};
      if (
        method === "item/commandExecution/requestApproval" ||
        method === "item/fileChange/requestApproval"
      ) {
        const decision = this.#approvalHandler
          ? await this.#approvalHandler({ method, params })
          : "decline";
        result = { decision };
      } else if (method === "item/permissions/requestApproval") {
        result = { permissions: {}, scope: "turn" };
      }
      this.#send({ id, result });
    } catch (error) {
      this.#trySend({
        id,
        error: { code: -32603, message: `client handler failed: ${errorText(error)}` },
      });
    }
  }

  #handleNotification(method: string, params: Record<string, unknown>): void {
    for (const listener of this.#notificationListeners) safeCall(listener, method, params);

    if (method === "item/agentMessage/delta") {
      const turnId = params.turnId;
      const delta = params.delta;
      if (typeof turnId === "string" && typeof delta === "string") {
        if (this.#finishedTurnIds.has(turnId)) return;
        const state = this.#turnState(turnId);
        state.chunks.push(delta);
        for (const subscriber of state.subscribers) safeCall(subscriber, delta);
      }
      return;
    }

    if (method === "item/completed") {
      const turnId = params.turnId;
      const item = params.item;
      if (typeof turnId === "string" && isRecord(item) && item.type === "agentMessage") {
        if (this.#finishedTurnIds.has(turnId)) return;
        const phase = item.phase;
        if (
          typeof item.text === "string" &&
          (phase === undefined || phase === null || phase === "final_answer")
        ) {
          this.#turnState(turnId).finalText = item.text;
        }
      }
      return;
    }

    if (method === "turn/completed" && isRecord(params.turn)) {
      const turnId = params.turn.id;
      if (typeof turnId !== "string") return;
      if (this.#finishedTurnIds.has(turnId)) return;
      const status = typeof params.turn.status === "string" ? params.turn.status : "completed";
      const error = isRecord(params.turn.error) ? params.turn.error.message : undefined;
      const completion: TurnCompletion = {
        status,
        ...(typeof error === "string" ? { error } : {}),
      };
      const state = this.#turnState(turnId);
      state.completion = completion;
      for (const waiter of state.waiters) waiter.resolve(completion);
      state.waiters.clear();
    }
  }

  #turnState(turnId: string): TurnState {
    let state = this.#turnStates.get(turnId);
    if (!state) {
      state = {
        chunks: [],
        subscribers: new Set(),
        waiters: new Set(),
      };
      this.#turnStates.set(turnId, state);
    }
    return state;
  }

  #waitForTurn(turnId: string, state: TurnState): Promise<TurnCompletion> {
    return new Promise((resolve, reject) => {
      const waiter: TurnWaiter = { resolve, reject };
      state.waiters.add(waiter);
      const timer = setTimeout(() => {
        state.waiters.delete(waiter);
        reject(
          new CodexAppServerError(
            `turn ${turnId} timed out after ${this.#turnTimeoutMs}ms`,
          ),
        );
      }, this.#turnTimeoutMs);
      waiter.resolve = (completion) => {
        clearTimeout(timer);
        resolve(completion);
      };
      waiter.reject = (error) => {
        clearTimeout(timer);
        reject(error);
      };
    });
  }

  #handleClose(): void {
    this.#connected = false;
    if (!this.#closed) {
      this.#closed = true;
      const error = this.#disconnectError ??
        new CodexAppServerError("app-server WebSocket connection closed");
      this.#rejectOutstanding(error);
      if (!this.#disconnectNotified) {
        this.#disconnectNotified = true;
        safeCall(this.#onDisconnect, error);
      }
    }
  }

  #rejectOutstanding(error: Error): void {
    for (const pending of this.#pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.#pending.clear();
    for (const state of this.#turnStates.values()) {
      for (const waiter of state.waiters) waiter.reject(error);
      state.waiters.clear();
      state.subscribers.clear();
    }
    this.#turnStates.clear();
  }

  #trySend(message: Record<string, unknown>): void {
    try {
      this.#send(message);
    } catch {
      // The transport may close while an asynchronous server request is being handled.
    }
  }

  #rememberFinishedTurn(turnId: string): void {
    this.#finishedTurnIds.add(turnId);
    if (this.#finishedTurnIds.size > 100) {
      const oldest = this.#finishedTurnIds.values().next().value;
      if (typeof oldest === "string") this.#finishedTurnIds.delete(oldest);
    }
  }

  #applyThreadSnapshot(snapshot: ThreadSnapshot): ThreadSnapshot {
    this.#threadId = snapshot.thread.id;
    if (snapshot.model) this.#model = snapshot.model;
    if (snapshot.cwd) this.#cwd = snapshot.cwd;
    if (snapshot.approvalPolicy) this.#approvalPolicy = snapshot.approvalPolicy;
    if (snapshot.approvalsReviewer) this.#approvalsReviewer = snapshot.approvalsReviewer;
    if (snapshot.sandboxMode) this.#sandboxMode = snapshot.sandboxMode;
    if (snapshot.networkAccess !== undefined) this.#networkAccess = snapshot.networkAccess;
    return snapshot;
  }

  async #activateThreadSnapshot(snapshot: ThreadSnapshot): Promise<ThreadSnapshot> {
    this.#applyThreadSnapshot(snapshot);
    if (!this.#sessionPermissions) return snapshot;
    await this.#syncCurrentThreadPermissions(this.#sessionPermissions);
    return {
      ...snapshot,
      ...this.#sessionPermissions,
    };
  }

  async #syncCurrentThreadPermissions(
    settings: SessionPermissionSettings,
  ): Promise<void> {
    if (!this.#threadId) throw new CodexAppServerError("no active thread");
    await this.request("thread/settings/update", {
      threadId: this.#threadId,
      ...runtimePermissionParams(settings, this.#cwd),
    });
    this.#approvalPolicy = settings.approvalPolicy;
    this.#approvalsReviewer = settings.approvalsReviewer;
    this.#sandboxMode = settings.sandboxMode;
    this.#networkAccess = settings.networkAccess;
  }

  runtimeSettings(): ThreadRuntimeSettings {
    return {
      ...(this.#approvalPolicy ? { approvalPolicy: this.#approvalPolicy } : {}),
      ...(this.#approvalsReviewer
        ? { approvalsReviewer: this.#approvalsReviewer }
        : {}),
      ...(this.#sandboxMode ? { sandboxMode: this.#sandboxMode } : {}),
      ...(this.#networkAccess !== undefined
        ? { networkAccess: this.#networkAccess }
        : {}),
    };
  }
}

function threadParams(options: ThreadOptions): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  if (options.cwd !== undefined) {
    assertAbsoluteDirectory(options.cwd);
    params.cwd = options.cwd;
  }
  if (options.model !== undefined) params.model = options.model;
  return params;
}

function configEdit(keyPath: string, value: unknown): Record<string, unknown> {
  return { keyPath, value, mergeStrategy: "replace" };
}

function normalizePermissionSettings(
  settings: SessionPermissionSettings,
): SessionPermissionSettings {
  return {
    ...settings,
    networkAccess: settings.sandboxMode === "danger-full-access"
      ? true
      : settings.networkAccess,
  };
}

function runtimePermissionParams(
  settings: SessionPermissionSettings,
  cwd: string | undefined,
): Record<string, unknown> {
  return {
    approvalPolicy: settings.approvalPolicy,
    approvalsReviewer: settings.approvalsReviewer,
    sandboxPolicy: sandboxPolicy(settings, cwd),
  };
}

function sandboxPolicy(
  settings: SessionPermissionSettings,
  cwd: string | undefined,
): Record<string, unknown> {
  if (settings.sandboxMode === "danger-full-access") {
    return { type: "dangerFullAccess" };
  }
  if (settings.sandboxMode === "read-only") {
    return {
      type: "readOnly",
      networkAccess: settings.networkAccess,
    };
  }
  return {
    type: "workspaceWrite",
    writableRoots: cwd ? [cwd] : [],
    networkAccess: settings.networkAccess,
    excludeTmpdirEnvVar: false,
    excludeSlashTmp: false,
  };
}

function userConfigVersion(result: Record<string, unknown>): string | undefined {
  if (!Array.isArray(result.layers)) return undefined;
  const layer = result.layers.find((candidate) => {
    if (!isRecord(candidate) || !isRecord(candidate.name)) return false;
    return (
      candidate.name.type === "user" &&
      (candidate.name.profile === undefined || candidate.name.profile === null)
    );
  });
  return isRecord(layer) && typeof layer.version === "string"
    ? layer.version
    : undefined;
}

function assertAbsoluteDirectory(path: string): void {
  if (!path.startsWith("/") || path.includes("\0")) {
    throw new TypeError("working directory must be an absolute path");
  }
}

function normalizeDirectory(path: string): string {
  const normalized = path.replace(/\/+/g, "/").replace(/\/+$/, "");
  return normalized || "/";
}

function joinDirectory(parent: string, name: string): string {
  return parent === "/" ? `/${name}` : `${parent}/${name}`;
}

function parentDirectory(path: string): string {
  const index = path.lastIndexOf("/");
  return index <= 0 ? "/" : path.slice(0, index);
}

function defaultWebSocketFactory(url: string): WebSocketLike {
  if (typeof WebSocket === "undefined") {
    throw new CodexAppServerError("global WebSocket is unavailable; use Node.js 22 or newer");
  }
  return new WebSocket(url) as unknown as WebSocketLike;
}

function hasOwn(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function requestKey(id: RpcId): string {
  return `${typeof id}:${String(id)}`;
}

function isRpcId(value: unknown): value is RpcId {
  return typeof value === "string" || (typeof value === "number" && Number.isFinite(value));
}

function hasApprovalIdentity(params: Record<string, unknown>): boolean {
  return (
    typeof params.threadId === "string" &&
    typeof params.turnId === "string" &&
    typeof params.itemId === "string" &&
    typeof params.startedAtMs === "number" &&
    Number.isFinite(params.startedAtMs)
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function safeCall<Args extends unknown[]>(
  callback: ((...args: Args) => void) | undefined,
  ...args: Args
): void {
  try {
    callback?.(...args);
  } catch {
    // Consumer callbacks must not be able to corrupt the protocol state machine.
  }
}
