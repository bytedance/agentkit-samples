import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { isImeComposerKey } from "../composer-keyboard";
import { useDismissibleMenu } from "../hooks/useDismissibleMenu";
import {
  activeSkillMention,
  composerSkillDisplay,
  composerValueWithSkills,
  insertSkillMention,
  skillMenuItems,
} from "../skill-mentions";
import { slashMenuItems, type SlashMenuItem } from "../slash-commands";
import type { ModelSummary, SkillSummary } from "../types";
import type { ConnectionState } from "../ui-types";
import {
  ArrowUpIcon,
  CheckIcon,
  ChevronIcon,
  CloseIcon,
  FolderIcon,
  ModelIcon,
  PaperclipIcon,
  PlusIcon,
  ShieldIcon,
  SkillIcon,
} from "./ui";

type ComposerMenuItem =
  | SlashMenuItem
  | { kind: "skill"; skill: SkillSummary };

interface ComposerProps {
  value: string;
  session: boolean;
  connectionState: ConnectionState;
  running: boolean;
  switchingThread: boolean;
  models: ModelSummary[];
  modelsLoading: boolean;
  currentModel?: string;
  skills: SkillSummary[];
  skillsLoading: boolean;
  skillsLoaded: boolean;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  onRequestModels: () => void;
  onRequestSkills: () => void;
  onSelectSkill: (skill: SkillSummary) => void;
  onChangeModel: (model: string) => void;
  onInterrupt: () => void;
  onConnect: () => void;
  onOpenPermissions: () => void;
  onOpenWorkspace: () => void;
  onUploadFiles: (files: FileList) => void;
  uploadBusy: boolean;
  workspaceLocked: boolean;
}

