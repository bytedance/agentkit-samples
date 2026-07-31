import { isRecord } from "./protocol.ts";

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  skillNames?: string[];
}

export type ApprovalPolicy = "untrusted" | "on-request" | "never";
export type ApprovalsReviewer = "user" | "auto_review";
export type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";

export interface ThreadRuntimeSettings {
  approvalPolicy?: ApprovalPolicy;
  approvalsReviewer?: ApprovalsReviewer;
  sandboxMode?: SandboxMode;
  networkAccess?: boolean;
}

export interface SessionPermissionSettings {
  approvalPolicy: ApprovalPolicy;
  approvalsReviewer: ApprovalsReviewer;
  sandboxMode: SandboxMode;
  networkAccess: boolean;
}

export interface ThreadSummary {
  id: string;
  name?: string;
  preview: string;
  cwd: string;
  modelProvider: string;
  createdAt: number;
  updatedAt: number;
  status: string;
}

export interface ThreadSnapshot extends ThreadRuntimeSettings {
  thread: ThreadSummary;
  messages: ConversationMessage[];
  model?: string;
  cwd?: string;
}

export interface ThreadPage {
  data: ThreadSummary[];
  nextCursor?: string;
}

export interface ModelSummary {
  id: string;
  displayName: string;
  description: string;
  isDefault: boolean;
}

export interface ModelPage {
  data: ModelSummary[];
  nextCursor?: string;
}

export interface SkillMetadata {
  name: string;
  description: string;
  path: string;
}

export function threadSnapshotFromResult(
  method: string,
  result: Record<string, unknown>,
): ThreadSnapshot {
  const thread = result.thread;
  if (!isRecord(thread)) {
    throw new TypeError(`${method} response did not contain a thread`);
  }
  const summary = threadSummaryFromValue(thread);
  const messages = messagesFromTurns(thread.turns, summary.updatedAt);
  return {
    thread: summary,
    messages,
    ...(typeof result.model === "string" ? { model: result.model } : {}),
    ...(typeof result.cwd === "string" ? { cwd: result.cwd } : {}),
    ...runtimeSettingsFromValue(result),
  };
}

export function runtimeSettingsFromValue(
  value: Record<string, unknown>,
): ThreadRuntimeSettings {
  const approvalPolicy = approvalPolicyFromValue(value.approvalPolicy);
  const approvalsReviewer = approvalsReviewerFromValue(value.approvalsReviewer);
  const sandbox = value.sandbox ?? value.sandboxPolicy;
  const sandboxSettings = sandboxSettingsFromValue(sandbox);
  return {
    ...(approvalPolicy ? { approvalPolicy } : {}),
    ...(approvalsReviewer ? { approvalsReviewer } : {}),
    ...sandboxSettings,
  };
}

export function threadPageFromResult(result: Record<string, unknown>): ThreadPage {
  if (!Array.isArray(result.data)) {
    throw new TypeError("thread/list response did not contain data");
  }
  const data = result.data.flatMap((value) => {
    try {
      return [threadSummaryFromValue(value)];
    } catch {
      return [];
    }
  });
  return {
    data,
    ...(typeof result.nextCursor === "string" ? { nextCursor: result.nextCursor } : {}),
  };
}

export function modelPageFromResult(result: Record<string, unknown>): ModelPage {
  if (!Array.isArray(result.data)) {
    throw new TypeError("model/list response did not contain data");
  }
  const data = result.data.flatMap((value) => {
    if (!isRecord(value)) return [];
    const id = typeof value.model === "string" ? value.model : value.id;
    if (typeof id !== "string") return [];
    return [{
      id,
      displayName: typeof value.displayName === "string" ? value.displayName : id,
      description: typeof value.description === "string" ? value.description : "",
      isDefault: value.isDefault === true,
    }];
  });
  return {
    data,
    ...(typeof result.nextCursor === "string" ? { nextCursor: result.nextCursor } : {}),
  };
}

export function skillsFromResult(
  result: Record<string, unknown>,
  cwd?: string,
): SkillMetadata[] {
  if (!Array.isArray(result.data)) {
    throw new TypeError("skills/list response did not contain data");
  }
  const skills = new Map<string, SkillMetadata>();
  for (const entry of result.data) {
    if (
      !isRecord(entry) ||
      !Array.isArray(entry.skills) ||
      (cwd !== undefined && entry.cwd !== cwd)
    ) {
      continue;
    }
    for (const value of entry.skills) {
      if (
        !isRecord(value) ||
        value.enabled !== true ||
        typeof value.name !== "string" ||
        !value.name.trim() ||
        typeof value.path !== "string" ||
        !value.path
      ) {
        continue;
      }
      skills.set(value.path, {
        name: value.name,
        description: typeof value.description === "string"
          ? value.description.slice(0, 1_000)
          : "",
        path: value.path,
      });
      if (skills.size >= 500) return [...skills.values()];
    }
  }
  return [...skills.values()];
}

