export const AGENTKIT_RUNTIME_TYPES = [
  "CodeEnv",
  "HermesEnv",
  "ArkClawEnv",
] as const;

export type AgentkitRuntimeType = (typeof AGENTKIT_RUNTIME_TYPES)[number];
export type RuntimeWorkspace = "Codex" | "Hermes" | "OpenClaw";
export type ExternalWorkspaceType = Exclude<RuntimeWorkspace, "Codex">;

const RUNTIME_WORKSPACES: Record<AgentkitRuntimeType, RuntimeWorkspace> = {
  CodeEnv: "Codex",
  HermesEnv: "Hermes",
  ArkClawEnv: "OpenClaw",
};

export function parsePrivateRuntimeType(
  value: string | undefined,
): AgentkitRuntimeType | undefined {
  const normalized = value?.trim();
  return isAgentkitRuntimeType(normalized) ? normalized : undefined;
}

export function runtimeWorkspaceForToolType(
  toolType: string | undefined,
  privateRuntimeType?: AgentkitRuntimeType,
): RuntimeWorkspace | undefined {
  const normalized = toolType?.trim();
  const runtimeType = normalized === "Private" ? privateRuntimeType : normalized;
  return isAgentkitRuntimeType(runtimeType) ? RUNTIME_WORKSPACES[runtimeType] : undefined;
}

function isAgentkitRuntimeType(
  value: string | undefined,
): value is AgentkitRuntimeType {
  return (AGENTKIT_RUNTIME_TYPES as readonly string[]).includes(value ?? "");
}
