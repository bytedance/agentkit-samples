import type { AgentkitTool } from "./types.ts";

const LEGACY_RECENT_TOOLS_KEY = "situla-recent-tools-v1";
const RECENT_TOOLS_KEY_PREFIX = "situla-recent-tools-v2:";
const MAX_RECENT_TOOLS = 3;

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

export function readRecentTools(storage: StorageLike, scope: string | undefined): AgentkitTool[] {
  discardLegacyRecentTools(storage);
  const key = recentToolsKey(scope);
  if (!key) return [];
  try {
    const value: unknown = JSON.parse(storage.getItem(key) ?? "[]");
    if (!Array.isArray(value)) return [];
    const tools = new Map<string, AgentkitTool>();
    for (const item of value) {
      const tool = parseRecentTool(item);
      if (tool) tools.set(tool.toolId, tool);
      if (tools.size >= MAX_RECENT_TOOLS) break;
    }
    return [...tools.values()];
  } catch {
    return [];
  }
}

export function writeRecentTools(
  storage: StorageLike,
  scope: string | undefined,
  tools: AgentkitTool[],
): void {
  const key = recentToolsKey(scope);
  if (!key) return;
  try {
    storage.setItem(
      key,
      JSON.stringify(tools.slice(0, MAX_RECENT_TOOLS).map(publicToolFields)),
    );
  } catch {
    // Recent Tools are a convenience; unavailable storage must not block Tool selection.
  }
}

export function enqueueRecentTool(
  current: AgentkitTool[],
  tool: AgentkitTool,
): AgentkitTool[] {
  return [
    publicToolFields(tool),
    ...current.filter((item) => item.toolId !== tool.toolId),
  ].slice(0, MAX_RECENT_TOOLS);
}

export function rememberRecentTool(
  storage: StorageLike,
  scope: string | undefined,
  tool: AgentkitTool,
): AgentkitTool[] {
  const updated = enqueueRecentTool(readRecentTools(storage, scope), tool);
  writeRecentTools(storage, scope, updated);
  return updated;
}

export function refreshRecentTools(
  current: AgentkitTool[],
  fresh: AgentkitTool[],
): AgentkitTool[] {
  const byId = new Map(fresh.map((tool) => [tool.toolId, tool]));
  return current.map((tool) => byId.get(tool.toolId) ?? tool);
}

function parseRecentTool(value: unknown): AgentkitTool | undefined {
  if (!isRecord(value) || typeof value.toolId !== "string" || !value.toolId.trim()) {
    return undefined;
  }
  return publicToolFields({
    toolId: value.toolId,
    status: stringField(value.status) ?? "Unknown",
    ...(stringField(value.name) ? { name: stringField(value.name) } : {}),
    ...(stringField(value.description) ? { description: stringField(value.description) } : {}),
    ...(stringField(value.toolType) ? { toolType: stringField(value.toolType) } : {}),
    ...(stringField(value.projectName) ? { projectName: stringField(value.projectName) } : {}),
    ...(stringField(value.createdAt) ? { createdAt: stringField(value.createdAt) } : {}),
    ...(stringField(value.updatedAt) ? { updatedAt: stringField(value.updatedAt) } : {}),
    ...(typeof value.enableSnapshot === "boolean"
      ? { enableSnapshot: value.enableSnapshot }
      : {}),
  });
}

function recentToolsKey(scope: string | undefined): string | undefined {
  const normalized = scope?.trim();
  return normalized ? `${RECENT_TOOLS_KEY_PREFIX}${normalized}` : undefined;
}

function discardLegacyRecentTools(storage: StorageLike): void {
  try {
    storage.removeItem?.(LEGACY_RECENT_TOOLS_KEY);
  } catch {
    // Legacy cleanup is best-effort and must not block the current account.
  }
}

function publicToolFields(tool: AgentkitTool): AgentkitTool {
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

function stringField(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
