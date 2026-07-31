import { useState } from "react";
import { shortId } from "../display";
import { useDismissibleMenu } from "../hooks/useDismissibleMenu";
import type { ConnectedSession } from "../types";
import type { Theme } from "../ui-types";
import { BrowserIcon, ChevronIcon, LinkIcon, MenuIcon, MoonIcon, MoreVerticalIcon, SunIcon, TerminalIcon } from "./ui";

interface TopbarProps {
  title: string;
  session?: ConnectedSession;
  theme: Theme;
  onOpenSidebar: () => void;
  onOpenConnectionSettings: () => void;
  onOpenTerminal: () => void;
  onOpenSandboxBrowser: () => void;
  onToggleTheme: () => void;
}

export function Topbar({
  title,
  session,
  theme,
  onOpenSidebar,
  onOpenConnectionSettings,
  onOpenTerminal,
  onOpenSandboxBrowser,
  onToggleTheme,
}: TopbarProps) {
  const [settingsMenuOpen, setSettingsMenuOpen] = useState(false);
  const settingsMenuRef = useDismissibleMenu<HTMLDivElement>(settingsMenuOpen, setSettingsMenuOpen);

  return (
    <header className="topbar">
      <button className="icon-button mobile-only" onClick={onOpenSidebar} aria-label="打开侧栏">
        <MenuIcon />
      </button>
      <div className="topbar-title">
        <div className="eyebrow">CODEX SANDBOX</div>
        <div className="thread-line">
          <span>{session ? title : "未连接"}</span>
          {session && <span className="thread-pill">{shortId(session.threadId)}</span>}
        </div>
      </div>
      <div className="topbar-actions">
        <div className="settings-menu-anchor" ref={settingsMenuRef}>
          <button
            className={`icon-button ${settingsMenuOpen ? "active" : ""}`}
            onClick={() => setSettingsMenuOpen((open) => !open)}
            aria-label="打开更多操作菜单"
            aria-expanded={settingsMenuOpen}
          >
            <MoreVerticalIcon />
          </button>
          {settingsMenuOpen && (
            <div className="settings-menu" role="menu">
              <button
                role="menuitem"
                onClick={() => {
                  setSettingsMenuOpen(false);
                  onOpenConnectionSettings();
                }}
              >
                <span className="settings-menu-icon"><LinkIcon /></span>
                <span><strong>{session ? "实例信息" : "连接设置"}</strong><small>{session ? "查看当前 AgentKit Session" : "使用已有 Endpoint"}</small></span>
                <ChevronIcon open={false} />
              </button>
              <button
                role="menuitem"
                disabled={!session}
                onClick={() => {
                  setSettingsMenuOpen(false);
                  onOpenTerminal();
                }}
              >
                <span className="settings-menu-icon"><TerminalIcon /></span>
                <span><strong>Terminal</strong><small>{session ? "打开实例的交互式 Shell" : "连接实例后可用"}</small></span>
                <ChevronIcon open={false} />
              </button>
              <button
                role="menuitem"
                disabled={!session}
                onClick={() => {
                  setSettingsMenuOpen(false);
                  onOpenSandboxBrowser();
                }}
              >
                <span className="settings-menu-icon"><BrowserIcon /></span>
                <span><strong>沙箱浏览器</strong><small>{session ? "在页面内打开实例浏览器" : "连接实例后可用"}</small></span>
                <ChevronIcon open={false} />
              </button>
              <button role="menuitem" aria-pressed={theme === "light"} onClick={onToggleTheme}>
                <span className="settings-menu-icon">{theme === "dark" ? <MoonIcon /> : <SunIcon />}</span>
                <span><strong>主题</strong><small>{theme === "dark" ? "深色模式" : "浅色模式"}</small></span>
                <span className={`theme-switch ${theme === "light" ? "on" : ""}`} aria-hidden="true"><i /></span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
