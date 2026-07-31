import { randomUUID } from "node:crypto";
import {
  CodexAppServerClient,
  type ApprovalDecision,
  type ApprovalRequest,
  type ClientOptions,
  type SkillInput,
  type DirectoryListing,
  type ThreadOptions,
} from "./client.ts";
import type {
  ApprovalPolicy,
  ApprovalsReviewer,
  ConversationMessage,
  ModelSummary,
  SkillMetadata,
  SandboxMode,
  SessionPermissionSettings,
  ThreadPage,
  ThreadRuntimeSettings,
  ThreadSnapshot,
} from "./app-server-data.ts";
import {
  errorText,
  redactSensitiveText,
  redactedUrl,
  sandboxServiceUrl,
} from "./protocol.ts";

export type BridgeEvent =
  | {
      type: "ready";
      sessionId: string;
      threadId: string;
      messages: ConversationMessage[];
      model?: string;
      cwd?: string;
    } & ThreadRuntimeSettings
  | {
      type: "thread_changed";
      threadId: string;
      messages: ConversationMessage[];
      model?: string;
      cwd?: string;
    } & ThreadRuntimeSettings
  | { type: "turn_started"; requestId: string }
  | { type: "delta"; requestId: string; delta: string }
  | {
      type: "turn_completed";
      requestId: string;
      turnId: string;
      status: string;
      text: string;
    }
  | {
      type: "token_usage";
      requestId: string;
      turnId: string;
      usage: TokenUsageBreakdown;
      threadTotal: TokenUsageBreakdown;
      modelContextWindow: number | null;
    }
  | {
      type: "execution_update";
      requestId: string;
      turnId: string;
      step: ExecutionStep;
    }
  | { type: "turn_error"; requestId: string; message: string }
  | { type: "notification"; method: string; params: Record<string, unknown> }
  | { type: "approval_requested"; approval: BrowserApproval }
  | { type: "approval_resolved"; approvalId: string }
  | { type: "closed"; reason?: string };

export interface BrowserApproval {
  id: string;
  kind: "command" | "file";
  method: ApprovalRequest["method"];
  reason?: string;
  command?: string;
  cwd?: string;
  grantRoot?: string;
  changes?: unknown;
  threadId?: string;
  turnId?: string;
  itemId?: string;
  environmentId?: string | null;
  startedAtMs?: number;
  commandActions?: unknown;
  networkApprovalContext?: unknown;
}

export interface TokenUsageBreakdown {
  totalTokens: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  reasoningOutputTokens: number;
}

export type ExecutionStepKind =
  | "reasoning"
  | "command"
  | "file"
  | "mcp"
  | "dynamic"
  | "web"
  | "collab"
  | "image"
  | "plan"
  | "context"
  | "other";

export interface ExecutionStep {
  id: string;
  kind: ExecutionStepKind;
  title: string;
  status: "running" | "completed" | "failed";
  detail?: string;
  durationMs?: number;
}

export interface SkillSummary {
  id: string;
  name: string;
  description: string;
}

interface BridgeSkill extends SkillInput, SkillSummary {}

export class SkillSelectionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SkillSelectionError";
  }
}

export interface BridgeSessionOptions extends ThreadOptions {
  sandboxUrl: string;
  resumeThreadId?: string;
  requestTimeoutMs?: number;
  clientFactory?: (url: string, options: ClientOptions) => CodexAppServerClient;
}

interface PendingApproval {
  resolve: (decision: ApprovalDecision) => void;
  timer: ReturnType<typeof setTimeout>;
}

interface TurnIdWaiter {
  resolve: (turnId: string) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

interface SequencedEvent {
  id: number;
  event: BridgeEvent;
  bytes: number;
}

type EventSubscriber = (event: BridgeEvent, eventId: number) => void;

const APPROVAL_TIMEOUT_MS = 5 * 60_000;
const EVENT_HISTORY_LIMIT = 1_000;
const EVENT_HISTORY_BYTES_LIMIT = 2 * 1024 * 1024;

export class BridgeSession {
  readonly id = randomUUID();
  readonly displayUrl: string;

