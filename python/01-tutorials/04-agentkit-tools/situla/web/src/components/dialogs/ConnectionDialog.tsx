import { useEffect } from "react";
import type { ConnectedSession } from "../../types";
import { CloseIcon, CubeIcon } from "../ui";

interface ConnectionDialogProps {
  session: ConnectedSession;
  onClose: () => void;
}

export function ConnectionDialog({ session, onClose }: ConnectionDialogProps) {
  useEffect(() => {
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [onClose]);

  return (
    <div className="modal-layer">
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭实例信息" />
      <section className="connection-dialog" role="dialog" aria-modal="true" aria-labelledby="connection-dialog-title">
        <div className="dialog-accent" />
        <div className="dialog-head"><div className="dialog-icon"><CubeIcon /></div><div><div className="eyebrow">AGENTKIT TOOL · SESSION</div><h2 id="connection-dialog-title">实例信息</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭实例信息"><CloseIcon /></button></div>
        <div className="connected-detail">
          <div className="detail-status"><span className="detail-status-indicator" /><div><strong>连接正常</strong><small>浏览器 ↔ 本地 bridge ↔ Codex app-server</small></div></div>
          <dl>{session.agentkitSession && <><div><dt>实例</dt><dd>{session.agentkitSession.userSessionId || session.agentkitSession.sessionId}</dd></div><div><dt>Session</dt><dd>{session.agentkitSession.sessionId}</dd></div></>}<div><dt>Endpoint</dt><dd>{session.endpoint}</dd></div><div><dt>Thread</dt><dd>{session.threadId}</dd></div></dl>
          <div className="dialog-actions"><button className="primary" onClick={onClose}>继续对话</button></div>
        </div>
      </section>
    </div>
  );
}
