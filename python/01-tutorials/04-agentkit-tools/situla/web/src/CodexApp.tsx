import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  answerApproval,
  archiveThread,
  closeSession,
  compactThread,
  connectSession,
  forkThread,
  getSessionStatus,
  interruptTurn,
  listSandboxDirectories,
  listModels,
  listSkills,
  listThreads,
  newThread,
  resumeThread,
  selectModel,
  sendTurn,
  updateSessionPermissions,
  updateWorkspaceSettings,
  uploadSandboxFile,
} from "./api";
import {
  applyDelta,
  applyExecutionUpdate,
  applyTokenUsage,
  applyTurnCompleted,
  applyTurnError,
  applyTurnStarted,
  failStreamingMessages,
} from "./event-state";
import { skillDisplayParts, skillIdsForText } from "./skill-mentions";
import {
  SLASH_COMMANDS,
  parseSlashInvocation,
  type SlashCommandName,
} from "./slash-commands";
import { ChatPanel } from "./components/ChatPanel";
import { Composer } from "./components/Composer";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { ApprovalDialog } from "./components/dialogs/ApprovalDialog";
import { ConnectionDialog } from "./components/dialogs/ConnectionDialog";
import { PermissionsDialog } from "./components/dialogs/PermissionsDialog";
import { WorkspaceDialog } from "./components/dialogs/WorkspaceDialog";
import { Spinner } from "./components/ui";
import { messageOf, shortId } from "./display";
import { useMessageScroll } from "./hooks/useMessageScroll";
import { useTheme } from "./hooks/useTheme";
import type {
  AgentkitTool,
  ApprovalDecision,
  BridgeEvent,
  BrowserApproval,
  ChatMessage,
  ConnectedSession,
  ConnectInput,
  HistoryMessage,
  ModelSummary,
  PermissionSettings,
  SessionStatus,
  SkillSummary,
  ThreadRuntimeSettings,
  ThreadSnapshot,
  ThreadSummary,
  WorkspaceSettings,
} from "./types";
import type { ConnectionState } from "./ui-types";
import {
  CODEX_LAUNCH_STORAGE_KEY,
  readCodexLaunch,
  type CodexWorkspaceLaunch,
} from "./workspace-launch";
const TerminalDialog = lazy(async () => ({
  default: (await import("./TerminalDialog")).TerminalDialog,
}));
const BrowserDialog = lazy(async () => ({
  default: (await import("./BrowserDialog")).BrowserDialog,
}));

