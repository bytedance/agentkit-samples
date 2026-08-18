import type { AgentkitRuntimeType } from "../../src/runtime.ts";

export type {
  AgentkitRuntimeType,
  RuntimeWorkspace,
} from "../../src/runtime.ts";

export type ApprovalPolicy = "untrusted" | "on-request" | "never";
export type ApprovalsReviewer = "user" | "auto_review";
export type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";

export interface ThreadRuntimeSettings {
  approvalPolicy?: ApprovalPolicy;
  approvalsReviewer?: ApprovalsReviewer;
  sandboxMode?: SandboxMode;
  networkAccess?: boolean;
}

export interface PermissionSettings {
  approvalPolicy: ApprovalPolicy;
  approvalsReviewer: ApprovalsReviewer;
  sandboxMode: SandboxMode;
  networkAccess: boolean;
}

export interface WorkspaceSettings {
  cwd: string;
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

export interface ConnectedSession extends ThreadRuntimeSettings {
  id: string;
  threadId: string;
  endpoint: string;
  messages?: HistoryMessage[];
  model?: string;
  cwd?: string;
  agentkitSession?: AgentkitSession;
}

export interface ConnectInput {
  agentkitToolId?: string;
  agentkitSessionId?: string;
  sandboxUrl?: string;
  cwd?: string;
  model?: string;
  threadId?: string;
}

export interface AgentkitConfig {
  configured: boolean;
  region?: string;
  consoleLogin?: boolean;
  privateType?: AgentkitRuntimeType;
  recentToolsScope?: string;
}

export interface AgentkitTool {
  toolId: string;
  name?: string;
  description?: string;
  status: string;
  toolType?: string;
  projectName?: string;
  createdAt?: string;
  updatedAt?: string;
  enableSnapshot?: boolean;
}

export interface AgentkitSession {
  sessionId: string;
  toolId?: string;
  userSessionId?: string;
  status: string;
  toolType?: string;
  createdAt?: string;
  expireAt?: string;
  endpoint?: string;
}

export interface AgentkitSessionSnapshot {
  snapshotId: string;
  toolId?: string;
  sessionId?: string;
  userSessionId?: string;
  status?: string;
  reason?: string;
  createdAt?: string;
}

export type ApprovalDecision = "accept" | "acceptForSession" | "decline" | "cancel";

export interface BrowserApproval {
  id: string;
  kind: "command" | "file";
  method: string;
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

export type BridgeEvent =
  | {
      type: "ready";
      sessionId: string;
      threadId: string;
      messages: HistoryMessage[];
      model?: string;
      cwd?: string;
    } & ThreadRuntimeSettings
  | {
      type: "thread_changed";
      threadId: string;
      messages: HistoryMessage[];
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

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  state: "complete" | "streaming" | "error";
  timestamp: number;
  skillNames?: string[];
  turnId?: string;
  tokenUsage?: MessageTokenUsage;
  execution?: ExecutionStep[];
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

export interface TokenUsageBreakdown {
  totalTokens: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  reasoningOutputTokens: number;
}

export interface MessageTokenUsage {
  turn: TokenUsageBreakdown;
  threadTotal: TokenUsageBreakdown;
  modelContextWindow: number | null;
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  skillNames?: string[];
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
  threadId: string;
  thread: ThreadSummary;
  messages: HistoryMessage[];
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

export interface SkillSummary {
  id: string;
  name: string;
  description: string;
}

export interface SessionStatus extends ThreadRuntimeSettings {
  threadId: string;
  endpoint: string;
  model?: string;
  cwd?: string;
  active: boolean;
  agentkitSession?: AgentkitSession;
}
