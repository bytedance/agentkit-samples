import { formatInstanceTime, shortId } from "../display";
import { runtimeWorkspaceForToolType } from "../../../src/runtime.ts";
import type {
  AgentkitRuntimeType,
  AgentkitSession,
  AgentkitSessionSnapshot,
  AgentkitTool,
  RuntimeWorkspace,
} from "../types";
import type { Theme } from "../ui-types";
import {
  AlertIcon,
  ArrowLeftIcon,
  ChevronIcon,
  CubeIcon,
  Logo,
  MoonIcon,
  PlusIcon,
  RefreshIcon,
  Spinner,
  SunIcon,
} from "./ui";

interface SessionAdminProps {
  tool: AgentkitTool;
  privateType?: AgentkitRuntimeType;
  sessions: AgentkitSession[];
  snapshots: AgentkitSessionSnapshot[];
  loading: boolean;
  restoringSnapshotId?: string;
  error?: string;
  theme: Theme;
  onToggleTheme: () => void;
  onBack: () => void;
  onRefresh: () => void;
  onCreate: () => void;
  onRestore: (snapshot: AgentkitSessionSnapshot) => void;
  onEnter: (session: AgentkitSession) => void;
}

export function SessionAdmin({
  tool,
  privateType,
  sessions,
  snapshots,
  loading,
  restoringSnapshotId,
  error,
  theme,
  onToggleTheme,
  onBack,
  onRefresh,
  onCreate,
  onRestore,
  onEnter,
}: SessionAdminProps) {
  const workspace = runtimeWorkspaceForToolType(tool.toolType, privateType);
  const workspacePath = workspace ? WORKSPACE_PATHS[workspace] : undefined;

  return (
    <div className="tool-admin-shell session-admin-shell">
      <header className="tool-admin-topbar">
        <div className="tool-admin-brand"><Logo /><span><strong>Situla</strong><small>Session Center</small></span></div>
        <div className="tool-admin-actions">
          <span className="tool-admin-region"><i /><span>{tool.toolType || "Unknown runtime"}{workspacePath ? ` · ${workspacePath}` : ""}</span></span>
          <button className="session-back-button" onClick={onBack}><ArrowLeftIcon /><span>工作沙箱</span></button>
          <button className="icon-button" onClick={onToggleTheme} aria-label={theme === "dark" ? "切换浅色主题" : "切换深色主题"}>{theme === "dark" ? <SunIcon /> : <MoonIcon />}</button>
        </div>
      </header>

      <main className="tool-admin-main session-admin-main">
        <section className="session-admin-hero">
          <div className="session-admin-tool-icon"><CubeIcon /></div>
          <div className="session-admin-tool-copy">
            <div className="eyebrow">AGENTKIT TOOL / SESSIONS</div>
            <h1>{tool.name || "未命名 Tool"}</h1>
            <p>{tool.description || "选择或创建一个 AgentKit Session，再进入对应的 Runtime Workspace。"}</p>
            <div className="session-admin-meta"><code>{tool.toolId}</code><span>{tool.status}</span>{tool.projectName && <span>{tool.projectName}</span>}<span>{tool.enableSnapshot === undefined ? "正在读取快照配置" : tool.enableSnapshot ? "自动快照已开启" : "自动快照未开启"}</span></div>
          </div>
          <button className="session-create-button" onClick={onCreate}>
            <span className="session-create-icon"><PlusIcon /></span>
            <span className="session-create-copy"><strong>创建 Session</strong><small>启动新的沙箱实例</small></span>
            <ChevronIcon open={false} />
          </button>
        </section>

        {!workspace && (
          <div className="tool-admin-notice session-runtime-notice">
            <AlertIcon /><span>{tool.toolType === "Private"
              ? <>Private Tool 尚未配置 Runtime 映射。设置 <strong>SITULA_PRIVATE_TYPE</strong> 为 CodeEnv、HermesEnv 或 ArkClawEnv 后重启 Situla。</>
              : <><strong>{tool.toolType || "该类型"}</strong> 的 Runtime Workspace 尚未接入。当前仍可管理 Session，但不能进入工作区。</>}</span>
          </div>
        )}
        {error && <div className="tool-admin-notice error"><AlertIcon /><span>{error}</span><button onClick={onRefresh}>重试</button></div>}

        <section className="tool-section session-list-section">
          <div className="tool-list-toolbar">
            <div><h2>Session 实例</h2><p>AgentKit 控制面中的短期沙箱实例</p></div>
            <div className="session-list-actions">
              <button className="session-refresh-button" onClick={onRefresh} disabled={loading}><RefreshIcon /><span>刷新</span></button>
            </div>
          </div>

          <div className="session-admin-list" aria-busy={loading}>
            {sessions.map((session) => {
              const ready = session.status.toLowerCase() === "ready";
              const canEnter = ready && Boolean(workspace);
              return (
                <article className="session-admin-card" key={session.sessionId}>
                  <span className={`instance-avatar ${ready ? "ready" : "pending"}`}><CubeIcon /></span>
                  <span className="session-admin-card-copy">
                    <span className="session-admin-card-title"><strong>{session.userSessionId || `Session ${shortId(session.sessionId)}`}</strong><i className={`tool-status ${ready ? "ready" : "pending"}`}>{session.status}</i></span>
                    <code>{session.sessionId}</code>
                    <small>Session {shortId(session.sessionId)} · 创建于 {formatInstanceTime(session.createdAt)} · 到期 {formatInstanceTime(session.expireAt)}</small>
                  </span>
                  <button className="session-enter-button" disabled={!canEnter} onClick={() => onEnter(session)}>
                    {canEnter ? "进入工作区" : ready ? "等待 Runtime 接入" : "等待 Ready"}<ChevronIcon open={false} />
                  </button>
                </article>
              );
            })}
            {snapshots.map((snapshot) => {
              const restoring = restoringSnapshotId === snapshot.snapshotId;
              return (
                <article className="session-admin-card snapshot" key={snapshot.snapshotId}>
                  <span className="instance-avatar snapshot"><CubeIcon /></span>
                  <span className="session-admin-card-copy">
                    <span className="session-admin-card-title"><strong>{snapshot.userSessionId || (snapshot.sessionId ? `Session ${shortId(snapshot.sessionId)}` : `Snapshot ${shortId(snapshot.snapshotId)}`)}</strong><i className="tool-status snapshot">可唤醒</i></span>
                    <code>{snapshot.sessionId || snapshot.snapshotId}</code>
                    <small>创建于 {formatInstanceTime(snapshot.createdAt)}{snapshot.reason ? ` · ${snapshot.reason}` : ""} · 唤醒时可设置 1–1440 分钟</small>
                  </span>
                  <button className="session-enter-button snapshot" disabled={Boolean(restoringSnapshotId)} onClick={() => onRestore(snapshot)}>
                    {restoring ? <><Spinner />正在唤醒…</> : <>唤醒<ChevronIcon open={false} /></>}
                  </button>
                </article>
              );
            })}
            {loading && sessions.length === 0 && snapshots.length === 0 && <div className="tool-admin-loading"><Spinner />正在读取 Session 与快照…</div>}
            {!loading && sessions.length === 0 && snapshots.length === 0 && (
              <div className="session-admin-empty"><CubeIcon /><strong>还没有 Session</strong><span>使用页面右上方的“创建 Session”建立第一个实例。</span></div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

const WORKSPACE_PATHS: Record<RuntimeWorkspace, string> = {
  Codex: "/codex",
  Hermes: "/hermes",
  OpenClaw: "/openclaw",
};