export function CodexApp(): ReactNode {
  const [codexLaunch] = useState<CodexWorkspaceLaunch | undefined>(() => readCodexLaunch());
  const [session, setSession] = useState<ConnectedSession>();
  const [connectionState, setConnectionState] = useState<ConnectionState>("offline");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [approvals, setApprovals] = useState<BrowserApproval[]>([]);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isSwitchingThread, setIsSwitchingThread] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string>();
  const [showConnect, setShowConnect] = useState(false);
  const [showPermissions, setShowPermissions] = useState(false);
  const [showWorkspace, setShowWorkspace] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [threadCursor, setThreadCursor] = useState<string>();
  const [threadSearch, setThreadSearch] = useState("");
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsLoaded, setSkillsLoaded] = useState(false);
  const selectedTool = useMemo<AgentkitTool | undefined>(() => codexLaunch ? {
    toolId: codexLaunch.toolId,
    name: codexLaunch.toolName,
    status: "Ready",
    ...(codexLaunch.toolType ? { toolType: codexLaunch.toolType } : {}),
  } : undefined, [codexLaunch]);
  const [showTerminal, setShowTerminal] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [terminalShellId, setTerminalShellId] = useState<string>();
  const [uploadBusy, setUploadBusy] = useState(false);
  const messageScroll = useMessageScroll(messages);
  const eventSourceRef = useRef<EventSource | undefined>(undefined);
  const turnLockedRef = useRef(false);
  const threadLockedRef = useRef(false);
  const connectionLockedRef = useRef(false);
  const approvalLockedRef = useRef(false);
  const decidingApprovalIdRef = useRef<string | undefined>(undefined);
  const eventSessionRef = useRef<string | undefined>(undefined);
  const lastEventIdRef = useRef(0);
  const threadListRequestRef = useRef(0);
  const modelsSessionRef = useRef<string | undefined>(undefined);
  const skillsSessionRef = useRef<string | undefined>(undefined);
  const skillsGenerationRef = useRef(0);
  const selectedSkillIdsRef = useRef(new Map<string, string>());
  const workspaceLaunchAttemptedRef = useRef(false);
  const currentSessionIdRef = useRef<string | undefined>(undefined);
  const modelsRequestRef = useRef<{
    sessionId: string;
    promise: Promise<ModelSummary[]>;
  } | undefined>(undefined);
  const skillsRequestRef = useRef<{
    sessionId: string;
    promise: Promise<SkillSummary[]>;
  } | undefined>(undefined);
  const refreshThreadsRef = useRef<() => void>(() => undefined);

  const handleEvent = useCallback(
    (event: BridgeEvent) => {
      if (event.type === "ready") {
        setConnectionState("connected");
        setSession((current) => {
          if (!current) return current;
          return {
            ...current,
            threadId: event.threadId,
            messages: event.messages,
            ...(event.model ? { model: event.model } : {}),
            ...(event.cwd ? { cwd: event.cwd } : {}),
            ...runtimeSettings(event),
          };
        });
        setMessages(completeHistory(event.messages));
        return;
      }
      if (event.type === "thread_changed") {
        skillsGenerationRef.current += 1;
        skillsSessionRef.current = undefined;
        skillsRequestRef.current = undefined;
        selectedSkillIdsRef.current.clear();
        setSkills([]);
        setSkillsLoaded(false);
        setSkillsLoading(false);
        setSession((current) => current && {
          ...current,
          threadId: event.threadId,
          messages: event.messages,
          ...(event.model ? { model: event.model } : {}),
          ...(event.cwd ? { cwd: event.cwd } : {}),
          ...runtimeSettings(event),
        });
        setMessages(completeHistory(event.messages));
        refreshThreadsRef.current();
        return;
      }
      if (event.type === "turn_started") {
        turnLockedRef.current = true;
        setIsRunning(true);
        setMessages((current) => applyTurnStarted(current, event));
        return;
      }
      if (event.type === "delta") {
        setMessages((current) => applyDelta(current, event));
        return;
      }
      if (event.type === "turn_completed") {
        turnLockedRef.current = false;
        setIsRunning(false);
        setMessages((current) => applyTurnCompleted(current, event));
        refreshThreadsRef.current();
        return;
      }
      if (event.type === "token_usage") {
        setMessages((current) => applyTokenUsage(current, event));
        return;
      }
      if (event.type === "execution_update") {
        setMessages((current) => applyExecutionUpdate(current, event));
        return;
      }
      if (event.type === "turn_error") {
        turnLockedRef.current = false;
        setIsRunning(false);
        setMessages((current) => applyTurnError(current, event));
        return;
      }
      if (event.type === "notification") {
        if (event.method === "skills/changed") {
          skillsGenerationRef.current += 1;
          skillsSessionRef.current = undefined;
          skillsRequestRef.current = undefined;
          selectedSkillIdsRef.current.clear();
          setSkills([]);
          setSkillsLoaded(false);
          setSkillsLoading(false);
        }
        return;
      }
      if (event.type === "approval_requested") {
        setApprovals((current) =>
          current.some((approval) => approval.id === event.approval.id)
            ? current
            : [...current, event.approval],
        );
        return;
      }
      if (event.type === "approval_resolved") {
        if (!decidingApprovalIdRef.current) {
          approvalLockedRef.current = false;
          setApprovalBusy(false);
        }
        setApprovals((current) =>
          current.filter((approval) => approval.id !== event.approvalId),
        );
        return;
      }
      if (event.type === "closed") {
        currentSessionIdRef.current = undefined;
        threadListRequestRef.current += 1;
        turnLockedRef.current = false;
        threadLockedRef.current = false;
        approvalLockedRef.current = false;
        decidingApprovalIdRef.current = undefined;
        setIsRunning(false);
        setIsSwitchingThread(false);
        setApprovalBusy(false);
        setApprovals([]);
        setMessages((current) => failStreamingMessages(current));
        setConnectionState("offline");
        setSession(undefined);
        skillsGenerationRef.current += 1;
        skillsSessionRef.current = undefined;
        skillsRequestRef.current = undefined;
        selectedSkillIdsRef.current.clear();
        setSkills([]);
        setSkillsLoaded(false);
        setSkillsLoading(false);
        setShowConnect(false);
        setShowBrowser(false);
        setError(event.reason ?? "Codex app-server 连接已关闭");
      }
    },
    [],
  );

  const sessionId = session?.id;
  currentSessionIdRef.current = sessionId;

  const refreshThreads = useCallback(async () => {
    const requestId = ++threadListRequestRef.current;
    if (!sessionId) {
      setThreads([]);
      setThreadCursor(undefined);
      return;
    }
    setThreadsLoading(true);
    try {
      const page = await listThreads(sessionId, {
        ...(threadSearch.trim() ? { search: threadSearch.trim() } : {}),
      });
      if (requestId !== threadListRequestRef.current) return;
      setThreads(page.data);
      setThreadCursor(page.nextCursor);
    } catch (listError) {
      if (requestId === threadListRequestRef.current) setError(messageOf(listError));
    } finally {
      if (requestId === threadListRequestRef.current) setThreadsLoading(false);
    }
  }, [sessionId, threadSearch]);

  const loadMoreThreads = useCallback(async () => {
    if (!sessionId || !threadCursor || threadsLoading) return;
    const requestId = ++threadListRequestRef.current;
    setThreadsLoading(true);
    try {
      const page = await listThreads(sessionId, {
        cursor: threadCursor,
        ...(threadSearch.trim() ? { search: threadSearch.trim() } : {}),
      });
      if (requestId !== threadListRequestRef.current) return;
      setThreads((current) => mergeThreads(current, page.data));
      setThreadCursor(page.nextCursor);
    } catch (listError) {
      if (requestId === threadListRequestRef.current) setError(messageOf(listError));
    } finally {
      if (requestId === threadListRequestRef.current) setThreadsLoading(false);
    }
  }, [sessionId, threadCursor, threadSearch, threadsLoading]);

  const ensureModels = useCallback(async (): Promise<ModelSummary[]> => {
    if (!sessionId) return [];
    if (modelsSessionRef.current === sessionId && models.length > 0) return models;
    if (modelsRequestRef.current?.sessionId === sessionId) {
      return modelsRequestRef.current.promise;
    }
    setModelsLoading(true);
    const request = listModels(sessionId)
      .then((result) => {
        if (sessionId !== currentSessionIdRef.current) return [];
        modelsSessionRef.current = sessionId;
        setModels(result.data);
        return result.data;
      })
      .catch((modelError: unknown) => {
        if (sessionId === currentSessionIdRef.current) setError(messageOf(modelError));
        return [];
      })
      .finally(() => {
        if (modelsRequestRef.current?.promise === request) {
          modelsRequestRef.current = undefined;
        }
        if (sessionId === currentSessionIdRef.current) setModelsLoading(false);
      });
    modelsRequestRef.current = { sessionId, promise: request };
    return request;
  }, [models, sessionId]);

  const ensureSkills = useCallback(async (): Promise<SkillSummary[]> => {
    if (!sessionId) return [];
    if (skillsSessionRef.current === sessionId && skillsLoaded) return skills;
    if (skillsRequestRef.current?.sessionId === sessionId) {
      return skillsRequestRef.current.promise;
    }
    const generation = skillsGenerationRef.current;
    setSkillsLoading(true);
    const request = listSkills(sessionId)
      .then((result) => {
        if (
          sessionId !== currentSessionIdRef.current ||
          generation !== skillsGenerationRef.current
        ) {
          return [];
        }
        skillsSessionRef.current = sessionId;
        setSkills(result.data);
        setSkillsLoaded(true);
        return result.data;
      })
      .catch((skillError: unknown) => {
        if (
          sessionId === currentSessionIdRef.current &&
          generation === skillsGenerationRef.current
        ) {
          setSkillsLoaded(true);
          setError(messageOf(skillError));
        }
        return [];
      })
      .finally(() => {
        if (skillsRequestRef.current?.promise === request) {
          skillsRequestRef.current = undefined;
        }
        if (
          sessionId === currentSessionIdRef.current &&
          generation === skillsGenerationRef.current
        ) {
          setSkillsLoading(false);
        }
      });
    skillsRequestRef.current = { sessionId, promise: request };
    return request;
  }, [sessionId, skills, skillsLoaded]);

  useEffect(() => {
    if (!sessionId || skillsLoaded || skillsLoading) return;
    const hasSkillMessage = messages.some((message) =>
      message.role === "user" &&
      (
        Boolean(message.skillNames?.length) ||
        skillDisplayParts(message.content, []).skillNames.length > 0
      ));
    if (hasSkillMessage) void ensureSkills();
  }, [ensureSkills, messages, sessionId, skillsLoaded, skillsLoading]);

  refreshThreadsRef.current = () => {
    void refreshThreads();
  };

  useEffect(() => {
    const timer = setTimeout(() => void refreshThreads(), 220);
    return () => clearTimeout(timer);
  }, [refreshThreads]);

  useEffect(() => {
    eventSourceRef.current?.close();
    if (!sessionId) return;
    if (eventSessionRef.current !== sessionId) {
      eventSessionRef.current = sessionId;
      lastEventIdRef.current = 0;
    }
    const source = new EventSource(`/api/sessions/${encodeURIComponent(sessionId)}/events`);
    eventSourceRef.current = source;
    source.onopen = () => {
      if (eventSourceRef.current === source) setConnectionState("connected");
    };
    source.onmessage = (message) => {
      try {
        const eventId = Number(message.lastEventId);
        if (Number.isSafeInteger(eventId) && eventId > 0) {
          if (eventId <= lastEventIdRef.current) return;
          lastEventIdRef.current = eventId;
        }
        handleEvent(JSON.parse(message.data) as BridgeEvent);
      } catch {
        setError("收到了无法解析的 bridge 事件");
      }
    };
    source.onerror = () => {
      if (eventSourceRef.current === source) setConnectionState("reconnecting");
    };
    return () => {
      source.close();
      if (eventSourceRef.current === source) eventSourceRef.current = undefined;
    };
  }, [handleEvent, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    const closeOnPageHide = () => {
      void closeSession(sessionId, true).catch(() => undefined);
    };
    window.addEventListener("pagehide", closeOnPageHide);
    return () => window.removeEventListener("pagehide", closeOnPageHide);
  }, [sessionId]);

  const connect = useCallback(async (input: ConnectInput) => {
    if (connectionLockedRef.current) return;
    connectionLockedRef.current = true;
    setConnectionState("connecting");
    setError(undefined);
    const previous = session;
    try {
      const connected = await connectSession({
        ...input,
        ...(input.agentkitSessionId && selectedTool
          ? { agentkitToolId: selectedTool.toolId }
          : {}),
      });
      eventSourceRef.current?.close();
      currentSessionIdRef.current = connected.id;
      threadListRequestRef.current += 1;
      setSession(connected);
      setMessages(completeHistory(connected.messages ?? []));
      setThreads([]);
      setThreadCursor(undefined);
      setModels([]);
      modelsSessionRef.current = undefined;
      modelsRequestRef.current = undefined;
      skillsGenerationRef.current += 1;
      skillsSessionRef.current = undefined;
      skillsRequestRef.current = undefined;
      selectedSkillIdsRef.current.clear();
      setSkills([]);
      setSkillsLoaded(false);
      setSkillsLoading(false);
      setConnectionState("connected");
      setShowConnect(false);
      setShowBrowser(false);
      setTerminalShellId(undefined);
      if (previous && previous.id !== connected.id) {
        await closeSession(previous.id).catch(() => undefined);
      }
    } catch (connectError) {
      setConnectionState(previous ? "connected" : "offline");
      throw connectError;
    } finally {
      connectionLockedRef.current = false;
    }
  }, [selectedTool, session]);

  useEffect(() => {
    if (!codexLaunch || workspaceLaunchAttemptedRef.current) return;
    workspaceLaunchAttemptedRef.current = true;
    void connect({
      agentkitToolId: codexLaunch.toolId,
      agentkitSessionId: codexLaunch.sessionId,
    }).catch((connectError: unknown) => {
      setError(`连接实例 ${shortId(codexLaunch.sessionId)} 失败：${messageOf(connectError)}`);
    });
  }, [codexLaunch, connect]);

  const retryCodexConnection = useCallback(() => {
    if (!codexLaunch) {
      window.location.assign("/");
      return;
    }
    void connect({
      agentkitToolId: codexLaunch.toolId,
      agentkitSessionId: codexLaunch.sessionId,
    }).catch((connectError: unknown) => {
      setError(`连接实例 ${shortId(codexLaunch.sessionId)} 失败：${messageOf(connectError)}`);
    });
  }, [codexLaunch, connect]);

  const applySnapshot = useCallback((snapshot: ThreadSnapshot) => {
    setSession((current) => current && {
      ...current,
      threadId: snapshot.threadId,
      messages: snapshot.messages,
      ...(snapshot.model ? { model: snapshot.model } : {}),
      ...(snapshot.cwd ? { cwd: snapshot.cwd } : {}),
      ...runtimeSettings(snapshot),
    });
    setMessages(completeHistory(snapshot.messages));
  }, []);

  const submitMessage = async (text = draft) => {
    const content = text.trim();
    if (!content || !session || connectionState !== "connected" || turnLockedRef.current || threadLockedRef.current) return;
    if (content.startsWith("/")) {
      selectedSkillIdsRef.current.clear();
      setDraft("");
      setError(undefined);
      await executeSlash(content);
      return;
    }
    turnLockedRef.current = true;
    setIsRunning(true);
    messageScroll.pinToLatest();
    setDraft("");
    setError(undefined);
    const messageId = crypto.randomUUID();
    const optimisticDisplay = skillDisplayParts(
      content,
      [...selectedSkillIdsRef.current.keys()],
    );
    setMessages((current) => [
      ...current,
      {
        id: messageId,
        role: "user",
        content: optimisticDisplay.content,
        ...(optimisticDisplay.skillNames.length > 0
          ? { skillNames: optimisticDisplay.skillNames }
          : {}),
        state: "complete",
        timestamp: Date.now(),
      },
    ]);
    try {
      const availableSkills = content.includes("$") ? await ensureSkills() : [];
      const skillIds = skillIdsForText(
        content,
        availableSkills,
        selectedSkillIdsRef.current,
      );
      const selectedIds = new Set(skillIds);
      const display = skillDisplayParts(
        content,
        availableSkills
          .filter((skill) => selectedIds.has(skill.id))
          .map((skill) => skill.name),
      );
      if (
        display.content !== optimisticDisplay.content ||
        display.skillNames.join("\0") !== optimisticDisplay.skillNames.join("\0")
      ) {
        setMessages((current) => current.map((message) =>
          message.id === messageId
            ? {
                ...message,
                content: display.content,
                ...(display.skillNames.length > 0
                  ? { skillNames: display.skillNames }
                  : { skillNames: undefined }),
              }
            : message));
      }
      await sendTurn(session.id, content, skillIds);
      selectedSkillIdsRef.current.clear();
    } catch (turnError) {
      turnLockedRef.current = false;
      setIsRunning(false);
      setMessages((current) => current.filter((message) => message.id !== messageId));
      setDraft((current) => current || content);
      setError(messageOf(turnError));
    }
  };

  const startNewThread = useCallback(async () => {
    if (!session || turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      applySnapshot(await newThread(session.id));
      setSidebarOpen(false);
    } catch (threadError) {
      setError(messageOf(threadError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [applySnapshot, session]);

  const addSystemMessage = useCallback((content: string) => {
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "system",
        content,
        state: "complete",
        timestamp: Date.now(),
      },
    ]);
  }, []);

  const switchToThread = useCallback(async (threadId: string) => {
    if (!session || threadId === session.threadId) {
      setSidebarOpen(false);
      return;
    }
    if (turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      applySnapshot(await resumeThread(session.id, threadId));
      setSidebarOpen(false);
    } catch (threadError) {
      setError(messageOf(threadError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [applySnapshot, session]);

  const forkCurrentThread = useCallback(async () => {
    if (!session || turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      applySnapshot(await forkThread(session.id));
      addSystemMessage("已从原对话分叉，新消息不会影响原 thread。");
      setSidebarOpen(false);
    } catch (threadError) {
      setError(messageOf(threadError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [addSystemMessage, applySnapshot, session]);

  const archiveConversation = useCallback(async (threadId: string) => {
    if (!session || turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      const result = await archiveThread(session.id, threadId);
      if (result.threadId && result.thread && result.messages) {
        applySnapshot(result as ThreadSnapshot);
      }
      await refreshThreads();
    } catch (threadError) {
      setError(messageOf(threadError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [applySnapshot, refreshThreads, session]);

  const compactCurrentThread = useCallback(async () => {
    if (!session || turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      await compactThread(session.id);
      addSystemMessage("已开始压缩当前对话；进度会通过 app-server 事件继续返回。");
    } catch (compactError) {
      setError(messageOf(compactError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [addSystemMessage, session]);

  const changeModel = useCallback(async (model: string) => {
    if (!session || turnLockedRef.current || threadLockedRef.current) return;
    threadLockedRef.current = true;
    setIsSwitchingThread(true);
    setError(undefined);
    try {
      const result = await selectModel(session.id, model);
      setSession((current) => current && { ...current, model: result.model });
      addSystemMessage(`当前对话模型已切换为 \`${result.model}\`。`);
    } catch (modelError) {
      setError(messageOf(modelError));
    } finally {
      threadLockedRef.current = false;
      setIsSwitchingThread(false);
    }
  }, [addSystemMessage, session]);

  const showStatus = useCallback(async () => {
    if (!session) return;
    try {
      const status = await getSessionStatus(session.id);
      addSystemMessage(statusText(status));
    } catch (statusError) {
      setError(messageOf(statusError));
    }
  }, [addSystemMessage, session]);

  async function executeSlash(text: string): Promise<void> {
    const invocation = parseSlashInvocation(text);
    if (!invocation || !SLASH_COMMANDS.some((command) => command.name === invocation.name)) {
      setError(`未知快捷命令：${text.split(/\s/, 1)[0]}。输入 /help 查看可用命令。`);
      return;
    }
    const name = invocation.name as SlashCommandName;
    switch (name) {
      case "model":
        if (!invocation.argument) {
          setDraft("/model ");
          await ensureModels();
        } else {
          await changeModel(invocation.argument);
        }
        return;
      case "models": {
        const availableModels = await ensureModels();
        addSystemMessage(modelListText(availableModels, session?.model));
        return;
      }
      case "skills": {
        const availableSkills = await ensureSkills();
        if (availableSkills.length > 0) setDraft("$");
        else addSystemMessage("当前工作区没有可用的 Skill。");
        return;
      }
      case "new":
      case "clear":
        await startNewThread();
        return;
      case "resume":
        if (invocation.argument) await switchToThread(invocation.argument);
        else {
          setSidebarOpen(true);
          await refreshThreads();
        }
        return;
      case "fork":
        await forkCurrentThread();
        return;
      case "compact":
        await compactCurrentThread();
        return;
      case "archive":
        if (session) await archiveConversation(session.threadId);
        return;
      case "status":
        await showStatus();
        return;
      case "help":
        addSystemMessage(helpText());
        return;
    }
  }

  const disconnect = async () => {
    const current = session;
    eventSourceRef.current?.close();
    currentSessionIdRef.current = undefined;
    threadListRequestRef.current += 1;
    setSession(undefined);
    setMessages([]);
    setThreads([]);
    setThreadCursor(undefined);
    setThreadSearch("");
    setModels([]);
    modelsSessionRef.current = undefined;
    modelsRequestRef.current = undefined;
    skillsGenerationRef.current += 1;
    skillsSessionRef.current = undefined;
    skillsRequestRef.current = undefined;
    selectedSkillIdsRef.current.clear();
    setSkills([]);
    setSkillsLoaded(false);
    setSkillsLoading(false);
    setApprovals([]);
    setApprovalBusy(false);
    setIsRunning(false);
    setIsSwitchingThread(false);
    turnLockedRef.current = false;
    threadLockedRef.current = false;
    approvalLockedRef.current = false;
    decidingApprovalIdRef.current = undefined;
    eventSessionRef.current = undefined;
    lastEventIdRef.current = 0;
    setConnectionState("offline");
    setShowConnect(false);
    setShowBrowser(false);
    if (current) await closeSession(current.id).catch(() => undefined);
  };

  const decideApproval = async (decision: ApprovalDecision) => {
    const approval = approvals[0];
    if (!session || !approval || approvalLockedRef.current) return;
    approvalLockedRef.current = true;
    decidingApprovalIdRef.current = approval.id;
    setApprovalBusy(true);
    const currentApproval = approval;
    try {
      await answerApproval(session.id, currentApproval.id, decision);
    } catch (approvalError) {
      setError(messageOf(approvalError));
    } finally {
      if (decidingApprovalIdRef.current === currentApproval.id) {
        approvalLockedRef.current = false;
        decidingApprovalIdRef.current = undefined;
        setApprovalBusy(false);
      }
    }
  };

  const interrupt = async () => {
    if (!session) return;
    try {
      await interruptTurn(session.id);
    } catch (interruptError) {
      setError(messageOf(interruptError));
    }
  };

  const uploadFiles = async (files: FileList) => {
    if (!session || files.length === 0 || uploadBusy) return;
    setUploadBusy(true);
    setError(undefined);
    const directory = (session.cwd || "/home/gem/workspace").replace(/\/+$/, "");
    const uploaded: string[] = [];
    try {
      for (const file of Array.from(files)) {
        const fileName = safeUploadName(file.name);
        const path = `${directory}/${fileName}`;
        await uploadSandboxFile(session.id, file, path);
        uploaded.push(path);
      }
      addSystemMessage(
        uploaded.length === 1
          ? `文件已上传到沙箱：\`${uploaded[0]}\``
          : `已上传 ${uploaded.length} 个文件：\n${uploaded.map((path) => `- \`${path}\``).join("\n")}`,
      );
    } catch (uploadError) {
      setError(messageOf(uploadError));
    } finally {
      setUploadBusy(false);
    }
  };

  const browseDirectories = useCallback(async (path: string) => {
    if (!session) throw new Error("当前没有已连接的实例");
    return listSandboxDirectories(session.id, path);
  }, [session]);

  const saveWorkspaceSettings = useCallback(async (settings: WorkspaceSettings) => {
    if (!session) throw new Error("当前没有已连接的实例");
    const updated = await updateWorkspaceSettings(session.id, settings);
    setSession((current) => current && { ...current, ...updated });
    addSystemMessage([
      "已更新当前对话的工作空间：",
      "",
      `- 工作目录：\`${updated.cwd}\``,
    ].join("\n"));
  }, [addSystemMessage, session]);

  const savePermissionSettings = useCallback(async (settings: PermissionSettings) => {
    if (!session) throw new Error("当前没有已连接的实例");
    const updated = await updateSessionPermissions(session.id, settings);
    setSession((current) => current && { ...current, ...updated });
    addSystemMessage([
      "已更新当前 AgentKit Session 的 Codex 权限：",
      "",
      `- Sandbox：\`${updated.sandboxMode}\``,
      `- 审批策略：\`${updated.approvalPolicy}\``,
      `- 审批处理：\`${updated.approvalsReviewer}\``,
      `- 网络访问：${updated.networkAccess ? "允许" : "禁用"}`,
    ].join("\n"));
  }, [addSystemMessage, session]);

  const title = useMemo(() => conversationTitle(messages), [messages]);
  const workspaceLocked = isRunning || isSwitchingThread ||
    messages.some((message) => message.role === "user" || message.role === "assistant");
  const approval = approvals[0];

  useEffect(() => {
    const keyDown = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "n") {
        if (!session || turnLockedRef.current || threadLockedRef.current) return;
        event.preventDefault();
        void startNewThread();
      }
    };
    window.addEventListener("keydown", keyDown);
    return () => window.removeEventListener("keydown", keyDown);
  }, [session, startNewThread]);

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        title={title}
        session={session}
        busy={isRunning || isSwitchingThread || connectionState === "connecting"}
        threads={threads}
        threadsLoading={threadsLoading}
        hasMoreThreads={Boolean(threadCursor)}
        search={threadSearch}
        onSearch={setThreadSearch}
        onSelectThread={(threadId) => void switchToThread(threadId)}
        onArchiveThread={(threadId) => void archiveConversation(threadId)}
        onLoadMore={() => void loadMoreThreads()}
        onRefresh={() => void refreshThreads()}
        onNewThread={startNewThread}
        onOpenInstanceInfo={() => setShowConnect(Boolean(session))}
        onClose={() => setSidebarOpen(false)}
        selectedTool={selectedTool}
        onLeaveWorkspace={() => {
          void disconnect().then(() => {
            window.sessionStorage.removeItem(CODEX_LAUNCH_STORAGE_KEY);
            if (window.opener && !window.opener.closed) {
              window.opener.focus();
              window.close();
              window.setTimeout(() => window.location.assign("/"), 100);
              return;
            }
            window.location.assign("/");
          });
        }}
      />

      <main className="workspace">
        <Topbar
          title={title}
          session={session}
          theme={theme}
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenConnectionSettings={() => setShowConnect(Boolean(session))}
          onOpenTerminal={() => setShowTerminal(true)}
          onOpenSandboxBrowser={() => setShowBrowser(true)}
          onToggleTheme={toggleTheme}
        />
        <ChatPanel
          messages={messages}
          skills={skills}
          connected={Boolean(session)}
          scrollRef={messageScroll.scrollRef}
          onScroll={messageScroll.onScroll}
          onSuggestion={submitMessage}
          onConnect={retryCodexConnection}
          showJumpToLatest={messageScroll.showJumpToLatest}
          onJumpToLatest={messageScroll.jumpToLatest}
          error={error}
          onDismissError={() => setError(undefined)}
          composer={(
            <Composer
              value={draft}
              session={Boolean(session)}
              connectionState={connectionState}
              running={isRunning}
              switchingThread={isSwitchingThread}
              onChange={setDraft}
              models={models}
              modelsLoading={modelsLoading}
              currentModel={session?.model}
              skills={skills}
              skillsLoading={skillsLoading}
              skillsLoaded={skillsLoaded}
              onRequestModels={ensureModels}
              onRequestSkills={() => void ensureSkills()}
              onSelectSkill={(skill) => {
                selectedSkillIdsRef.current.set(skill.name, skill.id);
              }}
              onChangeModel={(model) => void changeModel(model)}
              onSubmit={(text) => void submitMessage(text)}
              onInterrupt={() => void interrupt()}
              onConnect={retryCodexConnection}
              onOpenPermissions={() => setShowPermissions(true)}
              onOpenWorkspace={() => setShowWorkspace(true)}
              onUploadFiles={(files) => void uploadFiles(files)}
              uploadBusy={uploadBusy}
              workspaceLocked={workspaceLocked}
            />
          )}
        />
      </main>

      {showConnect && session && (
        <ConnectionDialog
          session={session}
          onClose={() => setShowConnect(false)}
        />
      )}
      {showPermissions && session && (
        <PermissionsDialog
          session={session}
          disabled={isRunning || isSwitchingThread}
          onSave={savePermissionSettings}
          onClose={() => setShowPermissions(false)}
        />
      )}
      {showWorkspace && session && (
        <WorkspaceDialog
          session={session}
          locked={workspaceLocked}
          onListDirectories={browseDirectories}
          onSave={saveWorkspaceSettings}
          onClose={() => setShowWorkspace(false)}
        />
      )}
      {showTerminal && session && (
        <Suspense fallback={<div className="modal-layer terminal-layer"><div className="modal-backdrop" /><div className="terminal-loading"><Spinner />正在加载 Terminal…</div></div>}>
          <TerminalDialog
            sessionId={session.id}
            shellSessionId={terminalShellId}
            onShellSessionId={setTerminalShellId}
            onClose={() => setShowTerminal(false)}
          />
        </Suspense>
      )}
      {showBrowser && session && (
        <Suspense fallback={<div className="modal-layer terminal-layer"><div className="modal-backdrop" /><div className="terminal-loading"><Spinner />正在加载沙箱浏览器…</div></div>}>
          <BrowserDialog
            sessionId={session.id}
            onClose={() => setShowBrowser(false)}
          />
        </Suspense>
      )}
      {approval && <ApprovalDialog approval={approval} pendingCount={approvals.length} busy={approvalBusy} onDecision={decideApproval} />}
    </div>
  );
}

function completeHistory(messages: HistoryMessage[]): ChatMessage[] { return messages.map((message) => ({ ...message, state: "complete" })); }
function mergeThreads(current: ThreadSummary[], incoming: ThreadSummary[]): ThreadSummary[] { const merged = new Map(current.map((thread) => [thread.id, thread])); for (const thread of incoming) merged.set(thread.id, thread); return [...merged.values()]; }
function statusText(status: SessionStatus): string { return [`**当前连接状态**`, ``, ...(status.agentkitSession ? [`- AgentKit Session：\`${status.agentkitSession.sessionId}\``] : []), `- Thread：\`${status.threadId}\``, `- Endpoint：\`${status.endpoint}\``, `- 模型：\`${status.model ?? "沙箱默认"}\``, `- 工作目录：\`${status.cwd ?? "沙箱默认"}\``, `- Sandbox：\`${status.sandboxMode ?? "沙箱默认"}\``, `- 审批策略：\`${status.approvalPolicy ?? "沙箱默认"}\``, `- 审批处理：\`${status.approvalsReviewer ?? "沙箱默认"}\``, `- 网络访问：${status.networkAccess === undefined ? "沙箱默认" : status.networkAccess ? "允许" : "禁用"}`, `- 运行状态：${status.active ? "处理中" : "空闲"}`].join("\n"); }
function runtimeSettings(value: ThreadRuntimeSettings): ThreadRuntimeSettings { return { ...(value.approvalPolicy ? { approvalPolicy: value.approvalPolicy } : {}), ...(value.approvalsReviewer ? { approvalsReviewer: value.approvalsReviewer } : {}), ...(value.sandboxMode ? { sandboxMode: value.sandboxMode } : {}), ...(value.networkAccess !== undefined ? { networkAccess: value.networkAccess } : {}) }; }
function modelListText(models: ModelSummary[], current?: string): string { if (models.length === 0) return "app-server 没有返回可用模型。"; return [`**可用模型（${models.length}）**`, ``, ...models.slice(0, 40).map((model) => `- ${model.id === current ? "✓ " : ""}\`${model.id}\`${model.isDefault ? "（默认）" : ""} — ${model.displayName}`), ...(models.length > 40 ? [`- …其余 ${models.length - 40} 个模型请用 \`/model 关键字\` 筛选`] : [])].join("\n"); }
function helpText(): string { return [`**Situla 快捷命令**`, ``, ...SLASH_COMMANDS.map((command) => `- \`${command.usage}\` — ${command.description}`), ``, `输入 \`/\` 后可使用 ↑↓、Tab、Enter 和 Esc 操作命令面板。`].join("\n"); }
function safeUploadName(value: string): string { const normalized = value.replace(/[\\/\0]/g, "_").trim(); return normalized || `upload-${Date.now()}`; }
function conversationTitle(messages: ChatMessage[]): string { const first = messages.find((message) => message.role === "user")?.content.trim(); return first ? (first.length > 22 ? `${first.slice(0, 22)}…` : first) : "新对话"; }
