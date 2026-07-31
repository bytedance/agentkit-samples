import type {
  ApprovalDecision,
  AgentkitConfig,
  AgentkitSession,
  AgentkitTool,
  ConnectedSession,
  ConnectInput,
  DirectoryListing,
  ModelSummary,
  PermissionSettings,
  SessionStatus,
  SkillSummary,
  ThreadPage,
  ThreadSnapshot,
  WorkspaceSettings,
} from "./types";

interface ApiErrorBody {
  error?: string;
}

let capabilityRequest: Promise<void> | undefined;

async function ensureCapability(): Promise<void> {
  capabilityRequest ??= fetch("/api/capability", { cache: "no-store" }).then((response) => {
    if (!response.ok) throw new Error(`无法初始化本地 bridge (${response.status})`);
  });
  try {
    await capabilityRequest;
  } catch (error) {
    capabilityRequest = undefined;
    throw error;
  }
}

async function api<T>(path: string, init?: RequestInit, canRetry = true): Promise<T> {
  await ensureCapability();
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "content-type": "application/json" }
        : {}),
      ...init?.headers,
    },
  });
  if (response.status === 401 && canRetry) {
    capabilityRequest = undefined;
    return api(path, init, false);
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body.error) detail = body.error;
    } catch {
      // Keep the HTTP status fallback.
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getAgentkitConfig(): Promise<AgentkitConfig> {
  return api("/api/agentkit/config");
}

export function startConsoleLogin(region?: string): Promise<{
  id: string;
  authorizationUrl: string;
}> {
  return api("/api/auth/start", { method: "POST", body: JSON.stringify({ region }) });
}

export function completeRemoteConsoleLogin(id: string, authorizationResponse: string): Promise<{ ok: true }> {
  return api(`/api/auth/${encodeURIComponent(id)}/remote`, {
    method: "POST", body: JSON.stringify({ authorizationResponse }),
  });
}

export function logoutConsoleLogin(): Promise<{ ok: true; loggedOut: boolean }> {
  return api("/api/auth/logout", { method: "POST" });
}

export function listAgentkitTools(options: {
  maxResults?: number;
  nextToken?: string;
  search?: string;
} = {}): Promise<{ data: AgentkitTool[]; nextToken?: string }> {
  const query = new URLSearchParams();
  query.set("maxResults", String(options.maxResults ?? 10));
  if (options.nextToken) query.set("nextToken", options.nextToken);
  if (options.search) query.set("search", options.search);
  return api(`/api/agentkit/tools?${query}`);
}

export function listAgentkitSessions(toolId: string): Promise<{ data: AgentkitSession[] }> {
  return api(`/api/agentkit/tools/${encodeURIComponent(toolId)}/sessions`);
}

export function getAgentkitSession(toolId: string, sessionId: string): Promise<AgentkitSession> {
  return api(`/api/agentkit/tools/${encodeURIComponent(toolId)}/sessions/${encodeURIComponent(sessionId)}`);
}

export function createAgentkitSession(toolId: string, input: {
  userSessionId?: string;
  ttl?: number;
}): Promise<AgentkitSession> {
  return api(`/api/agentkit/tools/${encodeURIComponent(toolId)}/sessions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function launchAgentkitWorkspace(
  toolId: string,
  sessionId: string,
): Promise<{ url: string }> {
  return api(`/api/agentkit/tools/${encodeURIComponent(toolId)}/sessions/${encodeURIComponent(sessionId)}/workspace`, {
    method: "POST",
  });
}

export function connectSession(input: ConnectInput): Promise<ConnectedSession> {
  return api("/api/sessions", { method: "POST", body: JSON.stringify(input) });
}

export function sendTurn(
  sessionId: string,
  text: string,
  skillIds: readonly string[] = [],
): Promise<{ requestId: string }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/turns`, {
    method: "POST",
    body: JSON.stringify({
      text,
      ...(skillIds.length > 0 ? { skillIds } : {}),
    }),
  });
}

export function interruptTurn(sessionId: string): Promise<{ ok: true }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/interrupt`, {
    method: "POST",
  });
}

export function newThread(sessionId: string): Promise<ThreadSnapshot> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads`, {
    method: "POST",
  });
}

export function listThreads(
  sessionId: string,
  options: { cursor?: string; search?: string } = {},
): Promise<ThreadPage> {
  const query = new URLSearchParams();
  if (options.cursor) query.set("cursor", options.cursor);
  if (options.search) query.set("search", options.search);
  const suffix = query.size ? `?${query}` : "";
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads${suffix}`);
}

export function resumeThread(sessionId: string, threadId: string): Promise<ThreadSnapshot> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads/resume`, {
    method: "POST",
    body: JSON.stringify({ threadId }),
  });
}

export function forkThread(sessionId: string): Promise<ThreadSnapshot> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads/fork`, {
    method: "POST",
  });
}

export function archiveThread(
  sessionId: string,
  threadId: string,
): Promise<{ archived: true } & Partial<ThreadSnapshot>> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads/archive`, {
    method: "POST",
    body: JSON.stringify({ threadId }),
  });
}

export function compactThread(sessionId: string): Promise<{ ok: true }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/threads/compact`, {
    method: "POST",
  });
}

export function listModels(sessionId: string): Promise<{ data: ModelSummary[] }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/models`);
}

export function listSkills(sessionId: string): Promise<{ data: SkillSummary[] }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/skills`);
}

export function selectModel(sessionId: string, model: string): Promise<{ model: string }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/models`, {
    method: "POST",
    body: JSON.stringify({ model }),
  });
}

export function listSandboxDirectories(
  sessionId: string,
  path: string,
): Promise<DirectoryListing> {
  const query = new URLSearchParams({ path });
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/directories?${query}`);
}

export function updateSessionPermissions(
  sessionId: string,
  settings: PermissionSettings,
): Promise<PermissionSettings> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/permissions`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export function updateWorkspaceSettings(
  sessionId: string,
  settings: WorkspaceSettings,
): Promise<WorkspaceSettings> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/workspace`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export function uploadSandboxFile(
  sessionId: string,
  file: File,
  path: string,
): Promise<{ ok: true }> {
  const form = new FormData();
  form.set("path", path);
  form.set("file", file, file.name);
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/files/upload`, {
    method: "POST",
    body: form,
  });
}

export function getSessionStatus(sessionId: string): Promise<SessionStatus> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/status`);
}

export function getSandboxBrowserUrl(sessionId: string): Promise<{ url: string }> {
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/browser`);
}

export function getSandboxTerminalUrl(
  sessionId: string,
  shellSessionId?: string,
): Promise<{ url: string; shellSessionId: string }> {
  const query = new URLSearchParams();
  if (shellSessionId) query.set("shellSessionId", shellSessionId);
  const suffix = query.size ? `?${query}` : "";
  return api(`/api/sessions/${encodeURIComponent(sessionId)}/terminal${suffix}`);
}

export function answerApproval(
  sessionId: string,
  approvalId: string,
  decision: ApprovalDecision,
): Promise<{ ok: true }> {
  return api(
    `/api/sessions/${encodeURIComponent(sessionId)}/approvals/${encodeURIComponent(approvalId)}`,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
}

export function closeSession(sessionId: string, keepalive = false): Promise<void> {
  const path = `/api/sessions/${encodeURIComponent(sessionId)}`;
  if (keepalive) {
    return fetch(path, { method: "DELETE", keepalive }).then((response) => {
      if (!response.ok && response.status !== 404) {
        throw new Error(`关闭 session 失败 (${response.status})`);
      }
    });
  }
  return api(path, { method: "DELETE" });
}
