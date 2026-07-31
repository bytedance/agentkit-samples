import { relativeThreadTime, shortId, threadTitle } from "../display";
import type { AgentkitTool, ConnectedSession, ThreadSummary } from "../types";
import {
  ArchiveIcon,
  ArrowLeftIcon,
  ChatIcon,
  CloseIcon,
  CubeIcon,
  Logo,
  PlusIcon,
  RefreshIcon,
} from "./ui";

interface SidebarProps {
  open: boolean;
  title: string;
  session?: ConnectedSession;
  busy: boolean;
  threads: ThreadSummary[];
  threadsLoading: boolean;
  hasMoreThreads: boolean;
  search: string;
  onSearch: (value: string) => void;
  onSelectThread: (threadId: string) => void;
  onArchiveThread: (threadId: string) => void;
  onLoadMore: () => void;
  onRefresh: () => void;
  onNewThread: () => void;
  onOpenInstanceInfo: () => void;
  onClose: () => void;
  selectedTool?: AgentkitTool;
  onLeaveWorkspace: () => void;
}

export function Sidebar({
  open,
  title,
  session,
  busy,
  threads,
  threadsLoading,
  hasMoreThreads,
  search,
  onSearch,
  onSelectThread,
  onArchiveThread,
  onLoadMore,
  onRefresh,
  onNewThread,
  onOpenInstanceInfo,
  onClose,
  selectedTool,
  onLeaveWorkspace,
}: SidebarProps) {
  return (
    <>
      <aside className={`sidebar ${open ? "open" : ""}`} aria-label={`Thread：${title}`}>
        <div className="brand-row">
          <Logo />
          <div><div className="brand">Situla</div><div className="brand-subtitle">AgentKit client</div></div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="关闭侧栏"><CloseIcon /></button>
        </div>
        <button className="workspace-back-action" onClick={onLeaveWorkspace}>
          <span className="workspace-back-icon"><ArrowLeftIcon /></span>
          <span className="workspace-back-copy"><small>返回</small><strong>{selectedTool ? "Session 列表" : "Tool Center"}</strong></span>
        </button>
        <button className="new-chat" disabled={!session || busy} onClick={onNewThread}>
          <PlusIcon /><span>发起任务</span><kbd>⌘/Ctrl N</kbd>
        </button>
        <div className="nav-label"><span>Threads</span>{session && <small>{threads.length}</small>}</div>
        {session && (
          <div className="thread-tools">
            <input type="search" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="搜索历史对话" aria-label="搜索历史对话" />
            <button onClick={onRefresh} disabled={threadsLoading} aria-label="刷新 Thread 列表"><RefreshIcon /></button>
          </div>
        )}
        <div className="conversation-list">
          {session ? (
            <>
              {threads.map((thread) => {
                const active = thread.id === session.threadId;
                return (
                  <div className={`conversation-row ${active ? "active" : ""}`} key={thread.id}>
                    <button className="conversation" disabled={busy} onClick={() => onSelectThread(thread.id)} title={thread.preview || thread.name || thread.id}>
                      <span className="conversation-icon"><ChatIcon /></span>
                      <span className="conversation-copy"><strong>{threadTitle(thread)}</strong><small>{relativeThreadTime(thread.updatedAt)} · {shortId(thread.id)}</small></span>
                      {active && <span className="live-dot" />}
                    </button>
                    <button className="archive-thread" disabled={busy} onClick={() => onArchiveThread(thread.id)} aria-label={`归档 ${threadTitle(thread)}`} title="归档对话"><ArchiveIcon /></button>
                  </div>
                );
              })}
              {threadsLoading && <div className="thread-list-note">正在加载 Threads…</div>}
              {!threadsLoading && threads.length === 0 && <div className="empty-conversations">{search ? "没有匹配的历史对话。" : "还没有可恢复的对话。"}</div>}
              {hasMoreThreads && !threadsLoading && <button className="load-more-threads" onClick={onLoadMore}>加载更多</button>}
            </>
          ) : (
            <div className="empty-conversations">连接实例后，Threads 会出现在这里。</div>
          )}
        </div>
        <div className="sidebar-bottom">
          <button className="sidebar-action" disabled={!session} onClick={onOpenInstanceInfo}><CubeIcon />实例信息</button>
        </div>
      </aside>
      {open && <button className="sidebar-backdrop" onClick={onClose} aria-label="关闭侧栏" />}
    </>
  );
}
