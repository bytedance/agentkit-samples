import { useEffect, useState, type ReactNode } from "react";
import { messageOf } from "../../display";
import type {
  ApprovalPolicy,
  ApprovalsReviewer,
  ConnectedSession,
  PermissionSettings,
  SandboxMode,
} from "../../types";
import {
  AlertIcon,
  CheckIcon,
  CloseIcon,
  ShieldIcon,
  Spinner,
} from "../ui";

interface PermissionsDialogProps {
  session: ConnectedSession;
  disabled: boolean;
  onSave: (settings: PermissionSettings) => Promise<void>;
  onClose: () => void;
}

interface Choice<T extends string> {
  value: T;
  label: string;
  description: string;
  danger?: boolean;
}

const SANDBOX_CHOICES: Choice<SandboxMode>[] = [
  {
    value: "read-only",
    label: "read-only",
    description: "只允许读取文件；任何写入都需要提升权限。",
  },
  {
    value: "workspace-write",
    label: "workspace-write",
    description: "允许写入当前工作目录，访问其他位置时请求提升权限。",
  },
  {
    value: "danger-full-access",
    label: "danger-full-access",
    description: "不限制文件系统和网络访问，请仅在可信任务中使用。",
    danger: true,
  },
];

const APPROVAL_CHOICES: Choice<ApprovalPolicy>[] = [
  {
    value: "untrusted",
    label: "untrusted",
    description: "只有已知安全的只读命令自动执行，其余操作请求审批。",
  },
  {
    value: "on-request",
    label: "on-request",
    description: "Codex 在需要突破沙箱限制时主动请求审批。",
  },
  {
    value: "never",
    label: "never",
    description: "永不请求人工审批；被沙箱阻止的操作会直接失败。",
    danger: true,
  },
];

const REVIEWER_CHOICES: Choice<ApprovalsReviewer>[] = [
  {
    value: "user",
    label: "user",
    description: "所有审批请求都交给你决定。",
  },
  {
    value: "auto_review",
    label: "auto_review",
    description: "由 Codex 风险审查器自动判断是否批准检测到的风险操作。",
  },
];

export function PermissionsDialog({
  session,
  disabled,
  onSave,
  onClose,
}: PermissionsDialogProps) {
  const [sandboxMode, setSandboxMode] = useState<SandboxMode>(
    session.sandboxMode ?? "workspace-write",
  );
  const [approvalPolicy, setApprovalPolicy] = useState<ApprovalPolicy>(
    session.approvalPolicy ?? "on-request",
  );
  const [approvalsReviewer, setApprovalsReviewer] = useState<ApprovalsReviewer>(
    session.approvalsReviewer ?? "user",
  );
  const [networkAccess, setNetworkAccess] = useState(session.networkAccess ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const effectiveNetworkAccess = sandboxMode === "danger-full-access"
    ? true
    : networkAccess;

  useEffect(() => {
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [onClose, saving]);

  const save = async () => {
    setSaving(true);
    setError(undefined);
    try {
      await onSave({
        sandboxMode,
        approvalPolicy,
        approvalsReviewer,
        networkAccess: effectiveNetworkAccess,
      });
      onClose();
    } catch (saveError) {
      setError(messageOf(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-layer">
      <button
        className="modal-backdrop"
        onClick={saving ? undefined : onClose}
        aria-label="关闭权限管理"
      />
      <section
        className="connection-dialog permissions-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="permissions-dialog-title"
      >
        <div className="dialog-accent" />
        <div className="dialog-head">
          <div className="dialog-icon"><ShieldIcon /></div>
          <div>
            <div className="eyebrow">AGENTKIT SESSION · CONFIG.TOML</div>
            <h2 id="permissions-dialog-title">权限管理</h2>
          </div>
          <button className="icon-button" onClick={onClose} disabled={saving} aria-label="关闭权限管理"><CloseIcon /></button>
        </div>

        <p className="permissions-intro">
          设置会写入当前远程 Session 的 Codex 配置，并热加载到这个 Session 中的对话。
        </p>

        <PermissionChoiceGroup
          label="Sandbox mode"
          description="决定 Codex 可以访问和修改哪些文件。"
          choices={SANDBOX_CHOICES}
          value={sandboxMode}
          disabled={saving || disabled}
          onChange={setSandboxMode}
        />
        <PermissionChoiceGroup
          label="Approval policy"
          description="决定 Codex 在什么情况下发起审批。"
          choices={APPROVAL_CHOICES}
          value={approvalPolicy}
          disabled={saving || disabled}
          onChange={setApprovalPolicy}
        />
        <PermissionChoiceGroup
          label="Approvals reviewer"
          description="决定审批请求由谁处理。"
          choices={REVIEWER_CHOICES}
          value={approvalsReviewer}
          disabled={saving || disabled}
          onChange={setApprovalsReviewer}
        />

        <label className={`permission-network ${sandboxMode === "danger-full-access" ? "disabled" : ""}`}>
          <span><strong>允许网络访问</strong><small>写入 sandbox_workspace_write.network_access。</small></span>
          <input
            type="checkbox"
            checked={effectiveNetworkAccess}
            onChange={(event) => setNetworkAccess(event.target.checked)}
            disabled={saving || disabled || sandboxMode === "danger-full-access"}
          />
        </label>

        {sandboxMode === "danger-full-access" && (
          <div className="workspace-danger-note">
            <AlertIcon />
            <span><strong>完全访问会绕过 Codex 文件系统与网络沙箱。</strong>如果同时选择 <code>never</code>，命令和文件修改不会再弹出人工审批。</span>
          </div>
        )}
        {disabled && (
          <div className="workspace-settings-note">
            当前任务仍在运行，请等待完成或先停止任务再修改权限。
          </div>
        )}
        {error && <div className="form-error"><AlertIcon />{error}</div>}

        <div className="dialog-actions workspace-settings-actions">
          <button className="secondary" onClick={onClose} disabled={saving}>取消</button>
          <button className="primary" onClick={() => void save()} disabled={saving || disabled}>
            {saving ? <><Spinner />正在保存…</> : "保存 Session 权限"}
          </button>
        </div>
      </section>
    </div>
  );
}

function PermissionChoiceGroup<T extends string>({
  label,
  description,
  choices,
  value,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  choices: Choice<T>[];
  value: T;
  disabled: boolean;
  onChange: (value: T) => void;
}): ReactNode {
  return (
    <fieldset className="permission-choice-group" disabled={disabled}>
      <legend><strong>{label}</strong><small>{description}</small></legend>
      <div className="permission-choice-list">
        {choices.map((choice) => (
          <button
            type="button"
            key={choice.value}
            className={`${value === choice.value ? "active" : ""} ${choice.danger ? "danger" : ""}`}
            onClick={() => onChange(choice.value)}
            aria-pressed={value === choice.value}
          >
            <span><strong>{choice.label}</strong><small>{choice.description}</small></span>
            {value === choice.value && <CheckIcon />}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