  #sandboxUrl: string;
  #client: CodexAppServerClient;
  #threadOptions: ThreadOptions;
  #threadId?: string;
  #messages: ConversationMessage[] = [];
  #threadStarted = false;
  #activeRequestId?: string;
  #activeTurnId?: string;
  #closed = false;
  #subscribers = new Set<EventSubscriber>();
  #pendingApprovals = new Map<string, PendingApproval>();
  #turnIdWaiters = new Set<TurnIdWaiter>();
  #requestIdByTurnId = new Map<string, string>();
  #usageByTurnId = new Map<string, TokenUsageBreakdown>();
  #threadTokenTotal?: TokenUsageBreakdown;
  #nextEventId = 1;
  #eventHistory: SequencedEvent[] = [];
  #eventHistoryBytes = 0;
  #resumeThreadId?: string;
  #skillsById = new Map<string, BridgeSkill>();
  #skillsLoaded = false;
  #skillsCwd?: string;

  constructor(options: BridgeSessionOptions) {
    this.#sandboxUrl = options.sandboxUrl;
    this.#resumeThreadId = options.resumeThreadId;
    this.displayUrl = redactedUrl(options.sandboxUrl);
    this.#threadOptions = {
      cwd: options.cwd,
      model: options.model,
    };
    const timeoutMs = options.requestTimeoutMs ?? 300_000;
    const clientFactory = options.clientFactory ?? ((url, clientOptions) =>
      new CodexAppServerClient(url, clientOptions));
    this.#client = clientFactory(options.sandboxUrl, {
      requestTimeoutMs: timeoutMs,
      turnTimeoutMs: timeoutMs,
      approvalHandler: (request) => this.#requestApproval(request),
      onDisconnect: (error) => this.#finishClose(false, error.message),
    });
    this.#client.onNotification((method, params) => {
      if (method === "skills/changed") this.#invalidateSkills();
      if (method === "turn/started" && isRecord(params.turn)) {
        const turnId = params.turn.id;
        if (typeof turnId === "string") this.#setActiveTurnId(turnId);
      }
      if (method === "thread/tokenUsage/updated") {
        if (this.#emitTokenUsage(params)) return;
      }
      if (method === "item/started" || method === "item/completed") {
        this.#emitExecutionUpdate(params, method === "item/completed");
        return;
      }
      if (/\/delta$/i.test(method)) return;
      this.emit({ type: "notification", method, params });
    });
  }

  get threadId(): string | undefined {
    return this.#threadId;
  }

  get active(): boolean {
    return this.#activeRequestId !== undefined;
  }

  get workspaceLocked(): boolean {
    return this.active || this.#threadStarted;
  }

  get model(): string | undefined {
    return this.#client.model;
  }

  get cwd(): string | undefined {
    return this.#client.cwd;
  }

  get approvalPolicy(): ApprovalPolicy | undefined {
    return this.#client.approvalPolicy;
  }

  get approvalsReviewer(): ApprovalsReviewer | undefined {
    return this.#client.approvalsReviewer;
  }

  get sandboxMode(): SandboxMode | undefined {
    return this.#client.sandboxMode;
  }

  get networkAccess(): boolean | undefined {
    return this.#client.networkAccess;
  }

  get messages(): ConversationMessage[] {
    return [...this.#messages];
  }

  sandboxServiceUrl(pathname: string, websocket = false): string {
    if (this.#closed) throw new Error("session is closed");
    return sandboxServiceUrl(this.#sandboxUrl, pathname, websocket);
  }

  async connect(): Promise<string> {
    if (this.#closed) throw new Error("session is closed");
    await this.#client.connect();
    const snapshot = this.#resumeThreadId
      ? await this.#client.resumeThreadSnapshot(this.#resumeThreadId, this.#threadOptions)
      : await this.#client.startThreadSnapshot(this.#threadOptions);
    this.#setSnapshot(snapshot);
    this.emit({
      type: "ready",
      sessionId: this.id,
      threadId: snapshot.thread.id,
      messages: this.messages,
      ...(this.model ? { model: this.model } : {}),
      ...(this.cwd ? { cwd: this.cwd } : {}),
      ...this.#client.runtimeSettings(),
    });
    return snapshot.thread.id;
  }

  subscribe(subscriber: EventSubscriber, afterEventId = 0): () => void {
    for (const record of this.#eventHistory) {
      if (record.id <= afterEventId) continue;
      try {
        subscriber(record.event, record.id);
      } catch {
        return () => undefined;
      }
    }
    this.#subscribers.add(subscriber);
    return () => this.#subscribers.delete(subscriber);
  }

  async startTurn(text: string, skillIds: readonly string[] = []): Promise<string> {
    if (this.#closed) throw new Error("session is closed");
    if (!text.trim()) throw new TypeError("message must not be empty");
    if (this.#activeRequestId) throw new Error("a turn is already running");

    const requestId = randomUUID();
    this.#threadStarted = true;
    this.#activeRequestId = requestId;
    this.#activeTurnId = undefined;
    let skills: SkillInput[];
    try {
      skills = await this.#resolveSkills(text, skillIds);
    } catch (error) {
      this.#activeRequestId = undefined;
      throw error;
    }
    this.emit({ type: "turn_started", requestId });

    void this.#client
      .runTurn(
        text,
        (delta) => this.emit({ type: "delta", requestId, delta }),
        (turnId) => this.#setActiveTurnId(turnId),
        skills,
      )
      .then((result) => {
        this.emit({
          type: "turn_completed",
          requestId,
          turnId: result.turnId,
          status: result.status,
          text: result.text,
        });
      })
      .catch((error: unknown) => {
        if (!this.#closed) {
          this.emit({ type: "turn_error", requestId, message: this.safeError(error) });
        }
      })
      .finally(() => {
        this.#rejectTurnIdWaiters(new Error("the active turn ended before it could be interrupted"));
        this.#activeRequestId = undefined;
        this.#activeTurnId = undefined;
      });
    return requestId;
  }

  async interrupt(): Promise<void> {
    if (!this.#activeRequestId) throw new Error("there is no active turn");
    const turnId = this.#activeTurnId ?? (await this.#waitForTurnId());
    await this.#client.interruptTurn(turnId);
  }

  async newThread(): Promise<ThreadSnapshot> {
    if (this.active) throw new Error("cannot start a new thread while a turn is running");
    return this.#activateSnapshot(await this.#client.startThreadSnapshot(this.#threadOptions));
  }

  async listThreads(options: {
    cursor?: string;
    searchTerm?: string;
    archived?: boolean;
  } = {}): Promise<ThreadPage> {
    return this.#client.listThreads(options);
  }

  async switchThread(threadId: string): Promise<ThreadSnapshot> {
    if (this.active) throw new Error("cannot switch threads while a turn is running");
    const snapshot = await this.#client.resumeThreadSnapshot(threadId);
    return this.#activateSnapshot(snapshot);
  }

  async forkThread(): Promise<ThreadSnapshot> {
    if (this.active) throw new Error("cannot fork a thread while a turn is running");
    return this.#activateSnapshot(await this.#client.forkThread());
  }

  async archiveThread(threadId: string): Promise<ThreadSnapshot | undefined> {
    if (this.active) throw new Error("cannot archive a thread while a turn is running");
    await this.#client.archiveThread(threadId);
    if (threadId !== this.#threadId) return undefined;
    return this.#activateSnapshot(await this.#client.startThreadSnapshot(this.#threadOptions));
  }

  async compactThread(): Promise<void> {
    if (this.active) throw new Error("cannot compact a thread while a turn is running");
    await this.#client.compactThread();
  }

  async listModels(): Promise<ModelSummary[]> {
    const models: ModelSummary[] = [];
    let cursor: string | undefined;
    do {
      const page = await this.#client.listModels(cursor);
      models.push(...page.data);
      cursor = page.nextCursor;
    } while (cursor && models.length < 500);
    return models;
  }

  async listSkills(forceReload = false): Promise<SkillSummary[]> {
    if (this.#closed) throw new Error("session is closed");
    const cwd = this.cwd;
    if (!forceReload && this.#skillsLoaded && this.#skillsCwd === cwd) {
      return this.#publicSkills();
    }
    const skills = await this.#client.listSkills(forceReload);
    if (cwd !== this.cwd) return this.listSkills(forceReload);
    this.#replaceSkills(skills);
    this.#skillsCwd = cwd;
    this.#skillsLoaded = true;
    return this.#publicSkills();
  }

  async setModel(model: string): Promise<void> {
    if (this.active) throw new Error("cannot change model while a turn is running");
    await this.#client.setModel(model);
    this.#threadOptions = { ...this.#threadOptions, model };
  }

  async updateWorkspaceDirectory(cwd: string): Promise<{ cwd: string }> {
    if (this.workspaceLocked) {
      throw new Error("cannot change workspace after the thread has started");
    }
    const updated = await this.#client.updateThreadSettings({ cwd });
    this.#threadOptions = { ...this.#threadOptions, ...updated };
    return { cwd: updated.cwd ?? cwd };
  }

  async updateSessionPermissions(
    settings: SessionPermissionSettings,
  ): Promise<SessionPermissionSettings> {
    if (this.active) throw new Error("cannot change permissions while a turn is running");
    return this.#client.updateSessionPermissions(settings);
  }

  async listDirectories(path: string): Promise<DirectoryListing> {
    return this.#client.listDirectories(path);
  }

  resolveApproval(approvalId: string, decision: ApprovalDecision): void {
    const pending = this.#pendingApprovals.get(approvalId);
    if (!pending) throw new Error("approval request was not found or already resolved");
    clearTimeout(pending.timer);
    this.#pendingApprovals.delete(approvalId);
    pending.resolve(decision);
    this.emit({ type: "approval_resolved", approvalId });
  }

  close(): void {
    this.#finishClose(true);
  }

  #finishClose(closeClient: boolean, reason?: string): void {
    if (this.#closed) return;
    this.#closed = true;
    for (const [approvalId, pending] of this.#pendingApprovals) {
      clearTimeout(pending.timer);
      pending.resolve("decline");
      this.emit({ type: "approval_resolved", approvalId });
    }
    this.#pendingApprovals.clear();
    this.#rejectTurnIdWaiters(new Error(reason ?? "session is closed"));
    if (closeClient) this.#client.close();
    this.emit({ type: "closed", ...(reason ? { reason } : {}) });
    this.#subscribers.clear();
    this.#sandboxUrl = "";
    this.#resumeThreadId = undefined;
    this.#skillsById.clear();
    this.#skillsLoaded = false;
    this.#skillsCwd = undefined;
  }

  emit(event: BridgeEvent): void {
    const record = {
      id: this.#nextEventId++,
      event,
      bytes: Buffer.byteLength(JSON.stringify(event)),
    };
    if (record.bytes <= EVENT_HISTORY_BYTES_LIMIT) {
      this.#eventHistory.push(record);
      this.#eventHistoryBytes += record.bytes;
      while (
        this.#eventHistory.length > EVENT_HISTORY_LIMIT ||
        this.#eventHistoryBytes > EVENT_HISTORY_BYTES_LIMIT
      ) {
        const removed = this.#eventHistory.shift();
        if (removed) this.#eventHistoryBytes -= removed.bytes;
      }
    }
    for (const subscriber of this.#subscribers) {
      try {
        subscriber(event, record.id);
      } catch {
        this.#subscribers.delete(subscriber);
      }
    }
  }

  safeError(error: unknown): string {
    return redactSensitiveText(errorText(error), [this.#sandboxUrl, this.#client.websocketUrl]);
  }

  #requestApproval(request: ApprovalRequest): Promise<ApprovalDecision> {
    const approvalId = randomUUID();
    const params = request.params;
    const approval: BrowserApproval = {
      id: approvalId,
      kind: request.method === "item/commandExecution/requestApproval" ? "command" : "file",
      method: request.method,
      ...(typeof params.reason === "string" ? { reason: params.reason } : {}),
      ...(typeof params.command === "string" ? { command: params.command } : {}),
      ...(typeof params.cwd === "string" ? { cwd: params.cwd } : {}),
      ...(typeof params.grantRoot === "string" ? { grantRoot: params.grantRoot } : {}),
      ...(params.changes !== undefined ? { changes: params.changes } : {}),
      ...(typeof params.threadId === "string" ? { threadId: params.threadId } : {}),
      ...(typeof params.turnId === "string" ? { turnId: params.turnId } : {}),
      ...(typeof params.itemId === "string" ? { itemId: params.itemId } : {}),
      ...(typeof params.environmentId === "string" || params.environmentId === null
        ? { environmentId: params.environmentId }
        : {}),
      ...(typeof params.startedAtMs === "number" ? { startedAtMs: params.startedAtMs } : {}),
      ...(params.commandActions !== undefined ? { commandActions: params.commandActions } : {}),
      ...(params.networkApprovalContext !== undefined
        ? { networkApprovalContext: params.networkApprovalContext }
        : {}),
    };

    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.#pendingApprovals.delete(approvalId);
        resolve("decline");
        this.emit({ type: "approval_resolved", approvalId });
      }, APPROVAL_TIMEOUT_MS);
      this.#pendingApprovals.set(approvalId, { resolve, timer });
      this.emit({ type: "approval_requested", approval });
    });
  }

  #setActiveTurnId(turnId: string): void {
    this.#activeTurnId = turnId;
    if (this.#activeRequestId) this.#requestIdByTurnId.set(turnId, this.#activeRequestId);
    for (const waiter of this.#turnIdWaiters) {
      clearTimeout(waiter.timer);
      waiter.resolve(turnId);
    }
    this.#turnIdWaiters.clear();
  }

  #setSnapshot(snapshot: ThreadSnapshot): void {
    this.#threadId = snapshot.thread.id;
    this.#messages = [...snapshot.messages];
    this.#threadStarted = snapshot.messages.length > 0;
    if (snapshot.cwd) this.#threadOptions = { ...this.#threadOptions, cwd: snapshot.cwd };
    if (snapshot.model) this.#threadOptions = { ...this.#threadOptions, model: snapshot.model };
    this.#requestIdByTurnId.clear();
    this.#usageByTurnId.clear();
    this.#threadTokenTotal = undefined;
  }

  #emitTokenUsage(params: Record<string, unknown>): boolean {
    const update = tokenUsageUpdate(params);
    if (!update || update.threadId !== this.#threadId) return false;
    let requestId = this.#requestIdByTurnId.get(update.turnId);
    if (
      !requestId &&
      this.#activeRequestId &&
      (!this.#activeTurnId || this.#activeTurnId === update.turnId)
    ) {
      requestId = this.#activeRequestId;
      this.#setActiveTurnId(update.turnId);
    }
    if (!requestId) return false;

    const increment = this.#threadTokenTotal
      ? subtractUsage(update.total, this.#threadTokenTotal) ?? update.last
      : update.last;
    this.#threadTokenTotal = update.total;

    const current = this.#usageByTurnId.get(update.turnId) ?? emptyUsage();
    const usage = increment ? addUsage(current, increment) : current;
    this.#usageByTurnId.set(update.turnId, usage);
    this.emit({
      type: "token_usage",
      requestId,
      turnId: update.turnId,
      usage,
      threadTotal: update.total,
      modelContextWindow: update.modelContextWindow,
    });
    return true;
  }

  #emitExecutionUpdate(params: Record<string, unknown>, completed: boolean): boolean {
    const threadId = stringField(params, "threadId", "thread_id");
    const turnId = stringField(params, "turnId", "turn_id");
    const item = recordField(params, "item");
    if (!turnId || !item || (threadId && threadId !== this.#threadId)) return false;

    let requestId = this.#requestIdByTurnId.get(turnId);
    if (
      !requestId &&
      this.#activeRequestId &&
      (!this.#activeTurnId || this.#activeTurnId === turnId)
    ) {
      requestId = this.#activeRequestId;
      this.#setActiveTurnId(turnId);
    }
    if (!requestId) return false;

    const step = executionStep(item, completed);
    if (!step) return false;
    if (step.detail) {
      step.detail = redactSensitiveText(step.detail, [
        this.#sandboxUrl,
        this.#client.websocketUrl,
      ]);
    }
    this.emit({ type: "execution_update", requestId, turnId, step });
    return true;
  }

  #activateSnapshot(snapshot: ThreadSnapshot): ThreadSnapshot {
    this.#setSnapshot(snapshot);
    this.emit({
      type: "thread_changed",
      threadId: snapshot.thread.id,
      messages: snapshot.messages,
      ...(snapshot.model ? { model: snapshot.model } : {}),
      ...(snapshot.cwd ? { cwd: snapshot.cwd } : {}),
      ...runtimeSettings(snapshot),
    });
    return snapshot;
  }

  async #resolveSkills(text: string, skillIds: readonly string[]): Promise<SkillInput[]> {
    if (skillIds.length === 0) return [];
    await this.listSkills();
    const selectedByName = new Map<string, SkillInput>();
    for (const id of skillIds) {
      const skill = this.#skillsById.get(id);
      if (!skill) throw new SkillSelectionError("selected Skill is unavailable");
      const existing = selectedByName.get(skill.name);
      if (existing && existing.path !== skill.path) {
        throw new SkillSelectionError(
          `only one selected Skill may use the name $${skill.name}`,
        );
      }
      selectedByName.set(skill.name, { name: skill.name, path: skill.path });
    }
    const availableNames = new Set(
      [...this.#skillsById.values()].map((skill) => skill.name),
    );
    const leadingNames = leadingSkillNames(text, availableNames);
    if (leadingNames.length === 0) {
      throw new SkillSelectionError("selected Skill must be the first item in the prompt");
    }
    if (
      leadingNames.length !== selectedByName.size ||
      leadingNames.some((name) => !selectedByName.has(name))
    ) {
      throw new SkillSelectionError(
        "selected Skills must match the leading Skill markers in the prompt",
      );
    }
    return leadingNames.map((name) => selectedByName.get(name)!);
  }

  #replaceSkills(skills: readonly SkillMetadata[]): void {
    const previousIds = new Map(
      [...this.#skillsById.values()].map((skill) => [skill.path, skill.id]),
    );
    const next = new Map<string, BridgeSkill>();
    for (const skill of skills) {
      const entry: BridgeSkill = {
        id: previousIds.get(skill.path) ?? randomUUID(),
        name: skill.name,
        description: skill.description,
        path: skill.path,
      };
      next.set(entry.id, entry);
    }
    this.#skillsById = next;
  }

  #publicSkills(): SkillSummary[] {
    return [...this.#skillsById.values()].map(({ id, name, description }) => ({
      id,
      name,
      description,
    }));
  }

  #invalidateSkills(): void {
    this.#skillsLoaded = false;
  }

  #waitForTurnId(): Promise<string> {
    return new Promise((resolve, reject) => {
      const waiter: TurnIdWaiter = {
        resolve,
        reject,
        timer: setTimeout(() => {
          this.#turnIdWaiters.delete(waiter);
          reject(new Error("timed out waiting for the active turn to start"));
        }, 10_000),
      };
      this.#turnIdWaiters.add(waiter);
    });
  }

  #rejectTurnIdWaiters(error: Error): void {
    for (const waiter of this.#turnIdWaiters) {
      clearTimeout(waiter.timer);
      waiter.reject(error);
    }
    this.#turnIdWaiters.clear();
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function leadingSkillNames(
  text: string,
  availableNames: ReadonlySet<string>,
): string[] {
  let remaining = text;
  const names: string[] = [];
  while (remaining) {
    const name = leadingSkillName(remaining, availableNames);
    if (!name) break;
    if (!names.includes(name)) names.push(name);
    remaining = remaining.slice(name.length + 1);
    if (!/^\s/u.test(remaining)) break;
    remaining = remaining.trimStart();
  }
  return names;
}

function leadingSkillName(
  text: string,
  availableNames: ReadonlySet<string>,
): string | undefined {
  let matched: string | undefined;
  for (const name of availableNames) {
    const marker = `$${name}`;
    if (!text.startsWith(marker)) continue;
    const next = text.slice(marker.length, marker.length + 1);
    if (next && !/[\s)\]},.!?;:，。！？；：]/u.test(next)) continue;
    if (!matched || name.length > matched.length) matched = name;
  }
  return matched;
}

