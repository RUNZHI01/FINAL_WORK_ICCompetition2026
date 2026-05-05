import process from "node:process";
import {
  canonicalizeMainSessionAlias,
  resolveMainSessionKey,
} from "../../../agent-lab/openclaw/src/config/sessions/main-session.ts";
import { loadConfig, resolveGatewayPort } from "../../../agent-lab/openclaw/src/config/config.ts";
import { loadGatewayTlsRuntime } from "../../../agent-lab/openclaw/src/infra/tls/gateway.ts";
import { GatewayClient } from "../../../agent-lab/openclaw/src/gateway/client.ts";
import { buildGatewayConnectionDetails } from "../../../agent-lab/openclaw/src/gateway/call.ts";
import { resolveGatewayCredentialsFromConfig } from "../../../agent-lab/openclaw/src/gateway/credentials.ts";
import {
  GATEWAY_CLIENT_MODES,
  GATEWAY_CLIENT_NAMES,
} from "../../../agent-lab/openclaw/src/utils/message-channel.ts";
import { DEFAULT_AGENT_ID } from "../../../agent-lab/openclaw/src/routing/session-key.ts";

type ChatHistoryMessage = {
  role?: unknown;
  content?: unknown;
  timestamp?: unknown;
  stopReason?: unknown;
};

type HistoryEntry = {
  role: "user" | "assistant";
  text: string;
  timestampMs: number | null;
  isAutoUser: boolean;
  isInternalUser: boolean;
  hasToolCall: boolean;
  stopReason: string;
};

type ChatEventPayload = {
  runId?: unknown;
  sessionKey?: unknown;
  state?: unknown;
};

const DEFAULT_HISTORY_LIMIT = 24;
const DEFAULT_TIMEOUT_MS = 4 * 60 * 60 * 1000;
const DEFAULT_SETTLE_MS = 1200;
const DEFAULT_IN_PROGRESS_RECENT_MS = 30 * 60 * 1000;
const AUTO_CONTINUE_MARKER = "[auto-continue]";

const DONE_MARKERS = [
  "[done]",
  "已完成",
  "已经完成",
  "完成了",
  "完成并",
  "修好了",
  "已修复",
  "已提交",
  "已更新",
  "收尾",
  "总结一下",
  "主结论",
  "关键输出",
  "final summary",
  "completed",
  "finished",
  "fixed",
  "submitted",
];

const IN_PROGRESS_MARKERS = [
  "我开始",
  "开始重",
  "开始做",
  "开始重新",
  "我先",
  "我会先",
  "我会",
  "接下来",
  "现在去",
  "正在",
  "先检查",
  "先看",
  "先修",
  "先改",
  "继续做",
  "我去",
  "我在",
  "重新做",
  "i'll",
  "i will",
  "i'm going to",
  "starting",
  "working on",
];

function usage(): never {
  console.error(
    "Usage: wait_for_gateway_session_idle.ts --session <key> [--timeout-ms <n>] [--history-limit <n>]  (--timeout-ms 0 disables the timeout)",
  );
  process.exit(1);
}

function getArg(flag: string): string | undefined {
  const idx = process.argv.indexOf(flag);
  if (idx === -1 || idx + 1 >= process.argv.length) {
    return undefined;
  }
  return process.argv[idx + 1];
}

function parsePositiveInt(raw: string | undefined, fallback: number, flag: string): number {
  if (!raw) {
    return fallback;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    console.error(`invalid ${flag}: ${raw}`);
    process.exit(1);
  }
  return value;
}

function parseNonNegativeInt(raw: string | undefined, fallback: number, flag: string): number {
  if (!raw) {
    return fallback;
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 0) {
    console.error(`invalid ${flag}: ${raw}`);
    process.exit(1);
  }
  return value;
}

function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function textOf(content: unknown): string {
  if (typeof content === "string") {
    return normalizeText(content);
  }
  if (!Array.isArray(content)) {
    return "";
  }
  const parts: string[] = [];
  for (const item of content) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const record = item as { type?: unknown; text?: unknown };
    if (record.type !== "text" || typeof record.text !== "string") {
      continue;
    }
    const normalized = normalizeText(record.text);
    if (normalized) {
      parts.push(normalized);
    }
  }
  return parts.join(" ").trim();
}

