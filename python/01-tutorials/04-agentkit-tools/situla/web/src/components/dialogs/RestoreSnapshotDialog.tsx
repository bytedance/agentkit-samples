import { useState, type FormEvent } from "react";
import { messageOf } from "../../display";
import type { AgentkitSessionSnapshot } from "../../types";
import { AlertIcon, CloseIcon, RefreshIcon, Spinner } from "../ui";

interface RestoreSnapshotDialogProps {
  snapshot: AgentkitSessionSnapshot;
  onClose: () => void;
  onRestore: (input: { ttl: number }) => Promise<void>;
}

export function RestoreSnapshotDialog({
  snapshot,
  onClose,
  onRestore,
}: RestoreSnapshotDialogProps) {
  const [minutes, setMinutes] = useState(480);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      await onRestore({ ttl: Math.round(minutes * 60) });
    } catch (restoreError) {
      setFormError(messageOf(restoreError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-layer create-instance-layer">
      <button className="modal-backdrop" onClick={busy ? undefined : onClose} aria-label="关闭唤醒窗口" />
      <section className="connection-dialog create-instance-dialog" role="dialog" aria-modal="true" aria-labelledby="restore-snapshot-title">
        <div className="dialog-accent" />
        <div className="dialog-head"><div className="dialog-icon"><RefreshIcon /></div><div><div className="eyebrow">WAKE FROM SNAPSHOT</div><h2 id="restore-snapshot-title">唤醒 Sandbox</h2></div><button className="icon-button" disabled={busy} onClick={onClose} aria-label="关闭"><CloseIcon /></button></div>
        <form onSubmit={submit}>
          <p className="dialog-copy">从快照唤醒同一 UserSessionId 的 Sandbox，并从唤醒完成时开始重新计算存活时间。</p>
          <label className="field"><span>UserSessionId</span><input value={snapshot.userSessionId || "未提供"} readOnly /></label>
          <label className="field"><span>唤醒后的存活时间（分钟）</span><input autoFocus type="number" min={1} max={1440} step={1} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label>
          {formError && <div className="form-error"><AlertIcon />{formError}</div>}
          <div className="dialog-actions"><button className="secondary" type="button" disabled={busy} onClick={onClose}>取消</button><button className="primary" disabled={busy || !Number.isInteger(minutes) || minutes < 1 || minutes > 1440}>{busy ? <><Spinner />正在唤醒并等待就绪…</> : <><RefreshIcon />唤醒</>}</button></div>
        </form>
      </section>
    </div>
  );
}