const TOKEN_USAGE_KEYS = [
  "totalTokens",
  "inputTokens",
  "cachedInputTokens",
  "outputTokens",
  "reasoningOutputTokens",
] as const;

function tokenUsageUpdate(params: Record<string, unknown>): {
  threadId: string;
  turnId: string;
  total: TokenUsageBreakdown;
  last: TokenUsageBreakdown;
  modelContextWindow: number | null;
} | undefined {
  const threadId = stringField(params, "threadId", "thread_id");
  const turnId = stringField(params, "turnId", "turn_id");
  const tokenUsage = recordField(params, "tokenUsage", "token_usage");
  if (!threadId || !turnId || !tokenUsage) return undefined;
  const total = usageBreakdown(recordField(tokenUsage, "total"));
  const last = usageBreakdown(recordField(tokenUsage, "last"));
  if (!total || !last) return undefined;
  const contextValue = numberField(tokenUsage, "modelContextWindow", "model_context_window");
  return {
    threadId,
    turnId,
    total,
    last,
    modelContextWindow: contextValue ?? null,
  };
}

function usageBreakdown(value: Record<string, unknown> | undefined): TokenUsageBreakdown | undefined {
  if (!value) return undefined;
  const totalTokens = numberField(value, "totalTokens", "total_tokens");
  if (totalTokens === undefined) return undefined;
  const inputTokens = numberField(value, "inputTokens", "input_tokens") ?? 0;
  const cachedInputTokens = numberField(value, "cachedInputTokens", "cached_input_tokens") ?? 0;
  const outputTokens = numberField(value, "outputTokens", "output_tokens") ?? 0;
  const reasoningOutputTokens = numberField(
    value,
    "reasoningOutputTokens",
    "reasoning_output_tokens",
  ) ?? 0;
  return { totalTokens, inputTokens, cachedInputTokens, outputTokens, reasoningOutputTokens };
}

