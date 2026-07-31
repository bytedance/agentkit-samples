import { useCallback, useEffect, useState, type ReactNode } from "react";
import { runtimeWorkspaceForToolType } from "../../src/runtime.ts";
import {
  createAgentkitSession,
  getAgentkitConfig,
  launchAgentkitWorkspace,
  listAgentkitSessions,
  logoutConsoleLogin,
} from "./api";
import { ConsoleLogin } from "./components/ConsoleLogin";
import { SessionAdmin } from "./components/SessionAdmin";
import { ToolAdmin } from "./components/ToolAdmin";
import { CreateInstanceDialog } from "./components/dialogs/CreateInstanceDialog";
import { messageOf } from "./display";
import { useTheme } from "./hooks/useTheme";
import { rememberRecentTool } from "./tool-recents";
import type { AgentkitConfig, AgentkitSession, AgentkitTool } from "./types";
import { openCodexWorkspace } from "./workspace-launch";

const DEFAULT_CONFIG: AgentkitConfig = { configured: false };

export function AdminApp(): ReactNode {
  const { theme, toggleTheme } = useTheme();
  const [config, setConfig] = useState<AgentkitConfig>(DEFAULT_CONFIG);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string>();
  const [selectedTool, setSelectedTool] = useState<AgentkitTool>();
  const [sessions, setSessions] = useState<AgentkitSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string>();
  const [showCreateInstance, setShowCreateInstance] = useState(false);

  const refreshConfig = useCallback(async () => {
    setConfigLoading(true);
    setConfigError(undefined);
    try {
      setConfig(await getAgentkitConfig());
    } catch (error) {
      setConfig(DEFAULT_CONFIG);
      setConfigError(messageOf(error));
    } finally {
      setConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshConfig();
  }, [refreshConfig]);

  const refreshSessions = useCallback(async () => {
    if (!selectedTool) {
      setSessions([]);
      setSessionsLoading(false);
      return;
    }
    setSessionsLoading(true);
    try {
      const result = await listAgentkitSessions(selectedTool.toolId);
      setSessions(result.data);
      setSessionError(undefined);
    } catch (error) {
      setSessionError(messageOf(error));
    } finally {
      setSessionsLoading(false);
    }
  }, [selectedTool]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const createInstance = async (input: { userSessionId?: string; ttl?: number }) => {
    if (!selectedTool) throw new Error("请先选择 AgentKit Tool");
    const created = await createAgentkitSession(selectedTool.toolId, input);
    setSessions((current) => mergeAgentkitSessions(current, [created]));
    await refreshSessions();
    setSessionError(undefined);
  };

  if (!configLoading && !config.configured) {
    return <ConsoleLogin onComplete={() => void refreshConfig()} />;
  }

  if (!selectedTool) {
    return (
      <ToolAdmin
        key={config.recentToolsScope ?? "no-account"}
        config={config}
        configLoading={configLoading}
        configError={configError}
        theme={theme}
        onToggleTheme={toggleTheme}
        onRetryConfig={() => void refreshConfig()}
        onSelectTool={(tool) => {
          rememberRecentTool(window.localStorage, config.recentToolsScope, tool);
          setSelectedTool(tool);
          setSessions([]);
          setSessionError(undefined);
        }}
        onLogout={() => {
          void logoutConsoleLogin()
            .then(() => refreshConfig())
            .catch((error: unknown) => setConfigError(messageOf(error)));
        }}
      />
    );
  }

  return (
    <>
      <SessionAdmin
        tool={selectedTool}
        privateType={config.privateType}
        sessions={sessions}
        loading={sessionsLoading}
        error={sessionError}
        theme={theme}
        onToggleTheme={toggleTheme}
        onBack={() => {
          setSelectedTool(undefined);
          setSessions([]);
          setSessionError(undefined);
        }}
        onRefresh={() => void refreshSessions()}
        onCreate={() => setShowCreateInstance(true)}
        onEnter={(session) => {
          setSessionError(undefined);
          const workspace = runtimeWorkspaceForToolType(
            selectedTool.toolType,
            config.privateType,
          );
          if (workspace === "Codex") {
            openCodexWorkspace(selectedTool, session);
            return;
          }
          if (workspace !== "Hermes" && workspace !== "OpenClaw") {
            setSessionError(`${selectedTool.toolType || "该类型"} 尚未接入 Runtime Workspace`);
            return;
          }
          const opened = window.open("about:blank", "_blank");
          if (!opened) {
            setSessionError("浏览器阻止了工作区窗口，请允许 Situla 打开新窗口后重试。");
            return;
          }
          void launchAgentkitWorkspace(selectedTool.toolId, session.sessionId)
            .then(({ url }) => {
              opened.location.replace(new URL(url, window.location.origin).toString());
              opened.focus();
            })
            .catch((error: unknown) => {
              opened.close();
              setSessionError(`打开 ${workspace} 工作区失败：${messageOf(error)}`);
            });
        }}
      />
      {showCreateInstance && (
        <CreateInstanceDialog
          onClose={() => setShowCreateInstance(false)}
          onCreate={async (input) => {
            await createInstance(input);
            setShowCreateInstance(false);
          }}
        />
      )}
    </>
  );
}

function mergeAgentkitSessions(
  current: AgentkitSession[],
  incoming: AgentkitSession[],
): AgentkitSession[] {
  const merged = new Map(current.map((session) => [session.sessionId, session]));
  for (const session of incoming) merged.set(session.sessionId, session);
  return [...merged.values()].sort(
    (left, right) =>
      (Date.parse(right.createdAt ?? "") || 0) - (Date.parse(left.createdAt ?? "") || 0),
  );
}
