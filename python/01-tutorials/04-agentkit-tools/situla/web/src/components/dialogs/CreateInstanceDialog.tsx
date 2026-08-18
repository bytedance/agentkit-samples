import { useState, type FormEvent } from "react";
import { messageOf } from "../../display";
import { AlertIcon, CloseIcon, LockIcon, PlusIcon, Spinner } from "../ui";

interface CreateInstanceDialogProps {
  onClose: () => void;
  onCreate: (input: { userSessionId?: string; ttl?: number }) => Promise<void>;
}

export function CreateInstanceDialog({ onClose, onCreate }: CreateInstanceDialogProps) {
  const [userSessionId, setUserSessionId] = useState("");
  const [minutes, setMinutes] = useState(480);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      await onCreate({
        ...(userSessionId.trim() ? { userSessionId: userSessionId.trim() } : {}),
        ttl: Math.round(minutes * 60),
      });
    } catch (createError) {
      setFormError(messageOf(createError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-layer create-instance-layer">
      <button className="modal-backdrop" onClick={busy ? undefined : onClose} aria-label="关闭创建实例" />
      <section className="connection-dialog create-instance-dialog" role="dialog" aria-modal="true" aria-labelledby="create-instance-title">
        <div className="dialog-accent" />
        <div className="dialog-head"><div className="dialog-icon"><PlusIcon /></div><div><div className="eyebrow">CREATE SESSION</div><h2 id="create-instance-title">创建新实例</h2></div><button className="icon-button" disabled={busy} onClick={onClose} aria-label="关闭"><CloseIcon /></button></div>
        <form onSubmit={submit}>
          <p className="dialog-copy">UserSessionId 用于识别实例，并在 Session 过期后关联和恢复快照。</p>
          <label className="field"><span>UserSessionId（可选）</span><input autoFocus value={userSessionId} onChange={(event) => setUserSessionId(event.target.value)} placeholder="留空则自动生成 situla-…" maxLength={200} pattern="[A-Za-z0-9_-]+" /></label>
          <label className="field"><span>存活时间（分钟）</span><input type="number" min={1} max={1440} step={1} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label>
          <div className="security-note"><LockIcon /><span>访问密钥只由本地 bridge 读取，不会发送给浏览器或写入页面存储。</span></div>
          {formError && <div className="form-error"><AlertIcon />{formError}</div>}
          <div className="dialog-actions"><button className="secondary" type="button" disabled={busy} onClick={onClose}>取消</button><button className="primary" disabled={busy || !Number.isInteger(minutes) || minutes < 1 || minutes > 1440}>{busy ? <><Spinner />正在创建并等待就绪…</> : <><PlusIcon />创建 Session</>}</button></div>
        </form>
      </section>
    </div>
  );
}
