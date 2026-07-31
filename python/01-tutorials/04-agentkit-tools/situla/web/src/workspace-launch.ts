import type { AgentkitSession, AgentkitTool } from "./types";

export interface CodexWorkspaceLaunch {
  toolId: string;
  toolName?: string;
  toolType?: string;
  sessionId: string;
}

export const CODEX_WORKSPACE_PATH = "/codex";
export const CODEX_LAUNCH_STORAGE_KEY = "situla-codex-workspace-v1";

export function readCodexLaunch(): CodexWorkspaceLaunch | undefined {
  if (currentPath() !== CODEX_WORKSPACE_PATH) return undefined;
  const query = new URLSearchParams(window.location.search);
  const toolId = query.get("toolId")?.trim();
  const sessionId = query.get("sessionId")?.trim();
  if (toolId && sessionId) {
    const launch: CodexWorkspaceLaunch = {
      toolId,
      sessionId,
      ...(query.get("toolName")?.trim() ? { toolName: query.get("toolName")!.trim() } : {}),
      ...(query.get("toolType")?.trim() ? { toolType: query.get("toolType")!.trim() } : {}),
    };
    window.sessionStorage.setItem(CODEX_LAUNCH_STORAGE_KEY, JSON.stringify(launch));
    window.history.replaceState(null, "", CODEX_WORKSPACE_PATH);
    return launch;
  }
  try {
    const stored = JSON.parse(
      window.sessionStorage.getItem(CODEX_LAUNCH_STORAGE_KEY) ?? "null",
    ) as Partial<CodexWorkspaceLaunch> | null;
    if (!stored || typeof stored.toolId !== "string" || typeof stored.sessionId !== "string") {
      return undefined;
    }
    return {
      toolId: stored.toolId,
      sessionId: stored.sessionId,
      ...(typeof stored.toolName === "string" ? { toolName: stored.toolName } : {}),
      ...(typeof stored.toolType === "string" ? { toolType: stored.toolType } : {}),
    };
  } catch {
    return undefined;
  }
}

export function openCodexWorkspace(tool: AgentkitTool, session: AgentkitSession): void {
  const url = new URL(CODEX_WORKSPACE_PATH, window.location.origin);
  url.searchParams.set("toolId", tool.toolId);
  url.searchParams.set("sessionId", session.sessionId);
  if (tool.name) url.searchParams.set("toolName", tool.name);
  if (tool.toolType) url.searchParams.set("toolType", tool.toolType);
  const opened = window.open(url, "_blank");
  opened?.focus();
}

function currentPath(): string {
  const normalized = window.location.pathname.replace(/\/+$/, "");
  return normalized || "/";
}
