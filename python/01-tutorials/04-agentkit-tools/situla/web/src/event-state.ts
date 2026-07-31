import type { BridgeEvent, ChatMessage } from "./types.ts";

type TurnStarted = Extract<BridgeEvent, { type: "turn_started" }>;
type Delta = Extract<BridgeEvent, { type: "delta" }>;
type TurnCompleted = Extract<BridgeEvent, { type: "turn_completed" }>;
type TokenUsage = Extract<BridgeEvent, { type: "token_usage" }>;
type ExecutionUpdate = Extract<BridgeEvent, { type: "execution_update" }>;
type TurnError = Extract<BridgeEvent, { type: "turn_error" }>;

export function applyTurnStarted(
  messages: ChatMessage[],
  event: TurnStarted,
  timestamp = Date.now(),
): ChatMessage[] {
  if (messages.some((message) => message.id === event.requestId)) return messages;
  return [
    ...messages,
    {
      id: event.requestId,
      role: "assistant",
      content: "",
      state: "streaming",
      timestamp,
    },
  ];
}

export function applyDelta(
  messages: ChatMessage[],
  event: Delta,
  timestamp = Date.now(),
): ChatMessage[] {
  const index = messages.findIndex((message) => message.id === event.requestId);
  if (index < 0) {
    return [
      ...messages,
      {
        id: event.requestId,
        role: "assistant",
        content: event.delta,
        state: "streaming",
        timestamp,
      },
    ];
  }
  if (messages[index].state !== "streaming") return messages;
  return messages.map((message, messageIndex) =>
    messageIndex === index ? { ...message, content: message.content + event.delta } : message,
  );
}

export function applyTurnCompleted(
  messages: ChatMessage[],
  event: TurnCompleted,
  timestamp = Date.now(),
): ChatMessage[] {
  const index = messages.findIndex((message) => message.id === event.requestId);
  if (index < 0) {
    return [
      ...messages,
      {
        id: event.requestId,
        role: "assistant",
        content: event.text,
        state: "complete",
        timestamp,
        turnId: event.turnId,
      },
    ];
  }
  return messages.map((message, messageIndex) =>
    messageIndex === index
      ? {
          ...message,
          content: event.text || message.content,
          state: "complete",
          turnId: event.turnId,
        }
      : message,
  );
}

export function applyTokenUsage(
  messages: ChatMessage[],
  event: TokenUsage,
): ChatMessage[] {
  const index = messages.findIndex((message) => message.id === event.requestId);
  if (index < 0 || messages[index].role !== "assistant") return messages;
  return messages.map((message, messageIndex) =>
    messageIndex === index
      ? {
          ...message,
          turnId: event.turnId,
          tokenUsage: {
            turn: event.usage,
            threadTotal: event.threadTotal,
            modelContextWindow: event.modelContextWindow,
          },
        }
      : message,
  );
}

export function applyExecutionUpdate(
  messages: ChatMessage[],
  event: ExecutionUpdate,
): ChatMessage[] {
  const index = messages.findIndex((message) => message.id === event.requestId);
  if (index < 0 || messages[index].role !== "assistant") return messages;
  return messages.map((message, messageIndex) => {
    if (messageIndex !== index) return message;
    const execution = message.execution ?? [];
    const stepIndex = execution.findIndex((step) => step.id === event.step.id);
    return {
      ...message,
      turnId: event.turnId,
      execution: stepIndex < 0
        ? [...execution, event.step]
        : execution.map((step, index) => index === stepIndex ? event.step : step),
    };
  });
}

export function applyTurnError(
  messages: ChatMessage[],
  event: TurnError,
  timestamp = Date.now(),
): ChatMessage[] {
  const index = messages.findIndex((message) => message.id === event.requestId);
  if (index < 0) {
    return [
      ...messages,
      {
        id: event.requestId,
        role: "assistant",
        content: event.message,
        state: "error",
        timestamp,
      },
    ];
  }
  return messages.map((message, messageIndex) =>
    messageIndex === index
      ? { ...message, content: event.message, state: "error" }
      : message,
  );
}

export function failStreamingMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => {
    if (message.role !== "assistant" || message.state !== "streaming") return message;
    const notice = "连接已中断，回复可能不完整。";
    return {
      ...message,
      content: message.content ? `${message.content}\n\n${notice}` : notice,
      state: "error",
    };
  });
}
