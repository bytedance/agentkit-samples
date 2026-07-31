import { useState, type FormEvent } from "react";
import { messageOf } from "../../display";
import { AlertIcon, CloseIcon, LockIcon, PlusIcon, Spinner } from "../ui";

interface CreateInstanceDialogProps {
  onClose: () => void;
  onCreate: (input: { userSessionId?: string; ttl?: number }) => Promise<void>;
}

export function CreateInstanceDialog({ onClose, onCreate }: CreateInstanceDialogProps) {
  const [name, setName] = useState("");
  const [hours, setHours] = useState(8);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      await onCreate({ ...(name.trim() ? { userSessionId: name.trim() } : {}), ttl: Math.round(hours * 3_600) });
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
          <p className="dialog-copy">实例创建后会等待 Ready 并返回 Session 列表；同一个 UserSessionId 可用于识别和复用任务环境。</p>
          <label className="field"><span>实例名称 / UserSessionId</span><input autoFocus value={name} onChange={(event) => setName(event.target.value)} placeholder="留空则自动生成 situla-…" maxLength={128} /></label>
          <label className="field"><span>存活时间（小时）</span><input type="number" min={1} max={168} step={1} value={hours} onChange={(event) => setHours(Number(event.target.value))} /></label>
          <div className="security-note"><LockIcon /><span>访问密钥只由本地 bridge 读取，不会发送给浏览器或写入页面存储。</span></div>
          {formError && <div className="form-error"><AlertIcon />{formError}</div>}
          <div className="dialog-actions"><button className="secondary" type="button" disabled={busy} onClick={onClose}>取消</button><button className="primary" disabled={busy || !Number.isFinite(hours) || hours < 1 || hours > 168}>{busy ? <><Spinner />正在创建并等待就绪…</> : <><PlusIcon />创建 Session</>}</button></div>
        </form>
      </section>
    </div>
  );
}