export function Composer({
  value,
  session,
  connectionState,
  running,
  switchingThread,
  models,
  modelsLoading,
  currentModel,
  skills,
  skillsLoading,
  skillsLoaded,
  onChange,
  onSubmit,
  onRequestModels,
  onRequestSkills,
  onSelectSkill,
  onChangeModel,
  onInterrupt,
  onConnect,
  onOpenPermissions,
  onOpenWorkspace,
  onUploadFiles,
  uploadBusy,
  workspaceLocked,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const compositionActiveRef = useRef(false);
  const compositionJustEndedRef = useRef(false);
  const compositionTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [menuDismissed, setMenuDismissed] = useState(false);
  const [actionMenuOpen, setActionMenuOpen] = useState(false);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const actionMenuRef = useDismissibleMenu<HTMLDivElement>(actionMenuOpen, setActionMenuOpen);
  const modelMenuRef = useDismissibleMenu<HTMLDivElement>(modelMenuOpen, setModelMenuOpen);
  const available = session && connectionState === "connected" && !switchingThread;
  const composerDisplay = useMemo(
    () => composerSkillDisplay(value, skills.map((skill) => skill.name)),
    [skills, value],
  );
  const mention = useMemo(() => activeSkillMention(value), [value]);
  const skillItems = useMemo(() => skillMenuItems(mention, skills), [mention, skills]);
  const slashItems = useMemo(() => slashMenuItems(value, models), [models, value]);
  const menuItems = useMemo<ComposerMenuItem[]>(
    () => mention
      ? skillItems.map((skill) => ({ kind: "skill", skill }))
      : slashItems,
    [mention, skillItems, slashItems],
  );
  const skillMode = mention !== undefined;
  const modelMode = /^\/model\s/.test(value);
  const menuVisible = !menuDismissed && !running && available && (
    skillMode
      ? (!skillsLoaded || menuItems.length > 0)
      : value.startsWith("/") &&
        !value.includes("\n") &&
        (menuItems.length > 0 || modelMode)
  );

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [value]);

  useEffect(() => {
    setSelectedIndex(0);
    setMenuDismissed(false);
  }, [value]);

  useEffect(() => {
    if (modelMode && models.length === 0) onRequestModels();
  }, [modelMode, models.length, onRequestModels]);

  useEffect(() => {
    if (skillMode && !skillsLoaded && !skillsLoading) onRequestSkills();
  }, [skillMode, skillsLoaded, skillsLoading, onRequestSkills]);

  useEffect(() => () => {
    if (compositionTimerRef.current) clearTimeout(compositionTimerRef.current);
  }, []);

  const chooseItem = (item: ComposerMenuItem) => {
    if (item.kind === "skill") {
      if (!mention) return;
      onSelectSkill(item.skill);
      onChange(insertSkillMention(value, mention, item.skill));
      queueMicrotask(() => textareaRef.current?.focus());
      return;
    }
    if (item.kind === "model") {
      onSubmit(`/model ${item.model.id}`);
      return;
    }
    if (item.command.name === "model") {
      onChange("/model ");
      onRequestModels();
      queueMicrotask(() => textareaRef.current?.focus());
      return;
    }
    onSubmit(`/${item.command.name}`);
  };

  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isImeComposerKey(
      {
        key: event.key,
        isComposing: event.nativeEvent.isComposing,
        keyCode: event.nativeEvent.keyCode,
      },
      compositionActiveRef.current,
      compositionJustEndedRef.current,
    )) {
      return;
    }
    if (menuVisible) {
      if (event.key === "ArrowDown" || (event.key === "Tab" && !event.shiftKey)) {
        event.preventDefault();
        setSelectedIndex((current) => menuItems.length ? (current + 1) % menuItems.length : 0);
        return;
      }
      if (event.key === "ArrowUp" || (event.key === "Tab" && event.shiftKey)) {
        event.preventDefault();
        setSelectedIndex((current) => menuItems.length ? (current - 1 + menuItems.length) % menuItems.length : 0);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setMenuDismissed(true);
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        const item = menuItems[selectedIndex];
        if (item) chooseItem(item);
        return;
      }
    }
    if (
      event.key === "Backspace" &&
      !composerDisplay.content &&
      composerDisplay.skillNames.length > 0
    ) {
      event.preventDefault();
      onChange(composerValueWithSkills("", composerDisplay.skillNames.slice(0, -1)));
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit(value);
    }
  };

  const compositionStart = () => {
    compositionActiveRef.current = true;
    compositionJustEndedRef.current = false;
    if (compositionTimerRef.current) clearTimeout(compositionTimerRef.current);
  };

  const compositionEnd = () => {
    compositionActiveRef.current = false;
    compositionJustEndedRef.current = true;
    if (compositionTimerRef.current) clearTimeout(compositionTimerRef.current);
    compositionTimerRef.current = setTimeout(() => {
      compositionJustEndedRef.current = false;
      compositionTimerRef.current = undefined;
    }, 0);
  };

  return (
    <div className="composer-wrap">
      {menuVisible && (
        <div className="slash-menu" role="listbox" aria-label={skillMode ? "选择 Skill" : modelMode ? "选择模型" : "快捷命令"}>
          <div className="slash-menu-title"><span>{skillMode ? "可用 Skills" : modelMode ? "可用模型" : "快捷指令"}</span>{modelMode && currentModel && <small>当前：{currentModel}</small>}</div>
          <div className="slash-menu-items">
            {menuItems.map((item, index) => (
              <button
                type="button"
                role="option"
                aria-selected={index === selectedIndex}
                className={index === selectedIndex ? "selected" : ""}
                key={item.kind === "command"
                  ? `command:${item.command.name}`
                  : item.kind === "model"
                    ? `model:${item.model.id}`
                    : `skill:${item.skill.id}`}
                onMouseEnter={() => setSelectedIndex(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => chooseItem(item)}
              >
                <span className="slash-item-icon">{item.kind === "command" ? "/" : item.kind === "skill" ? "$" : "◇"}</span>
                <span className="slash-item-copy">
                  <strong>{item.kind === "command" ? item.command.usage : item.kind === "skill" ? `$${item.skill.name}` : item.model.displayName}</strong>
                  <small>{item.kind === "command" ? item.command.description : item.kind === "skill" ? item.skill.description : item.model.description || item.model.id}</small>
                </span>
                {item.kind === "model" && item.model.isDefault && <span className="model-default">默认</span>}
                {index === selectedIndex && <span className="select-return">↵</span>}
              </button>
            ))}
            {modelMode && modelsLoading && <div className="slash-menu-empty">正在读取模型列表…</div>}
            {modelMode && !modelsLoading && menuItems.length === 0 && <div className="slash-menu-empty">没有匹配的模型，也可以直接输入模型 ID。</div>}
            {skillMode && !skillsLoaded && <div className="slash-menu-empty">正在发现当前工作区的 Skills…</div>}
          </div>
          <div className="slash-menu-help"><span><kbd>Tab</kbd> 切换</span><span><kbd>↑↓</kbd> 移动</span><span><kbd>Enter</kbd> 选择</span><span><kbd>Esc</kbd> 退出</span></div>
        </div>
      )}
      <div className={`composer ${!available ? "disabled" : ""}`}>
        <div className="composer-input-row">
          {composerDisplay.skillNames.length > 0 && (
            <div className="composer-skill-pills">
              {composerDisplay.skillNames.map((name) => (
                <span className="composer-skill-pill" key={name}>
                  <SkillIcon />
                  <strong>{name}</strong>
                  <button
                    type="button"
                    aria-label={`移除 Skill ${name}`}
                    onClick={() => {
                      onChange(composerValueWithSkills(
                        composerDisplay.content,
                        composerDisplay.skillNames.filter((candidate) => candidate !== name),
                      ));
                      queueMicrotask(() => textareaRef.current?.focus());
                    }}
                  >
                    <CloseIcon />
                  </button>
                </span>
              ))}
            </div>
          )}
          <textarea ref={textareaRef} value={composerDisplay.content} disabled={!available || running} aria-label="给 Codex 发消息" onChange={(event) => onChange(composerValueWithSkills(event.target.value, composerDisplay.skillNames))} onCompositionStart={compositionStart} onCompositionEnd={compositionEnd} onKeyDown={keyDown} placeholder={!session ? "先连接一个 Sandbox" : switchingThread ? "正在创建新对话…" : connectionState === "reconnecting" ? "正在恢复事件连接…" : running ? "Codex 正在工作…" : "给 Codex 发消息…"} rows={1} />
        </div>
        <div className="composer-footer">
          <div className="composer-left-tools">
            <div className="composer-popover-anchor" ref={actionMenuRef}>
              <button className={`composer-tool-button add ${actionMenuOpen ? "active" : ""}`} disabled={!available || running} onClick={() => { setActionMenuOpen((current) => !current); setModelMenuOpen(false); }} aria-label="添加"><PlusIcon /></button>
              {actionMenuOpen && (
                <div className="composer-popover action-popover">
                  <button disabled={uploadBusy} onClick={() => fileInputRef.current?.click()}><PaperclipIcon /><span><strong>{uploadBusy ? "正在上传…" : "上传文件"}</strong><small>保存到当前沙箱工作目录</small></span></button>
                </div>
              )}
              <input ref={fileInputRef} className="visually-hidden" type="file" multiple onChange={(event) => { if (event.target.files?.length) onUploadFiles(event.target.files); event.target.value = ""; setActionMenuOpen(false); }} />
            </div>
            {session && (
              <>
                <button
                  className="composer-setting-button"
                  disabled={!available}
                  onClick={() => {
                    setActionMenuOpen(false);
                    setModelMenuOpen(false);
                    onOpenPermissions();
                  }}
                >
                  <ShieldIcon /><span>权限管理</span>
                </button>
                <button
                  className={`composer-setting-button ${workspaceLocked ? "locked" : ""}`}
                  disabled={!available}
                  onClick={() => {
                    setActionMenuOpen(false);
                    setModelMenuOpen(false);
                    onOpenWorkspace();
                  }}
                  title={workspaceLocked ? "当前对话已经开始，工作空间已锁定" : "选择当前对话的工作空间"}
                >
                  <FolderIcon /><span>工作空间</span>
                </button>
              </>
            )}
            <span className="composer-command-hint">输入 / 使用快捷命令，输入 $ 调用 Skill</span>
          </div>
          <div className="composer-right-tools">
            {session && (
              <div className="composer-popover-anchor model-anchor" ref={modelMenuRef}>
                <button className={`model-picker-trigger ${modelMenuOpen ? "active" : ""}`} disabled={!available || running} onClick={() => { setModelMenuOpen((current) => !current); setActionMenuOpen(false); onRequestModels(); }}>
                  <ModelIcon /><span>{currentModel || "选择模型"}</span><ChevronIcon open={modelMenuOpen} />
                </button>
                {modelMenuOpen && (
                  <div className="composer-popover model-popover">
                    <div className="popover-title">可用模型 <small>{models.length}</small></div>
                    <div className="model-popover-list">
                      {models.map((model) => (
                        <button key={model.id} className={model.id === currentModel ? "active" : ""} onClick={() => { setModelMenuOpen(false); onChangeModel(model.id); }}>
                          <span><strong>{model.displayName}</strong><small>{model.description || model.id}</small></span>
                          {model.id === currentModel ? <CheckIcon /> : model.isDefault ? <em>默认</em> : null}
                        </button>
                      ))}
                      {modelsLoading && <div className="popover-empty">正在读取模型…</div>}
                      {!modelsLoading && models.length === 0 && <div className="popover-empty">没有可用模型</div>}
                    </div>
                  </div>
                )}
              </div>
            )}
            {running ? (
              <button className="stop-button" onClick={onInterrupt}><span />停止</button>
            ) : session ? (
              <button className="send-button" disabled={!available || !value.trim()} onClick={() => onSubmit(value)} aria-label="发送"><ArrowUpIcon /></button>
            ) : (
              <button className="connect-mini" onClick={onConnect}>连接</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