function hasToolCall(content: unknown): boolean {
  if (!Array.isArray(content)) {
    return false;
  }
  return content.some(
    (item) =>
      item &&
      typeof item === "object" &&
      (item as { type?: unknown }).type === "toolCall",
  );
}

function toTimestampMs(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value > 10_000_000_000) {
      return Math.trunc(value);
    }
    return Math.trunc(value * 1000);
  }
  if (typeof value === "string" && value.trim()) {
    const direct = Number(value);
    if (Number.isFinite(direct)) {
      return toTimestampMs(direct);
    }
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
}

function isInternalUserMessage(text: string): boolean {
  return (
    text.startsWith("System:") ||
    text.startsWith("An async command you ran earlier has completed.") ||
    text.startsWith("A scheduled reminder has been triggered.") ||
    text.startsWith("A scheduled cron event was triggered.")
  );
}

function clip(text: string, limit = 140): string {
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit - 1).trimEnd()}…`;
}

function normalizeSessionKeySet(cfg: ReturnType<typeof loadConfig>, sessionKey: string): Set<string> {
  const normalized = sessionKey.trim();
  const canonical =
    normalized === "main"
      ? resolveMainSessionKey(cfg)
      : canonicalizeMainSessionAlias({
          cfg,
          agentId: DEFAULT_AGENT_ID,
          sessionKey: normalized,
        });
  const directAgentKey =
    normalized && !normalized.startsWith("agent:") && normalized !== "main"
      ? `agent:${DEFAULT_AGENT_ID}:${normalized}`
      : "";
  return new Set(
    [normalized, canonical, directAgentKey].map((value) => value.trim()).filter(Boolean),
  );
}

function historyEntriesFromPayload(payload: unknown): HistoryEntry[] {
  const candidate =
    payload &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    "messages" in payload &&
    Array.isArray((payload as { messages?: unknown }).messages)
      ? ((payload as { messages: unknown[] }).messages ?? [])
      : [];
  const entries: HistoryEntry[] = [];
  for (const raw of candidate) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const message = raw as ChatHistoryMessage;
    const role = message.role === "user" || message.role === "assistant" ? message.role : null;
    if (!role) {
      continue;
    }
    const text = textOf(message.content);
    const toolCall = hasToolCall(message.content);
    if (!text && !toolCall) {
      continue;
    }
    entries.push({
      role,
      text,
      timestampMs: toTimestampMs(message.timestamp),
      isAutoUser: role === "user" && text.startsWith(AUTO_CONTINUE_MARKER),
      isInternalUser: role === "user" && isInternalUserMessage(text),
      hasToolCall: toolCall,
      stopReason: typeof message.stopReason === "string" ? message.stopReason : "",
    });
  }
  return entries;
}

function latestNonAutoUser(entries: HistoryEntry[]): HistoryEntry | null {
  for (let idx = entries.length - 1; idx >= 0; idx -= 1) {
    const entry = entries[idx];
    if (!entry) {
      continue;
    }
    if (entry.role === "user" && !entry.isAutoUser && !entry.isInternalUser) {
      return entry;
    }
  }
  return null;
}

function latestAssistant(entries: HistoryEntry[]): HistoryEntry | null {
  for (let idx = entries.length - 1; idx >= 0; idx -= 1) {
    const entry = entries[idx];
    if (entry?.role === "assistant") {
      return entry;
    }
  }
  return null;
}

function hasMarker(text: string, markers: readonly string[]): boolean {
  const normalized = text.toLowerCase();
  return markers.some((marker) => normalized.includes(marker.toLowerCase()));
}

function looksCompleted(text: string): boolean {
  return hasMarker(text, DONE_MARKERS);
}

function looksInProgress(text: string): boolean {
  return hasMarker(text, IN_PROGRESS_MARKERS) && !looksCompleted(text);
}

function describeBusyHint(entries: HistoryEntry[], nowMs: number): string | null {
  const latestVisible = entries.at(-1) ?? null;
  const latestUser = latestNonAutoUser(entries);
  const latestAssistantEntry = latestAssistant(entries);

  if (
    latestVisible &&
    latestVisible.role === "user" &&
    !latestVisible.isAutoUser &&
    !latestVisible.isInternalUser
  ) {
    return `最新可见消息还是用户消息: ${clip(latestVisible.text)}`;
  }

  if (!latestAssistantEntry) {
    return null;
  }

  if (latestAssistantEntry.hasToolCall || latestAssistantEntry.stopReason === "toolUse") {
    return "最近一条助手消息正在等待 toolCall 执行完成";
  }

  if (looksCompleted(latestAssistantEntry.text)) {
    return null;
  }

  if (looksInProgress(latestAssistantEntry.text)) {
    const ageMs =
      latestAssistantEntry.timestampMs == null ? null : Math.max(0, nowMs - latestAssistantEntry.timestampMs);
    if (ageMs == null || ageMs <= DEFAULT_IN_PROGRESS_RECENT_MS) {
      return `最新助手消息看起来仍在执行中: ${clip(latestAssistantEntry.text)}`;
    }
  }

  if (
    latestUser &&
    latestAssistantEntry.timestampMs != null &&
    latestUser.timestampMs != null &&
    latestUser.timestampMs >= latestAssistantEntry.timestampMs &&
    !looksCompleted(latestAssistantEntry.text)
  ) {
    return "最近一条非自动用户消息比最近助手消息更新";
  }

  return null;
}

async function resolveGatewayUrlAndAuth(cfg: ReturnType<typeof loadConfig>) {
  const details = buildGatewayConnectionDetails({ config: cfg });
  const creds = resolveGatewayCredentialsFromConfig({
    cfg,
    env: process.env,
    remotePasswordPrecedence: "env-first",
  });
  const token = creds.token?.trim() || undefined;
  const password = creds.password?.trim() || undefined;
  const usingRemote = cfg.gateway?.mode === "remote" && typeof cfg.gateway?.remote?.url === "string";
  const localPort = resolveGatewayPort(cfg);
  const localWsUrl = `ws://127.0.0.1:${localPort}`;
  const localWssUrl = `wss://127.0.0.1:${localPort}`;
  let tlsFingerprint: string | undefined;
  if (details.url === localWssUrl) {
    const tlsRuntime = await loadGatewayTlsRuntime(cfg.gateway?.tls);
    tlsFingerprint = tlsRuntime.enabled ? (tlsRuntime.fingerprintSha256 ?? undefined) : undefined;
  } else if (details.url === localWsUrl) {
    tlsFingerprint = undefined;
  } else if (usingRemote) {
    tlsFingerprint = cfg.gateway?.remote?.tlsFingerprint?.trim() || undefined;
  } else if (cfg.gateway?.tls?.enabled) {
    tlsFingerprint = undefined;
  }
  return {
    url: details.url,
    token,
    password,
    tlsFingerprint,
  };
}

