import { formatApprovalValue } from "../../display";
import type { ApprovalDecision, BrowserApproval } from "../../types";
import { ShieldIcon, Spinner } from "../ui";

interface ApprovalDialogProps {
  approval: BrowserApproval;
  pendingCount: number;
  busy: boolean;
  onDecision: (decision: ApprovalDecision) => void;
}

export function ApprovalDialog({ approval, pendingCount, busy, onDecision }: ApprovalDialogProps) {
  return (
    <div className="modal-layer approval-layer">
      <div className="modal-backdrop" />
      <section className="approval-dialog" role="alertdialog" aria-modal="true" aria-labelledby="approval-dialog-title">
        <div className="approval-icon"><ShieldIcon /></div>
        <div className="eyebrow">ACTION REQUIRED{pendingCount > 1 ? ` · ${pendingCount} PENDING` : ""}</div>
        <h2 id="approval-dialog-title">{approval.kind === "command" ? "允许执行命令？" : "允许修改文件？"}</h2>
        {approval.reason && <p>{approval.reason}</p>}
        {approval.command && <pre><code>{approval.command}</code></pre>}
        <dl>
          {approval.cwd && <div><dt>目录</dt><dd>{approval.cwd}</dd></div>}
          {approval.grantRoot && <div><dt>写入范围</dt><dd>{approval.grantRoot}</dd></div>}
          {approval.environmentId !== undefined && <div><dt>环境</dt><dd>{approval.environmentId ?? "默认环境"}</dd></div>}
          {approval.threadId && <div><dt>Thread ID</dt><dd>{approval.threadId}</dd></div>}
          {approval.turnId && <div><dt>Turn ID</dt><dd>{approval.turnId}</dd></div>}
          {approval.itemId && <div><dt>操作 ID</dt><dd>{approval.itemId}</dd></div>}
          {approval.startedAtMs !== undefined && <div><dt>请求时间</dt><dd>{new Date(approval.startedAtMs).toLocaleString()}</dd></div>}
          {approval.networkApprovalContext !== undefined && <div><dt>网络目标</dt><dd>{formatApprovalValue(approval.networkApprovalContext)}</dd></div>}
          {approval.commandActions !== undefined && <div><dt>解析动作</dt><dd>{formatApprovalValue(approval.commandActions)}</dd></div>}
          {approval.changes !== undefined && <div><dt>文件变更</dt><dd>{formatApprovalValue(approval.changes)}</dd></div>}
        </dl>
        <p className="approval-scope-note">“本次连接允许”可能让后续同类操作不再逐次询问，请只在目标和范围明确时使用。</p>
        <div className="approval-actions">
          <button className="secondary" autoFocus disabled={busy} onClick={() => onDecision("decline")}>拒绝</button>
          <button className="secondary" disabled={busy} onClick={() => onDecision("acceptForSession")}>本次连接允许</button>
          <button className="primary" disabled={busy} onClick={() => onDecision("accept")}>{busy ? <><Spinner />提交中…</> : "允许一次"}</button>
        </div>
      </section>
    </div>
  );
}