function threadSummaryFromValue(value: unknown): ThreadSummary {
  if (!isRecord(value) || typeof value.id !== "string") {
    throw new TypeError("thread entry did not contain an id");
  }
  const createdAt = finiteNumber(value.createdAt) ?? 0;
  const updatedAt = finiteNumber(value.updatedAt) ?? createdAt;
  return {
    id: value.id,
    ...(typeof value.name === "string" && value.name ? { name: value.name } : {}),
    preview: typeof value.preview === "string" ? value.preview : "",
    cwd: typeof value.cwd === "string" ? value.cwd : "",
    modelProvider: typeof value.modelProvider === "string" ? value.modelProvider : "",
    createdAt,
    updatedAt,
    status: threadStatus(value.status),
  };
}

function approvalPolicyFromValue(value: unknown): ApprovalPolicy | undefined {
  return value === "untrusted" || value === "on-request" || value === "never"
    ? value
    : undefined;
}

function approvalsReviewerFromValue(value: unknown): ApprovalsReviewer | undefined {
  return value === "user" || value === "auto_review" ? value : undefined;
}

function sandboxSettingsFromValue(value: unknown): ThreadRuntimeSettings {
  if (typeof value === "string") {
    return isSandboxMode(value) ? { sandboxMode: value } : {};
  }
  if (!isRecord(value) || typeof value.type !== "string") return {};
  if (value.type === "dangerFullAccess") {
    return { sandboxMode: "danger-full-access", networkAccess: true };
  }
  if (value.type === "readOnly") {
    return {
      sandboxMode: "read-only",
      ...(typeof value.networkAccess === "boolean"
        ? { networkAccess: value.networkAccess }
        : {}),
    };
  }
  if (value.type === "workspaceWrite") {
    return {
      sandboxMode: "workspace-write",
      ...(typeof value.networkAccess === "boolean"
        ? { networkAccess: value.networkAccess }
        : {}),
    };
  }
  return {};
}

function isSandboxMode(value: string): value is SandboxMode {
  return value === "read-only" ||
    value === "workspace-write" ||
    value === "danger-full-access";
}

function messagesFromTurns(value: unknown, fallbackSeconds: number): ConversationMessage[] {
  if (!Array.isArray(value)) return [];
  const messages: ConversationMessage[] = [];
  let sequence = 0;
  for (const turn of value) {
    if (!isRecord(turn) || !Array.isArray(turn.items)) continue;
    const turnTimestamp = (finiteNumber(turn.startedAt) ?? fallbackSeconds) * 1_000;
    for (const item of turn.items) {
      if (!isRecord(item) || typeof item.id !== "string") continue;
      let role: ConversationMessage["role"] | undefined;
      let content = "";
      let skillNames: string[] = [];
      if (item.type === "userMessage") {
        role = "user";
        const display = userMessageDisplay(item.content);
        content = display.content;
        skillNames = display.skillNames;
      } else if (item.type === "agentMessage" && typeof item.text === "string") {
        role = "assistant";
        content = item.text;
      }
      if (!role || (!content && skillNames.length === 0)) continue;
      messages.push({
        id: item.id,
        role,
        content,
        timestamp: turnTimestamp + sequence,
        ...(skillNames.length > 0 ? { skillNames } : {}),
      });
      sequence += 1;
    }
  }
  return messages;
}

function userMessageDisplay(value: unknown): {
  content: string;
  skillNames: string[];
} {
  if (!Array.isArray(value)) return { content: "", skillNames: [] };
  const skillNames = value.flatMap((part) =>
    isRecord(part) && part.type === "skill" && typeof part.name === "string"
      ? [part.name]
      : []);
  const visible = value.flatMap((part) => {
    if (!isRecord(part)) return [];
    if (part.type === "text" && typeof part.text === "string") return [part.text];
    if (part.type === "localImage" && typeof part.path === "string") {
      return [`[本地图片: ${part.path}]`];
    }
    if (part.type === "image") return ["[图片]"];
    return [];
  });
  if (visible.length > 0) {
    return skillDisplayParts(visible.join("\n"), skillNames);
  }
  return {
    content: value.flatMap((part) => {
      if (!isRecord(part)) return [];
      if (part.type === "mention" && typeof part.name === "string") return [`@${part.name}`];
      return [];
    }).join("\n"),
    skillNames: [...new Set(skillNames)],
  };
}

function skillDisplayParts(
  value: string,
  skillNames: readonly string[],
): { content: string; skillNames: string[] } {
  let content = value;
  const names = new Set(skillNames);
  const leadingSkillNames: string[] = [];
  while (content) {
    const name = leadingSkillName(content, names);
    if (!name) break;
    content = content.slice(name.length + 1);
    if (!leadingSkillNames.includes(name)) leadingSkillNames.push(name);
    if (!/^\s/u.test(content)) break;
    content = content.trimStart();
  }
  return {
    content,
    skillNames: leadingSkillNames,
  };
}

function leadingSkillName(
  value: string,
  allowedNames: ReadonlySet<string>,
): string | undefined {
  let matched: string | undefined;
  for (const name of allowedNames) {
    const marker = `$${name}`;
    if (!value.startsWith(marker)) continue;
    const next = value.slice(marker.length, marker.length + 1);
    if (next && !/[\s)\]},.!?;:，。！？；：]/u.test(next)) continue;
    if (!matched || name.length > matched.length) matched = name;
  }
  return matched;
}

function threadStatus(value: unknown): string {
  if (typeof value === "string") return value;
  if (isRecord(value) && typeof value.type === "string") return value.type;
  return "unknown";
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