function stringField(value: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    if (typeof value[key] === "string" && value[key]) return value[key];
  }
  return undefined;
}

function numberField(value: Record<string, unknown>, ...keys: string[]): number | undefined {
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === "number" && Number.isFinite(candidate) && candidate >= 0) {
      return Math.trunc(candidate);
    }
  }
  return undefined;
}

function recordField(
  value: Record<string, unknown>,
  ...keys: string[]
): Record<string, unknown> | undefined {
  for (const key of keys) {
    if (isRecord(value[key])) return value[key];
  }
  return undefined;
}

function executionStep(
  item: Record<string, unknown>,
  completed: boolean,
): ExecutionStep | undefined {
  const id = stringField(item, "id");
  const type = stringField(item, "type");
  if (!id || !type) return undefined;

  const status = completed
    ? executionStatus(stringField(item, "status"))
    : "running";
  const durationMs = numberField(item, "durationMs", "duration_ms");
  const common = {
    id,
    status,
    ...(durationMs === undefined ? {} : { durationMs }),
  };

  if (type === "reasoning") {
    return {
      ...common,
      kind: "reasoning",
      title: "思考",
      ...optionalDetail(stringList(item.summary).join("\n")),
    };
  }
  if (type === "agentMessage" && item.phase === "commentary") {
    return {
      ...common,
      kind: "reasoning",
      title: "Working",
      ...optionalDetail(stringField(item, "text")),
    };
  }
  if (type === "commandExecution") {
    const command = stringField(item, "command");
    const cwd = stringField(item, "cwd");
    const detail = [command ? `$ ${command}` : undefined, cwd ? `目录：${cwd}` : undefined]
      .filter((value): value is string => Boolean(value))
      .join("\n");
    return { ...common, kind: "command", title: "运行命令", ...optionalDetail(detail) };
  }
  if (type === "fileChange") {
    const changes = Array.isArray(item.changes) ? item.changes : [];
    const lines = changes.flatMap((change) => {
      if (!isRecord(change)) return [];
      const path = stringField(change, "path");
      if (!path) return [];
      return [`${fileChangeLabel(stringField(change, "kind"))} ${path}`];
    });
    return {
      ...common,
      kind: "file",
      title: lines.length > 1 ? `修改文件 · ${lines.length} 个` : "修改文件",
      ...optionalDetail(lines.join("\n")),
    };
  }
  if (type === "mcpToolCall") {
    const server = stringField(item, "server");
    const tool = stringField(item, "tool");
    const name = [server, tool].filter(Boolean).join("/");
    return {
      ...common,
      kind: "mcp",
      title: name ? `调用 MCP · ${name}` : "调用 MCP",
    };
  }
  if (type === "dynamicToolCall") {
    const namespace = stringField(item, "namespace");
    const tool = stringField(item, "tool");
    const name = [namespace, tool].filter(Boolean).join("/");
    return {
      ...common,
      kind: "dynamic",
      title: name ? `调用工具 · ${name}` : "调用工具",
    };
  }
  if (type === "collabToolCall" || type === "collabAgentToolCall") {
    const tool = stringField(item, "tool");
    return {
      ...common,
      kind: "collab",
      title: tool ? `协作代理 · ${tool}` : "协作代理",
    };
  }
  if (type === "subAgentActivity") {
    const kind = stringField(item, "kind");
    const path = stringField(item, "agentPath", "agent_path");
    return {
      ...common,
      kind: "collab",
      title: kind ? `代理活动 · ${kind}` : "代理活动",
      ...optionalDetail(path),
    };
  }
  if (type === "webSearch") {
    return {
      ...common,
      kind: "web",
      title: "网页搜索",
      ...optionalDetail(stringField(item, "query")),
    };
  }
  if (type === "imageView") {
    return {
      ...common,
      kind: "image",
      title: "查看图片",
      ...optionalDetail(stringField(item, "path")),
    };
  }
  if (type === "imageGeneration") {
    return { ...common, kind: "image", title: "生成图片" };
  }
  if (type === "plan") {
    return {
      ...common,
      kind: "plan",
      title: "更新计划",
      ...optionalDetail(stringField(item, "text")),
    };
  }
  if (type === "contextCompaction") {
    return { ...common, kind: "context", title: "压缩上下文" };
  }
  if (type === "enteredReviewMode") {
    return { ...common, kind: "other", title: "进入代码审查" };
  }
  if (type === "exitedReviewMode") {
    return { ...common, kind: "other", title: "完成代码审查" };
  }
  if (type === "sleep") {
    const waitMs = numberField(item, "durationMs", "duration_ms");
    return {
      ...common,
      kind: "other",
      title: "等待",
      ...optionalDetail(waitMs === undefined ? undefined : formatDuration(waitMs)),
    };
  }
  return undefined;
}

