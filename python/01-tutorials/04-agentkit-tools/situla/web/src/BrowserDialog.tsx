import { useEffect, useRef, useState, type ReactNode } from "react";
import { getSandboxBrowserUrl } from "./api";
import { messageOf } from "./display";
import { Spinner } from "./components/ui";

export function BrowserDialog({
  sessionId,
  onClose,
}: {
  sessionId: string;
  onClose: () => void;
}): ReactNode {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const [expanded, setExpanded] = useState(false);
  const [url, setUrl] = useState<string>();
  const [status, setStatus] = useState("正在连接");
  const [error, setError] = useState<string>();
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setUrl(undefined);
    setError(undefined);
    setStatus("正在连接");
    void getSandboxBrowserUrl(sessionId)
      .then((result) => {
        if (cancelled) return;
        setUrl(result.url);
        setStatus("正在加载");
      })
      .catch((browserError: unknown) => {
        if (cancelled) return;
        setError(messageOf(browserError));
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
    <div className={`modal-layer terminal-layer browser-layer ${expanded ? "expanded" : ""}`}>
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭沙箱浏览器" />
      <section className="terminal-dialog browser-dialog" role="dialog" aria-modal="true" aria-labelledby="browser-title">
        <header>
          <div>
            <span className="terminal-light" />
            <h2 id="browser-title">沙箱浏览器</h2>
            <small>{status}</small>
          </div>
          <div>
            <button onClick={reload} disabled={!url}>刷新</button>
            <button onClick={() => setExpanded((value) => !value)} aria-label={expanded ? "退出全屏" : "全屏"}>
              {expanded ? "收起" : "全屏"}
            </button>
            <button onClick={onClose} aria-label="关闭沙箱浏览器">关闭</button>
          </div>
        </header>
        <div className="browser-screen">
          {error ? (
            <div className="browser-error">无法打开沙箱浏览器：{error}</div>
          ) : url ? (
            <iframe
              key={revision}
              src={url}
              title="AgentKit Session 沙箱浏览器"
              sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-same-origin allow-scripts"
              allow="clipboard-read; clipboard-write"
              referrerPolicy="no-referrer"
              onLoad={() => setStatus("已加载")}
            />
          ) : (
            <div className="browser-loading"><Spinner />正在连接 AgentKit Session Browser…</div>
          )}
        </div>
      </section>
    </div>
  );
}
