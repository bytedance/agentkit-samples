import { useEffect, useRef, useState } from "react";
import { listAgentkitTools } from "../api";
import { messageOf } from "../display";
import {
  readRecentTools,
  refreshRecentTools,
  writeRecentTools,
} from "../tool-recents";
import type { AgentkitConfig, AgentkitTool } from "../types";
import type { Theme } from "../ui-types";
import {
  AlertIcon,
  CubeIcon,
  Logo,
  LogoutIcon,
  MoonIcon,
  PulseIcon,
  RefreshIcon,
  SearchIcon,
  Spinner,
  SunIcon,
} from "./ui";

interface ToolAdminProps {
  config: AgentkitConfig;
  configLoading: boolean;
  configError?: string;
  theme: Theme;
  onToggleTheme: () => void;
  onRetryConfig: () => void;
  onSelectTool: (tool: AgentkitTool) => void;
  onLogout?: () => void;
}

export function ToolAdmin({
  config,
  configLoading,
  configError,
  theme,
  onToggleTheme,
  onRetryConfig,
  onSelectTool,
  onLogout,
}: ToolAdminProps) {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [nextToken, setNextToken] = useState<string>();
  const [tokenHistory, setTokenHistory] = useState<Array<string | undefined>>([]);
  const [tools, setTools] = useState<AgentkitTool[]>([]);
  const [followingToken, setFollowingToken] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState<string>();
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [recentTools, setRecentTools] = useState<AgentkitTool[]>(() =>
    typeof window === "undefined"
      ? []
      : readRecentTools(window.localStorage, config.recentToolsScope));
  const requestRef = useRef(0);

  useEffect(() => {
    setRecentTools(typeof window === "undefined"
      ? []
      : readRecentTools(window.localStorage, config.recentToolsScope));
  }, [config.recentToolsScope]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const normalized = searchInput.trim();
      setSearch(normalized);
      setNextToken(undefined);
      setTokenHistory([]);
    }, 260);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (!logoutConfirmOpen) return;
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setLogoutConfirmOpen(false);
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [logoutConfirmOpen]);

  useEffect(() => {
    if (!config.configured) {
      setTools([]);
      setFollowingToken(undefined);
      return;
    }
    const requestId = ++requestRef.current;
    setLoading(true);
    setListError(undefined);
    void listAgentkitTools({
      maxResults: 10,
      ...(nextToken ? { nextToken } : {}),
      ...(search ? { search } : {}),
    }).then((page) => {
      if (requestId !== requestRef.current) return;
      setTools(page.data);
      setFollowingToken(page.nextToken);
      setRecentTools((current) => {
        const refreshed = refreshRecentTools(current, page.data);
        if (typeof window !== "undefined") {
          writeRecentTools(window.localStorage, config.recentToolsScope, refreshed);
        }
        return refreshed;
      });
    }).catch((error: unknown) => {
      if (requestId !== requestRef.current) return;
      setTools([]);
      setFollowingToken(undefined);
      setListError(messageOf(error));
    }).finally(() => {
      if (requestId === requestRef.current) setLoading(false);
    });
  }, [config.configured, config.recentToolsScope, nextToken, refreshKey, search]);

  const selectNextPage = () => {
    if (!followingToken) return;
    setTokenHistory((current) => [...current, nextToken]);
    setNextToken(followingToken);
  };

  const selectPreviousPage = () => {
    setTokenHistory((current) => {
      if (current.length === 0) return current;
      setNextToken(current[current.length - 1]);
      return current.slice(0, -1);
    });
  };

  return (
    <div className="tool-admin-shell">
      <header className="tool-admin-topbar">
        <div className="tool-admin-brand"><Logo /><span><strong>Situla</strong><small>AgentKit Admin</small></span></div>
        <div className="tool-admin-actions">
          {config.configured && <span className="tool-admin-region"><i /><span>{config.region}</span></span>}
          {config.consoleLogin && <button className="admin-logout-button" onClick={() => setLogoutConfirmOpen(true)}><LogoutIcon /><span>退出登录</span></button>}
          <button className="icon-button" onClick={onToggleTheme} aria-label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"}>{theme === "dark" ? <SunIcon /> : <MoonIcon />}</button>
        </div>
      </header>

      <main className="tool-admin-main">
        <section className="tool-admin-hero">
          <div><div className="eyebrow">ADMIN · AGENTKIT TOOLS</div><h1>选择工作沙箱</h1><p>选择一个 AgentKit Tool 后进入 Session 与 Codex 工作区。这里仅查询 Tool，不会创建或修改 Tool。</p></div>
        </section>

        {(configError || (!configLoading && !config.configured)) && (
          <div className="tool-admin-notice error">
            <AlertIcon />
            <span>{configError ?? "AgentKit 控制面未配置，请在 bridge 环境中设置访问凭证。"}</span>
            <button onClick={onRetryConfig}>重试</button>
          </div>
        )}

        {configLoading ? (
          <div className="tool-admin-loading"><Spinner />正在读取 AgentKit 配置…</div>
        ) : config.configured ? (
          <>
            <section className="tool-section recent-tools-section" aria-labelledby="recent-tools-title">
              <div className="tool-section-heading"><div><span className="tool-section-icon"><PulseIcon /></span><span><h2 id="recent-tools-title">常用 Tool</h2><p>记录当前账号最近进入或发生对话的 Tool，按使用时间排序。</p></span></div><small>{recentTools.length} / 3</small></div>
              {recentTools.length > 0 ? (
                <div className="recent-tool-grid">
                  {recentTools.map((tool) => <ToolCard key={tool.toolId} tool={tool} onSelect={onSelectTool} compact />)}
                </div>
              ) : (
                <div className="recent-tools-empty"><PulseIcon /><span>还没有常用 Tool。进入 Tool 或开始对话后会自动记录。</span></div>
              )}
            </section>

            <section className="tool-section all-tools-section" aria-labelledby="all-tools-title">
              <div className="tool-list-toolbar">
                <div><h2 id="all-tools-title">所有 Tool</h2><p>所有类型统一展示，每页 10 条。</p></div>
                <label className="tool-search"><SearchIcon /><input type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="筛选名称、ID 或描述" aria-label="筛选 Tool 名称、ID 或描述" />{loading && <Spinner />}</label>
                <button className="tool-refresh" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading} aria-label="刷新 Tool 列表"><RefreshIcon /></button>
              </div>

              {listError && <div className="tool-admin-notice error"><AlertIcon /><span>{listError}</span><button onClick={() => setRefreshKey((value) => value + 1)}>重试</button></div>}
              <div className="tool-list" aria-busy={loading}>
                {tools.map((tool) => (
                  <ToolCard key={tool.toolId} tool={tool} onSelect={onSelectTool} />
                ))}
                {loading && tools.length === 0 && <div className="tool-admin-loading"><Spinner />正在调用 ListTools…</div>}
                {!loading && !listError && tools.length === 0 && <div className="tool-list-empty"><CubeIcon /><strong>{search ? "没有匹配的 Tool" : "当前地域没有 Tool"}</strong><span>{search ? "请尝试其他名称、ID 或描述关键字。" : "可在 AgentKit 控制台创建 Tool 后回到此处刷新。"}</span></div>}
              </div>

              <footer className="tool-pagination"><span>第 {tokenHistory.length + 1} 页{search ? ` · 筛选“${search}”` : ""}</span><div><button className="secondary" disabled={loading || tokenHistory.length === 0} onClick={selectPreviousPage}>上一页</button><button className="primary" disabled={loading || !followingToken} onClick={selectNextPage}>下一页</button></div></footer>
            </section>
          </>
        ) : null}
      </main>
      {logoutConfirmOpen && (
        <div className="modal-layer logout-confirm-layer">
          <button className="modal-backdrop" onClick={() => setLogoutConfirmOpen(false)} aria-label="取消退出登录" />
          <section className="connection-dialog logout-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="logout-confirm-title" aria-describedby="logout-confirm-description">
            <div className="dialog-accent" />
            <div className="dialog-head">
              <div className="dialog-icon"><LogoutIcon /></div>
              <div><div className="eyebrow">CONSOLE LOGIN</div><h2 id="logout-confirm-title">确认退出登录？</h2></div>
            </div>
            <p className="dialog-copy" id="logout-confirm-description">退出后将删除本机保存的 Console Login 凭证。再次使用 Situla 时，需要重新完成授权登录。</p>
            <div className="logout-confirm-note"><AlertIcon /><span>这个操作不会删除 AgentKit Tool 或已有的 Session。</span></div>
            <div className="dialog-actions">
              <button className="secondary" autoFocus onClick={() => setLogoutConfirmOpen(false)}>取消</button>
              <button className="logout-confirm-action" onClick={() => { setLogoutConfirmOpen(false); onLogout?.(); }}><LogoutIcon />确认退出</button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function ToolCard({ tool, compact = false, onSelect }: {
  tool: AgentkitTool;
  compact?: boolean;
  onSelect: (tool: AgentkitTool) => void;
}) {
  const ready = tool.status.toLowerCase() === "ready";
  return (
    <article className={`tool-card ${compact ? "compact" : ""}`}>
      <button className="tool-card-main" onClick={() => onSelect(tool)} disabled={!ready}>
        <span className="tool-card-icon"><CubeIcon /></span>
        <span className="tool-card-copy">
          <span className="tool-card-title"><strong>{tool.name || "未命名 Tool"}</strong><i className={`tool-status ${ready ? "ready" : "pending"}`}>{tool.status}</i></span>
          <code>{tool.toolId}</code>
          <span className="tool-description">{tool.description || "暂无描述"}</span>
          <span className="tool-meta"><em>{tool.toolType || "未知类型"}</em>{tool.projectName && <em>{tool.projectName}</em>}{tool.updatedAt && <em>更新于 {formatToolDate(tool.updatedAt)}</em>}</span>
        </span>
        <span className="tool-enter">{ready ? "进入" : "不可用"}<span aria-hidden="true">→</span></span>
      </button>
    </article>
  );
}

function formatToolDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("zh-CN");
}