function executionStatus(status: string | undefined): ExecutionStep["status"] {
  return status === "failed" || status === "declined" || status === "cancelled"
    ? "failed"
    : "completed";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string" && Boolean(entry.trim()));
}

function optionalDetail(value: string | undefined): { detail?: string } {
  if (!value?.trim()) return {};
  const maximum = 4_000;
  const trimmed = value.trim();
  return { detail: trimmed.length > maximum ? `${trimmed.slice(0, maximum)}\n…` : trimmed };
}

function fileChangeLabel(kind: string | undefined): string {
  return {
    add: "新增",
    delete: "删除",
    update: "更新",
    move: "移动",
  }[kind ?? ""] ?? "修改";
}

function formatDuration(durationMs: number): string {
  if (durationMs < 1_000) return `${durationMs} ms`;
  return `${(durationMs / 1_000).toFixed(durationMs < 10_000 ? 1 : 0)} s`;
}

function emptyUsage(): TokenUsageBreakdown {
  return {
    totalTokens: 0,
    inputTokens: 0,
    cachedInputTokens: 0,
    outputTokens: 0,
    reasoningOutputTokens: 0,
  };
}

function runtimeSettings(value: ThreadRuntimeSettings): ThreadRuntimeSettings {
  return {
    ...(value.approvalPolicy ? { approvalPolicy: value.approvalPolicy } : {}),
    ...(value.approvalsReviewer
      ? { approvalsReviewer: value.approvalsReviewer }
      : {}),
    ...(value.sandboxMode ? { sandboxMode: value.sandboxMode } : {}),
    ...(value.networkAccess !== undefined
      ? { networkAccess: value.networkAccess }
      : {}),
  };
}

function addUsage(left: TokenUsageBreakdown, right: TokenUsageBreakdown): TokenUsageBreakdown {
  return {
    totalTokens: left.totalTokens + right.totalTokens,
    inputTokens: left.inputTokens + right.inputTokens,
    cachedInputTokens: left.cachedInputTokens + right.cachedInputTokens,
    outputTokens: left.outputTokens + right.outputTokens,
    reasoningOutputTokens: left.reasoningOutputTokens + right.reasoningOutputTokens,
  };
}

function subtractUsage(
  current: TokenUsageBreakdown,
  previous: TokenUsageBreakdown,
): TokenUsageBreakdown | undefined {
  if (TOKEN_USAGE_KEYS.some((key) => current[key] < previous[key])) return undefined;
  return {
    totalTokens: current.totalTokens - previous.totalTokens,
    inputTokens: current.inputTokens - previous.inputTokens,
    cachedInputTokens: current.cachedInputTokens - previous.cachedInputTokens,
    outputTokens: current.outputTokens - previous.outputTokens,
    reasoningOutputTokens: current.reasoningOutputTokens - previous.reasoningOutputTokens,
  };
}
