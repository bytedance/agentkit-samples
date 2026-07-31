import { useEffect, useRef, useState, type ReactNode } from "react";
import { getSandboxTerminalUrl } from "./api";
import { Spinner } from "./components/ui";
import { messageOf } from "./display";

export function TerminalDialog({
  sessionId,
  shellSessionId,
  onShellSessionId,
  onClose,
}: {
  sessionId: string;
  shellSessionId?: string;
  onShellSessionId: (value: string) => void;
  onClose: () => void;
}): ReactNode {
  const closeRef = useRef(onClose);
  const shellIdRef = useRef(onShellSessionId);
  closeRef.current = onClose;
  shellIdRef.current = onShellSessionId;
  const [expanded, setExpanded] = useState(true);
  const [url, setUrl] = useState<string>();
  const [status, setStatus] = useState("正在连接");
  const [error, setError] = useState<string>();
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setUrl(undefined);
    setError(undefined);
    setStatus("正在连接");
    void getSandboxTerminalUrl(sessionId, shellSessionId)
      .then((result) => {
        if (cancelled) return;
        shellIdRef.current(result.shellSessionId);
        setUrl(result.url);
        setStatus("正在加载");
      })
      .catch((terminalError: unknown) => {
        if (cancelled) return;
        setError(messageOf(terminalError));
        setStatus("连接异常");
      });
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
    };
    window.addEventListener("keydown", escape);
    return () => {
      cancelled = true;
      window.removeEventListener("keydown", escape);
    };
  }, [sessionId]);

  const reload = () => {
    if (!url) return;
    setStatus("正在刷新");
    setRevision((value) => value + 1);
  };

  return (
    <div className={`modal-layer terminal-layer ${expanded ? "expanded" : ""}`}>
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭 Terminal" />
      <section className="terminal-dialog" role="dialog" aria-modal="true" aria-labelledby="terminal-title">
        <header>
          <div>
            <span className="terminal-traffic" aria-hidden="true"><i /><i /><i /></span>
            <h2 id="terminal-title">AgentKit Shell</h2>
            <small>{status}</small>
          </div>
          <div>
            <button onClick={reload} disabled={!url}>刷新</button>
            <button onClick={() => setExpanded((value) => !value)} aria-label={expanded ? "退出全屏" : "全屏"}>
              {expanded ? "收起" : "全屏"}
            </button>
            <button onClick={onClose} aria-label="关闭 Terminal">关闭</button>
          </div>
        </header>
        <div className="terminal-screen native-terminal-screen">
          {error ? (
            <div className="browser-error">无法打开原生 Terminal：{error}</div>
          ) : url ? (
            <iframe
              key={revision}
              src={url}
              title="AgentKit Session Terminal"
              sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-same-origin allow-scripts"
              allow="clipboard-read; clipboard-write"
              referrerPolicy="no-referrer"
              onLoad={() => setStatus("已加载")}
            />
          ) : (
            <div className="browser-loading"><Spinner />正在连接 AgentKit Session Terminal…</div>
          )}
        </div>
      </section>
    </div>
  );
}
