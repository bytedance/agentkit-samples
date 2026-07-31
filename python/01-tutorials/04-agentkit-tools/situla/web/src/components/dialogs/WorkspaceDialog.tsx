import { useEffect, useState } from "react";
import { messageOf } from "../../display";
import type {
  ConnectedSession,
  DirectoryListing,
  WorkspaceSettings,
} from "../../types";
import {
  AlertIcon,
  ArrowLeftIcon,
  ChevronIcon,
  CloseIcon,
  FolderIcon,
  Spinner,
} from "../ui";

interface WorkspaceDialogProps {
  session: ConnectedSession;
  locked: boolean;
  onListDirectories: (path: string) => Promise<DirectoryListing>;
  onSave: (settings: WorkspaceSettings) => Promise<void>;
  onClose: () => void;
}

export function WorkspaceDialog({
  session,
  locked,
  onListDirectories,
  onSave,
  onClose,
}: WorkspaceDialogProps) {
  const [cwd, setCwd] = useState(session.cwd || "/");
  const [listing, setListing] = useState<DirectoryListing>();
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [onClose, saving]);

  const loadDirectory = async (path: string) => {
    if (directoryLoading || locked) return;
    setDirectoryLoading(true);
    setError(undefined);
    try {
      setListing(await onListDirectories(path));
    } catch (directoryError) {
      setError(
        `无法读取远程目录：${messageOf(directoryError)}。仍可手动输入绝对路径。`,
      );
    } finally {
      setDirectoryLoading(false);
    }
  };

  const save = async () => {
    const normalizedCwd = normalizeDirectory(cwd);
    if (!validAbsolutePath(normalizedCwd)) {
      setError("工作目录必须是远程沙箱中的绝对路径，例如 /home/gem。");
      return;
    }
    setSaving(true);
    setError(undefined);
    try {
      await onSave({ cwd: normalizedCwd });
      onClose();
    } catch (saveError) {
      setError(messageOf(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-layer">
      <button className="modal-backdrop" onClick={saving ? undefined : onClose} aria-label="关闭工作空间" />
      <section className="connection-dialog workspace-dialog" role="dialog" aria-modal="true" aria-labelledby="workspace-dialog-title">
        <div className="dialog-accent" />
        <div className="dialog-head">
          <div className="dialog-icon"><FolderIcon /></div>
          <div><div className="eyebrow">CODEX THREAD · CWD</div><h2 id="workspace-dialog-title">工作空间</h2></div>
          <button className="icon-button" onClick={onClose} disabled={saving} aria-label="关闭工作空间"><CloseIcon /></button>
        </div>

        <p className="permissions-intro">
          为当前对话选择远程沙箱中的默认工作目录。文件不会被移动。
        </p>

        <label className="field">
          <span>远程绝对路径</span>
          <div className="workspace-path-input">
            <input
              value={cwd}
              onChange={(event) => setCwd(event.target.value)}
              placeholder="/home/gem"
              spellCheck={false}
              disabled={saving || locked}
            />
            <button
              type="button"
              onClick={() => void loadDirectory(validAbsolutePath(cwd) ? cwd : "/")}
              disabled={saving || locked}
            >
              浏览
            </button>
          </div>
          <small>第一条消息发出后，当前对话的工作空间会被锁定。</small>
        </label>

        {(listing || directoryLoading) && (
          <div className="directory-browser">
            <div className="directory-browser-toolbar">
              <button type="button" onClick={() => listing?.parent && void loadDirectory(listing.parent)} disabled={!listing?.parent || directoryLoading || locked} aria-label="返回上级目录"><ArrowLeftIcon /></button>
              <code>{listing?.path ?? cwd}</code>
              <button
                type="button"
                onClick={() => {
                  if (listing) setCwd(listing.path);
                  setListing(undefined);
                }}
                disabled={!listing || directoryLoading || locked}
              >
                选择当前目录
              </button>
            </div>
            <div className="directory-browser-list">
              {directoryLoading && <div className="directory-browser-empty"><Spinner />正在读取远程目录…</div>}
              {!directoryLoading && listing?.directories.map((directory) => (
                <button type="button" key={directory.path} onClick={() => void loadDirectory(directory.path)} disabled={locked}>
                  <FolderIcon /><span>{directory.name}</span><ChevronIcon open={false} />
                </button>
              ))}
              {!directoryLoading && listing?.directories.length === 0 && <div className="directory-browser-empty">此目录没有子目录</div>}
            </div>
          </div>
        )}

        {locked && (
          <div className="workspace-settings-note">
            当前对话已经开始，工作空间已锁定。发起新任务后，可在发送第一条消息前重新选择。
          </div>
        )}
        {error && <div className="form-error"><AlertIcon />{error}</div>}

        <div className="dialog-actions workspace-settings-actions">
          <button className="secondary" onClick={onClose} disabled={saving}>取消</button>
          <button className="primary" onClick={() => void save()} disabled={saving || locked}>
            {saving ? <><Spinner />正在保存…</> : "使用此工作空间"}
          </button>
        </div>
      </section>
    </div>
  );
}

function validAbsolutePath(value: string): boolean {
  return value.startsWith("/") && !value.includes("\0");
}

function normalizeDirectory(value: string): string {
  const normalized = value.trim().replace(/\/+/g, "/").replace(/\/+$/, "");
  return normalized || "/";
}