async function main() {
  const sessionKey = getArg("--session")?.trim();
  if (!sessionKey) {
    usage();
  }

  const timeoutMs = parseNonNegativeInt(getArg("--timeout-ms"), DEFAULT_TIMEOUT_MS, "--timeout-ms");
  const historyLimit = parsePositiveInt(
    getArg("--history-limit"),
    DEFAULT_HISTORY_LIMIT,
    "--history-limit",
  );

  const cfg = loadConfig();
  const sessionKeys = normalizeSessionKeySet(cfg, sessionKey);

  let settleTimer: NodeJS.Timeout | null = null;
  let deadlineTimer: NodeJS.Timeout | null = null;
  let client: GatewayClient | null = null;
  let done = false;
  let observedBusy = false;
  let terminalObserved = false;
  const activeRunIds = new Set<string>();
  const startedAt = Date.now();
  let helloResolve: (() => void) | null = null;
  let helloReject: ((error: Error) => void) | null = null;

  const finish = (status: "idle-now" | "idle-after-wait" | "timeout", reason: string): never => {
    if (done) {
      process.exit(status === "timeout" ? 124 : 0);
    }
    done = true;
    if (settleTimer) {
      clearTimeout(settleTimer);
      settleTimer = null;
    }
    if (deadlineTimer) {
      clearTimeout(deadlineTimer);
      deadlineTimer = null;
    }
    client?.stop();
    const waitedMs = Math.max(0, Date.now() - startedAt);
    console.log([status, reason, String(waitedMs)].join("\t"));
    process.exit(status === "timeout" ? 124 : 0);
  };

  const armSettle = (reason: string) => {
    if (!observedBusy || !terminalObserved || activeRunIds.size > 0 || done) {
      return;
    }
    if (settleTimer) {
      clearTimeout(settleTimer);
    }
    settleTimer = setTimeout(() => {
      finish("idle-after-wait", reason);
    }, DEFAULT_SETTLE_MS);
  };

  try {
    const gateway = await resolveGatewayUrlAndAuth(cfg);
    const helloPromise = new Promise<void>((resolve, reject) => {
      helloResolve = resolve;
      helloReject = reject;
    });

    client = new GatewayClient({
      url: gateway.url,
      token: gateway.token,
      password: gateway.password,
      tlsFingerprint: gateway.tlsFingerprint,
      clientName: GATEWAY_CLIENT_NAMES.CLI,
      clientDisplayName: "continue idle waiter",
      clientVersion: "dev",
      platform: process.platform,
      mode: GATEWAY_CLIENT_MODES.CLI,
      role: "operator",
      scopes: ["operator.read", "operator.write", "operator.admin"],
      instanceId: "continue-idle-waiter",
      onHelloOk: () => {
        helloResolve?.();
      },
      onConnectError: (err) => {
        helloReject?.(err);
      },
      onClose: (code, reason) => {
        if (!done) {
          helloReject?.(new Error(`gateway closed (${code}): ${reason}`));
        }
      },
      onEvent: (evt) => {
        if (done || evt.event !== "chat") {
          return;
        }
        const payload = evt.payload as ChatEventPayload | undefined;
        const eventSessionKey =
          payload && typeof payload.sessionKey === "string" ? payload.sessionKey.trim() : "";
        if (!eventSessionKey || !sessionKeys.has(eventSessionKey)) {
          return;
        }
        const runId = typeof payload.runId === "string" ? payload.runId.trim() : "";
        const state = typeof payload.state === "string" ? payload.state.trim() : "";
        observedBusy = true;
        if (state === "delta" && runId) {
          activeRunIds.add(runId);
          if (settleTimer) {
            clearTimeout(settleTimer);
            settleTimer = null;
          }
          return;
        }
        if (runId) {
          activeRunIds.delete(runId);
        }
        if (state === "final" || state === "error" || state === "aborted") {
          terminalObserved = true;
          armSettle(`观察到 ${eventSessionKey} 的终态事件: ${state}`);
        }
      },
    });

    if (timeoutMs > 0) {
      deadlineTimer = setTimeout(() => {
        finish("timeout", "等待主会话上一轮任务结束超时");
      }, timeoutMs);
    }

    client.start();
    await Promise.race([
      helloPromise,
      new Promise<void>((_, reject) => {
        setTimeout(() => reject(new Error("gateway connect timeout")), 15_000);
      }),
    ]);
    const historyPayload = await client.request<{ messages?: unknown[] }>("chat.history", {
      sessionKey,
      limit: historyLimit,
    });
    const entries = historyEntriesFromPayload(historyPayload);
    const nowMs = Date.now();
    const busyHint = describeBusyHint(entries, nowMs);
    if (!busyHint) {
      finish("idle-now", "主会话当前没有明显的未完成上一轮任务");
    }

    observedBusy = true;
    if (settleTimer) {
      clearTimeout(settleTimer);
      settleTimer = null;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (deadlineTimer) {
      clearTimeout(deadlineTimer);
      deadlineTimer = null;
    }
    if (settleTimer) {
      clearTimeout(settleTimer);
      settleTimer = null;
    }
    client?.stop();
    console.error(message);
    process.exit(1);
  }
}

void main();
