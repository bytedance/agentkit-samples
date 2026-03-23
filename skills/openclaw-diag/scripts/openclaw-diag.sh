#!/bin/bash
# OpenClaw 诊断日志解析工具 v3.2
# 用法:
#   ./openclaw-diag.sh              # 解析今天的日志
#   ./openclaw-diag.sh 2026-03-11   # 解析指定日期
#   ./openclaw-diag.sh -f           # 实时跟踪模式（标准）
#   ./openclaw-diag.sh -f --advanced # 实时跟踪模式（高级：自动开启 debug 日志）
#   ./openclaw-diag.sh -l 5         # 只看最近5个run
#   ./openclaw-diag.sh -s           # 只看摘要统计
#   ./openclaw-diag.sh -a waicode 2026-03-19  # 按 agent 过滤
#   ./openclaw-diag.sh -s -a main   # 指定 agent 的摘要
#   ./openclaw-diag.sh -f -a waicode # 实时跟踪指定 agent
#
# 功能:
#   - 解析 OpenClaw 诊断日志，展示 Run 时间线
#   - 从 session 文件提取工具调用参数和 Token 用量
#   - 计算推理分段耗时和 Token 速率 (inference_ms, tokens_per_sec)
#   - 实时跟踪模式 (-f) 流式输出
#   - 高级模式 (--advanced) 自动开启 diagnostics + debug 日志
#   - 摘要模式 (-s) 快速统计
#
# 注: 完整探测功能（health/gateway/doctor/config/models）请使用:
#   python3 openclaw-dashboard.py --cli [--probe <name>] [--json]
#
# 数据源:
#   - 日志文件: /tmp/openclaw/openclaw-YYYY-MM-DD.log
#   - 会话文件: ~/.openclaw/agents/*/sessions/*.jsonl

set -euo pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

# 默认参数
DATE=$(date +%F)
FOLLOW=false
ADVANCED=false
LAST_N=0
SUMMARY_ONLY=false
AGENT_FILTER=""

# ============================================================
# 高级模式：配置管理函数
# ============================================================

# 查找 openclaw.json 路径
find_openclaw_config() {
    local config=""
    for p in \
        "$HOME/.openclaw/openclaw.json" \
        "/root/.openclaw/openclaw.json" \
        "/etc/openclaw/openclaw.json"; do
        if [ -f "$p" ]; then
            config="$p"
            break
        fi
    done
    # 尝试 openclaw config validate 输出
    if [ -z "$config" ]; then
        config=$(openclaw config validate 2>&1 | grep -oP '(?<=config: ).*\.json' | head -1 2>/dev/null || true)
    fi
    echo "$config"
}

# 备份 openclaw.json
backup_config() {
    local config="$1"
    local backup="${config}.diag-backup.$(date +%s)"
    cp "$config" "$backup"
    echo "$backup"
}

# 检查配置项当前值
check_config_value() {
    local config="$1"
    local key_path="$2"
    python3 -c "
import json, sys
with open('$config') as f:
    data = json.load(f)
keys = '$key_path'.split('.')
obj = data
for k in keys:
    obj = obj.get(k, None) if isinstance(obj, dict) else None
    if obj is None:
        break
print(obj if obj is not None else 'NOT_SET')
" 2>/dev/null
}

# 修改配置项
set_config_value() {
    local config="$1"
    local key_path="$2"
    local value="$3"
    python3 -c "
import json
with open('$config') as f:
    data = json.load(f)
keys = '$key_path'.split('.')
obj = data
for k in keys[:-1]:
    if k not in obj or not isinstance(obj[k], dict):
        obj[k] = {}
    obj = obj[k]
val = '$value'
if val == 'true':
    obj[keys[-1]] = True
elif val == 'false':
    obj[keys[-1]] = False
elif val.isdigit():
    obj[keys[-1]] = int(val)
else:
    obj[keys[-1]] = val
with open('$config', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
" 2>/dev/null
}

# 启用高级诊断模式
enable_advanced_mode() {
    local config
    config=$(find_openclaw_config)
    if [ -z "$config" ]; then
        echo -e "${RED}✘ 找不到 openclaw.json 配置文件${NC}" >&2
        return 1
    fi

    echo -e "${BOLD}[高级模式] 配置检查${NC}"
    echo -e "${GRAY}配置文件: $config${NC}"
    echo ""

    # 检查当前状态
    local diag_enabled
    local log_level
    diag_enabled=$(check_config_value "$config" "diagnostics.enabled")
    log_level=$(check_config_value "$config" "logging.level")

    local need_change=false
    local changes=""

    if [ "$diag_enabled" != "True" ]; then
        changes="${changes}  diagnostics.enabled: ${RED}${diag_enabled}${NC} → ${GREEN}true${NC}\n"
        need_change=true
    else
        changes="${changes}  diagnostics.enabled: ${GREEN}true${NC} (已启用)\n"
    fi

    if [ "$log_level" != "debug" ]; then
        changes="${changes}  logging.level: ${RED}${log_level}${NC} → ${GREEN}debug${NC}\n"
        need_change=true
    else
        changes="${changes}  logging.level: ${GREEN}debug${NC} (已启用)\n"
    fi

    echo -e "$changes"

    if [ "$need_change" = false ]; then
        echo -e "${GREEN}✔ 高级模式已经启用，无需修改配置${NC}"
        echo ""
        return 0
    fi

    # 提醒需要重启
    echo -e "${YELLOW}⚠  开启高级模式需要修改配置并重启 OpenClaw Gateway${NC}"
    echo -e "${YELLOW}   修改内容: diagnostics.enabled=true, logging.level=debug${NC}"
    echo ""
    read -p "$(echo -e "${BOLD}确认修改配置并重启? [y/N] ${NC}")" confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${GRAY}已取消${NC}"
        return 1
    fi

    # 备份
    echo ""
    local backup
    backup=$(backup_config "$config")
    echo -e "${GREEN}✔ 配置已备份: ${GRAY}$backup${NC}"
    # 将备份路径保存供后续恢复使用
    ADVANCED_BACKUP="$backup"
    ADVANCED_CONFIG="$config"

    # 修改配置
    if [ "$diag_enabled" != "True" ]; then
        set_config_value "$config" "diagnostics.enabled" "true"
        echo -e "${GREEN}✔ diagnostics.enabled → true${NC}"
    fi
    if [ "$log_level" != "debug" ]; then
        set_config_value "$config" "logging.level" "debug"
        echo -e "${GREEN}✔ logging.level → debug${NC}"
    fi

    # 重启 Gateway
    echo ""
    echo -e "${BLUE}⟳ 正在重启 OpenClaw Gateway...${NC}"
    if openclaw gateway restart 2>&1 | tail -3; then
        echo -e "${GREEN}✔ Gateway 重启成功${NC}"
    else
        echo -e "${RED}✘ Gateway 重启失败，正在恢复配置...${NC}"
        cp "$backup" "$config"
        echo -e "${YELLOW}⟳ 配置已恢复，再次重启...${NC}"
        openclaw gateway restart 2>&1 | tail -3 || true
        return 1
    fi

    echo ""
    echo -e "${GREEN}✔ 高级模式已启用${NC}"
    echo -e "${GRAY}退出时将提示恢复原始配置${NC}"
    echo ""
    return 0
}

# 恢复配置（高级模式退出时调用，仅执行一次）
RESTORE_DONE=false
restore_config() {
    # 防止重入（EXIT + INT/TERM 重复触发）
    if [ "$RESTORE_DONE" = true ]; then
        return 0
    fi
    RESTORE_DONE=true

    if [ -z "${ADVANCED_BACKUP:-}" ] || [ -z "${ADVANCED_CONFIG:-}" ]; then
        return 0
    fi

    echo ""
    echo -e "${BOLD}[高级模式] 退出清理${NC}"
    echo ""
    read -p "$(echo -e "${YELLOW}是否恢复原始配置并重启 Gateway? [Y/n] ${NC}")" restore_confirm </dev/tty
    if [[ "$restore_confirm" =~ ^[Nn]$ ]]; then
        echo -e "${GRAY}保留当前高级模式配置${NC}"
        echo -e "${GRAY}备份文件: $ADVANCED_BACKUP${NC}"
        echo -e "${GRAY}手动恢复: cp $ADVANCED_BACKUP $ADVANCED_CONFIG && openclaw gateway restart${NC}"
        return 0
    fi

    echo -e "${BLUE}⟳ 恢复原始配置...${NC}"
    cp "$ADVANCED_BACKUP" "$ADVANCED_CONFIG"
    echo -e "${GREEN}✔ 配置已恢复${NC}"

    echo -e "${BLUE}⟳ 重启 OpenClaw Gateway...${NC}"
    if openclaw gateway restart 2>&1 | tail -3; then
        echo -e "${GREEN}✔ Gateway 重启成功，已退出高级模式${NC}"
    else
        echo -e "${RED}✘ Gateway 重启失败${NC}"
        echo -e "${YELLOW}请手动执行: openclaw gateway restart${NC}"
    fi

    # 清理备份文件
    read -p "$(echo -e "${GRAY}删除备份文件? [y/N] ${NC}")" del_backup </dev/tty
    if [[ "$del_backup" =~ ^[Yy]$ ]]; then
        rm -f "$ADVANCED_BACKUP"
        echo -e "${GRAY}已删除 $ADVANCED_BACKUP${NC}"
    fi
}

# ============================================================
# 参数解析
# ============================================================

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)  FOLLOW=true; shift ;;
        --advanced)   ADVANCED=true; shift ;;
        -a|--agent)   AGENT_FILTER=$2; shift 2 ;;
        -l|--last)    LAST_N=$2; shift 2 ;;
        -s|--summary) SUMMARY_ONLY=true; shift ;;
        -h|--help)
            echo "OpenClaw 诊断日志解析工具 v3.1"
            echo ""
            echo "用法: $0 [选项] [日期]"
            echo ""
            echo "选项:"
            echo "  -f, --follow      实时跟踪模式"
            echo "  --advanced        高级模式（自动开启 diagnostics + debug 日志）"
            echo "  -a, --agent NAME  只看指定 agent（如 main/waicode/wairesearch）"
            echo "  -l N, --last N    只显示最近 N 个 run"
            echo "  -s, --summary     只显示摘要统计"
            echo "  -h, --help        帮助"
            echo ""
            echo "示例:"
            echo "  $0                          # 解析今天的日志（全部 agent）"
            echo "  $0 2026-03-11               # 解析指定日期"
            echo "  $0 -f                       # 实时跟踪（标准）"
            echo "  $0 -f --advanced            # 实时跟踪（高级：自动开启 debug）"
            echo "  $0 -f -a waicode            # 只跟踪 waicode agent"
            echo "  $0 -a main                  # 只看 main agent"
            echo "  $0 -l 3                     # 最近3个run"
            echo "  $0 -s                       # 摘要统计"
            echo ""
            echo "高级模式说明:"
            echo "  --advanced 会自动修改 openclaw.json 配置:"
            echo "    - diagnostics.enabled = true"
            echo "    - logging.level = debug"
            echo "  启用前会备份配置，退出时提示恢复原始配置并重启"
            exit 0
            ;;
        *)
            if [[ $1 =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
                DATE=$1
            else
                echo "未知参数: $1 (用 -h 查看帮助)"
                exit 1
            fi
            shift
            ;;
    esac
done

LOG="/tmp/openclaw/openclaw-${DATE}.log"

# 自动查找会话文件目录
SESSIONS_DIR=""
for d in \
    "$HOME/.openclaw/agents/main/sessions" \
    "$HOME/.openclaw/agents/*/sessions" \
    "/root/.openclaw/agents/main/sessions" \
    "/root/.openclaw/agents/*/sessions"; do
    if [ -d "$d" ] 2>/dev/null; then
        SESSIONS_DIR="$d"
        break
    fi
done
# 如果通配符没展开，尝试 find
if [ -z "$SESSIONS_DIR" ] || [ ! -d "$SESSIONS_DIR" ]; then
    SESSIONS_DIR=$(find "${HOME}/.openclaw/agents" -type d -name "sessions" 2>/dev/null | head -1)
fi

if [ "$FOLLOW" = true ]; then
    # 高级模式：启用 diagnostics + debug
    if [ "$ADVANCED" = true ]; then
        enable_advanced_mode || exit 1
        # 注册退出清理（仅 EXIT，覆盖所有退出路径包括 Ctrl+C）
        trap restore_config EXIT
    fi

    echo -e "${BOLD}[实时跟踪] Ctrl+C 退出${NC}"
    if [ "$ADVANCED" = true ]; then
        echo -e "${GREEN}模式: 高级（diagnostics + debug）${NC}"
    else
        echo -e "${GRAY}模式: 标准（提示: 使用 --advanced 开启完整日志）${NC}"
    fi
    if [ -n "$AGENT_FILTER" ]; then
        echo -e "${CYAN}过滤: 仅显示 agent=${AGENT_FILTER}${NC}"
    else
        echo -e "${GRAY}过滤: 全部 agent（提示: 使用 -a <name> 过滤指定 agent）${NC}"
    fi
    echo -e "${GRAY}日志文件: $LOG${NC}"
    echo ""
    AGENT_FILTER_ENV="$AGENT_FILTER" tail -f "$LOG" 2>/dev/null | python3 -c "
import json, sys, os, re
from datetime import datetime

# Agent 颜色映射
AGENT_COLORS = {
    'main':        '\033[0;36m',     # cyan
    'waicode':     '\033[0;32m',     # green
    'waidesign':   '\033[0;35m',     # magenta
    'wairesearch': '\033[0;33m',     # yellow
    'waiqa':       '\033[0;34m',     # blue
}
NC = '\033[0m'
BOLD = '\033[1m'
GRAY = '\033[0;90m'

agent_filter = os.environ.get('AGENT_FILTER_ENV', '')

# 从日志消息中提取 agent 名称
def extract_agent(msg):
    # sessionKey=agent:waicode:main → waicode
    m = re.search(r'sessionKey=agent:([^:\s]+)', msg)
    if m:
        return m.group(1)
    # lane=session:agent:wairesearch:main → wairesearch
    m = re.search(r'lane=session:agent:([^:\s]+)', msg)
    if m:
        return m.group(1)
    # [waicode] starting provider → waicode
    m = re.search(r'\[(\w+)\]\s+(?:starting|stopping)', msg)
    if m and m.group(1) != 'openclaw':
        return m.group(1)
    return ''

def agent_tag(agent):
    if not agent:
        return ''
    color = AGENT_COLORS.get(agent, GRAY)
    return f'{color}[{agent}]{NC} '

# 跟踪每个 agent 的上一次时间戳
agent_prev_times = {}

for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        t = obj.get('time', '')
        parts = [obj.get(str(i), '') for i in range(3) if isinstance(obj.get(str(i), ''), str)]
        msg = ' '.join(parts)
        level = obj.get('_meta', {}).get('logLevelName', '')

        # 提取 agent
        agent = extract_agent(msg)

        # 过滤
        if agent_filter and agent and agent != agent_filter:
            continue

        label = None
        detail = ''

        if 'embedded run start:' in msg:
            label = '[RUN-START] 开始处理请求'
            if 'model=' in msg:
                detail = 'model=' + msg.split('model=')[1].split(' ')[0]
        elif 'run agent start' in msg:
            label = '[MODEL-SEND] 请求已发送给模型, 等待推理'
        elif 'run agent end' in msg:
            label = '[MODEL-DONE] 模型推理完成'
        elif 'tool start' in msg:
            tool = msg.split('tool=')[1].split(' ')[0] if 'tool=' in msg else '?'
            label = f'[TOOL-START] 开始执行工具: {tool}'
        elif 'tool end' in msg:
            tool = msg.split('tool=')[1].split(' ')[0] if 'tool=' in msg else '?'
            label = f'[TOOL-END]   工具执行完成: {tool}'
        elif 'sendMessage' in msg:
            label = '[MSG-SEND]  消息发送到通道'
            detail = msg.split('sendMessage')[1][:60].strip() if 'sendMessage' in msg else ''
        elif 'lane dequeue' in msg:
            label = '[DEQUEUE]   消息从队列取出'
            if 'waitMs=' in msg:
                detail = '排队等待 ' + msg.split('waitMs=')[1].split(' ')[0] + 'ms'
        elif 'pre-prompt' in msg:
            label = '[PROMPT]    构建提示词'
            if 'messages=' in msg:
                detail = '历史消息 ' + msg.split('messages=')[1].split(' ')[0] + ' 条'
        elif 'session state' in msg:
            # 会话状态变更
            new_state = ''
            if 'new=processing' in msg:
                new_state = '→ processing'
            elif 'new=idle' in msg:
                new_state = '→ idle'
            if new_state:
                label = f'[SESSION]   {new_state}'
                if 'reason=' in msg:
                    detail = msg.split('reason=')[1].split(' ')[0].strip('\"')
        elif 'spawn' in msg.lower() and ('sub-agent' in msg.lower() or 'sessions_spawn' in msg.lower()):
            label = '[SPAWN]     子 agent 派发'
            detail = msg[:80]
        elif level == 'ERROR':
            label = '[ERROR]     错误'
            detail = msg[:80]
        elif level == 'WARN':
            label = '[WARN]      警告'
            detail = msg[:80]

        if not label:
            continue

        ts = t[11:23]
        # 每个 agent 独立计算时间差
        track_key = agent or '__global__'
        try:
            curr = datetime.fromisoformat(t.replace('+00:00', ''))
            prev = agent_prev_times.get(track_key)
            if prev:
                delta_ms = (curr - prev).total_seconds() * 1000
                if delta_ms >= 1000:
                    delta_str = f'+{delta_ms/1000:.1f}s'
                else:
                    delta_str = f'+{delta_ms:.0f}ms'
            else:
                delta_str = '---'
            agent_prev_times[track_key] = curr
        except:
            delta_str = '?'

        tag = agent_tag(agent)
        detail_str = f'  {detail}' if detail else ''
        print(f'{ts} {delta_str:>8} {tag}{label}{detail_str}', flush=True)
    except:
        pass
"
    exit 0
fi

# 非实时模式
# --advanced 在非实时模式下仅提示，不自动修改配置
if [ "$ADVANCED" = true ] && [ "$FOLLOW" = false ]; then
    echo -e "${YELLOW}提示: --advanced 仅在实时跟踪模式 (-f) 下生效${NC}"
    echo -e "${GRAY}用法: $0 -f --advanced${NC}"
    echo ""
fi

NO_LOG=false
if [ ! -f "$LOG" ]; then
    NO_LOG=true
fi

echo -e "${BOLD}[OpenClaw 诊断报告]${NC}"
if [ "$NO_LOG" = true ]; then
    echo -e "${YELLOW}日志文件: $LOG (不存在，使用 session 数据)${NC}"
else
    echo -e "${GRAY}日志文件: $LOG${NC}"
fi
echo -e "${GRAY}会话目录: ${SESSIONS_DIR:-未找到}${NC}"
echo -e "${GRAY}日期: $DATE${NC}"
if [ -n "$AGENT_FILTER" ]; then
    echo -e "${CYAN}过滤: agent=${AGENT_FILTER}${NC}"
fi
echo ""

export DIAG_LOG="$LOG"
export DIAG_DATE="$DATE"
export DIAG_LAST_N="$LAST_N"
export DIAG_SUMMARY="$SUMMARY_ONLY"
export DIAG_SESSIONS_DIR="${SESSIONS_DIR:-}"
export DIAG_AGENT_FILTER="${AGENT_FILTER}"

python3 << 'PYEOF'
import json, sys, os, glob
from datetime import datetime
from collections import defaultdict

LOG = os.environ.get("DIAG_LOG", "/tmp/openclaw/openclaw.log")
LAST_N = int(os.environ.get("DIAG_LAST_N", "0"))
SUMMARY_ONLY = os.environ.get("DIAG_SUMMARY", "false") == "true"
SESSIONS_DIR = os.environ.get("DIAG_SESSIONS_DIR", "")
DIAG_DATE = os.environ.get("DIAG_DATE", "")
AGENT_FILTER = os.environ.get("DIAG_AGENT_FILTER", "")

# ============================================================
# 1. 从会话文件中提取工具调用参数
# ============================================================
# toolCallId -> {name, summary, workdir}
tool_params = {}
# toolCallId -> {toolName, isError, exitCode, durationMs, status, cwd, diff, url, tookMs, childSessionKey}
tool_details = {}

# 每次推理的 token 用量: toolCallId -> usage dict
# 一个 assistant 消息可能包含多个 toolCall, 它们共享同一个 usage
# 我们用第一个 toolCallId 作为 key, 也建立反向映射
inference_usage = {}  # toolCallId -> {input, output, cacheRead, cacheWrite, totalTokens, cost, all_tool_ids}
# 没有 toolCall 的推理(纯文本回复)按时间戳索引
text_reply_usage = []  # [(timestamp, usage)]

# session_uuid → agent 映射 (用于日志 Run 的 agent 归属判定)
session_uuid_to_agent = {}

# 推理事件序列 (session-based): session_key -> [event_dict]
session_infer_events = defaultdict(list)
# 所有推理事件(用于时间窗口匹配)
all_infer_events = []

def extract_tool_summary(name, args):
    """从工具参数中提取可读摘要"""
    cmd = args.get("command", "")
    path = args.get("path", "") or args.get("file_path", "")
    workdir = args.get("workdir", "")
    query = args.get("query", "")
    url = args.get("url", "")
    action = args.get("action", "")
    task = args.get("task", "")
    text = args.get("text", "")
    message = args.get("message", "")
    old_str = args.get("old_string", "") or args.get("oldText", "")
    new_str = args.get("new_string", "") or args.get("newText", "")

    parts = []
    if name == "exec":
        # 取命令第一行
        first_line = cmd.split("\n")[0][:90] if cmd else ""
        parts.append(first_line)
        if workdir:
            parts.append(f"cwd={workdir}")
    elif name == "read":
        parts.append(path)
    elif name == "write":
        parts.append(path)
    elif name == "edit":
        parts.append(path)
        if old_str:
            preview = old_str[:40].replace("\n", " ")
            parts.append(f'替换: "{preview}..."')
    elif name == "web_search":
        parts.append(f'搜索: "{query}"')
    elif name == "web_fetch":
        parts.append(url)
    elif name == "browser":
        parts.append(action)
        if url:
            parts.append(url)
    elif name == "message":
        parts.append(action)
        if message:
            parts.append(message[:50])
    elif name == "sessions_spawn":
        agent = args.get("agentId", "?")
        parts.append(f"agent={agent}")
        if task:
            parts.append(task[:50])
    elif name == "memory_search":
        parts.append(f'查询: "{query}"')
    elif name == "memory_get":
        parts.append(path)
    elif name == "session_status":
        parts.append("查看状态")
    elif name == "process":
        parts.append(action)
        sid = args.get("sessionId", "")
        if sid:
            parts.append(f"session={sid}")
    elif name == "tts":
        parts.append(text[:50] if text else "")
    else:
        # 通用: 取前几个有值的参数
        for k, v in list(args.items())[:3]:
            if v and isinstance(v, str):
                parts.append(f"{k}={v[:40]}")

    return "  ".join(filter(None, parts))

if SESSIONS_DIR and os.path.isdir(SESSIONS_DIR):
    # 扫描所有 agent 的 sessions 目录
    # 往上两层到 agents/ 目录，扫描所有 agent 的 sessions
    agents_root = os.path.dirname(os.path.dirname(SESSIONS_DIR))  # agents/main/sessions → agents/
    session_dirs = glob.glob(os.path.join(agents_root, "*/sessions"))
    if not session_dirs:
        session_dirs = [SESSIONS_DIR]
    all_session_files = []
    for sd in session_dirs:
        for ext_pat in ["*.jsonl", "*.jsonl.reset.*", "*.jsonl.deleted.*"]:
            all_session_files.extend(glob.glob(os.path.join(sd, ext_pat)))
    if not all_session_files:
        for ext_pat in ["*.jsonl", "*.jsonl.reset.*", "*.jsonl.deleted.*"]:
            all_session_files.extend(glob.glob(os.path.join(SESSIONS_DIR, ext_pat)))
    for sf in all_session_files:
        try:
            # 从文件路径推导 session_key: agents/{agent}/sessions/{id}.jsonl -> {agent}:{id}
            sf_parts = sf.replace("\\", "/").split("/")
            sf_fname = os.path.basename(sf)
            sf_base = sf_fname
            for _sfx in [".deleted.", ".reset."]:
                _idx = sf_base.find(_sfx)
                if _idx >= 0:
                    sf_base = sf_base[:_idx]
            sf_base = sf_base.replace(".jsonl", "")
            sf_session_id = sf_base
            sf_agent = ""
            for pi, p in enumerate(sf_parts):
                if p == "agents" and pi + 1 < len(sf_parts):
                    sf_agent = sf_parts[pi + 1]
                    break
            sf_session_key = f"{sf_agent}:{sf_session_id}" if sf_agent else sf_session_id

            # 建立 session_uuid → agent 映射
            if sf_agent and sf_session_id:
                session_uuid_to_agent[sf_session_id] = sf_agent

            # Agent 过滤：跳过不匹配的 agent 的 session 文件
            if AGENT_FILTER and sf_agent and sf_agent != AGENT_FILTER:
                continue

            # 每个 session 文件独立跟踪 prev_top_timestamp
            prev_top_timestamp = ""
            infer_round = 0
            with open(sf) as f:
                for line in f:
                    try:
                        obj = json.loads(line.strip())
                        if obj.get("type") != "message":
                            continue
                        msg = obj.get("message", {})
                        content = msg.get("content", [])
                        if not isinstance(content, list):
                            content = []

                        role = msg.get("role", "")
                        usage = msg.get("usage", {})
                        model = msg.get("model", "")
                        timestamp = obj.get("timestamp", "")

                        # delivery-mirror: 记录 timestamp 但跳过后续处理
                        if role == "assistant" and model == "delivery-mirror":
                            if timestamp:
                                prev_top_timestamp = timestamp
                            continue

                        # user 消息: 记录 timestamp
                        if role == "user":
                            if timestamp:
                                prev_top_timestamp = timestamp
                            continue

                        # toolResult 消息: 记录 timestamp + 提取 details
                        if role == "toolResult":
                            if timestamp:
                                prev_top_timestamp = timestamp
                            tcid = msg.get("toolCallId", "")
                            tool_name = msg.get("toolName", "")
                            is_error = msg.get("isError", False)
                            details = msg.get("details", {})
                            if not isinstance(details, dict):
                                details = {}
                            if tcid:
                                tool_details[tcid] = {
                                    "toolName": tool_name,
                                    "isError": is_error,
                                    "exitCode": details.get("exitCode"),
                                    "durationMs": details.get("durationMs"),
                                    "status": details.get("status", ""),
                                    "cwd": details.get("cwd", ""),
                                    "diff": details.get("diff", ""),
                                    "url": details.get("url", ""),
                                    "tookMs": details.get("tookMs"),
                                    "childSessionKey": details.get("childSessionKey", ""),
                                }
                            continue

                        # 以下仅处理 assistant 消息 (非 delivery-mirror)
                        if role != "assistant":
                            continue

                        # 收集 toolCall 参数
                        tool_ids_in_msg = []
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "toolCall":
                                tid = block.get("id", "")
                                name = block.get("name", "?")
                                args_raw = block.get("arguments", "{}")
                                try:
                                    args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw if isinstance(args_raw, dict) else {})
                                except:
                                    args = {}
                                workdir = args.get("workdir", "")
                                summary = extract_tool_summary(name, args)
                                tool_params[tid] = {
                                    "name": name,
                                    "summary": summary,
                                    "workdir": workdir,
                                }
                                tool_ids_in_msg.append(tid)

                        # 计算 per-call 推理耗时 (与 Python dashboard 一致)
                        inference_ms = 0
                        tokens_per_sec = 0.0
                        if prev_top_timestamp and timestamp:
                            try:
                                cur_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                prev_dt = datetime.fromisoformat(prev_top_timestamp.replace("Z", "+00:00"))
                                delta = (cur_dt - prev_dt).total_seconds() * 1000
                                if delta > 0:
                                    inference_ms = round(delta)
                                    output_tokens = usage.get("output", 0) if isinstance(usage, dict) else 0
                                    if output_tokens > 0 and inference_ms > 0:
                                        tokens_per_sec = round(output_tokens / (inference_ms / 1000), 1)
                            except (ValueError, TypeError):
                                pass

                        # 收集每次推理的 usage (仅 assistant, 非 delivery-mirror)
                        if usage:
                            usage_record = {
                                "input": usage.get("input", 0),
                                "output": usage.get("output", 0),
                                "cacheRead": usage.get("cacheRead", 0),
                                "cacheWrite": usage.get("cacheWrite", 0),
                                "totalTokens": usage.get("totalTokens", 0),
                                "cost": usage.get("cost", {}),
                                "timestamp": timestamp,
                                "tool_ids": tool_ids_in_msg,
                                "inference_ms": inference_ms,
                                "tokens_per_sec": tokens_per_sec,
                            }
                            if tool_ids_in_msg:
                                for tid in tool_ids_in_msg:
                                    inference_usage[tid] = usage_record
                            else:
                                text_reply_usage.append((timestamp, usage_record))

                        # 推理事件提取: assistant 且 prev_top_timestamp 有值
                        if prev_top_timestamp and timestamp and inference_ms > 0:
                            infer_round += 1
                            infer_evt = {
                                "session_key": sf_session_key,
                                "send_ts": prev_top_timestamp,
                                "recv_ts": timestamp,
                                "inference_ms": inference_ms,
                                "round": infer_round,
                                "input_tokens": usage.get("input", 0) if isinstance(usage, dict) else 0,
                                "output_tokens": usage.get("output", 0) if isinstance(usage, dict) else 0,
                                "cache_read": usage.get("cacheRead", 0) if isinstance(usage, dict) else 0,
                                "tokens_per_sec": tokens_per_sec,
                                "model": model,
                            }
                            session_infer_events[sf_session_key].append(infer_evt)
                            all_infer_events.append(infer_evt)

                    except:
                        pass
        except:
            pass

# ============================================================
# 2. 解析日志事件
# ============================================================
events = []
if os.path.isfile(LOG):
    with open(LOG) as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                t = obj.get("time", "")
                parts = [obj.get(str(i), "") for i in range(3) if isinstance(obj.get(str(i), ""), str)]
                msg = " ".join(parts)
                level = obj.get("_meta", {}).get("logLevelName", "")
                events.append((t, level, msg))
            except:
                pass

# ============================================================
# 3. 提取 run 信息
# ============================================================
runs = {}
for t, level, msg in events:
    run_id = None
    if "runId=" in msg:
        run_id = msg.split("runId=")[1].split(" ")[0]

    if not run_id:
        continue

    if run_id not in runs:
        runs[run_id] = {
            "start": None, "end": None,
            "events": [], "tools": [],
            "model": "", "channel": "",
            "first_token": None,
            "prompt_messages": 0,
            "session_key": "",
            "session_uuid": "",  # session file UUID (from sessionId= in log)
        }

    r = runs[run_id]
    r["events"].append((t, msg))

    if "embedded run start:" in msg:
        r["start"] = t
        if "model=" in msg:
            r["model"] = msg.split("model=")[1].split(" ")[0]
        if "messageChannel=" in msg:
            r["channel"] = msg.split("messageChannel=")[1].split(" ")[0]
        elif "channel=" in msg.lower():
            r["channel"] = msg.lower().split("channel=")[1].split(" ")[0]
        if "sessionId=" in msg:
            # Extract session UUID for matching against session files
            r["session_uuid"] = msg.split("sessionId=")[1].split(" ")[0]

    elif "run agent start" in msg:
        r["first_token"] = t

    elif "run agent end" in msg or "run end" in msg:
        r["end"] = t

    elif "tool start" in msg:
        tool_name = msg.split("tool=")[1].split(" ")[0] if "tool=" in msg else "?"
        tool_id = msg.split("toolCallId=")[1].split(" ")[0] if "toolCallId=" in msg else ""
        r["tools"].append({"name": tool_name, "start": t, "end": None, "id": tool_id})

    elif "tool end" in msg:
        tool_id = msg.split("toolCallId=")[1].split(" ")[0] if "toolCallId=" in msg else ""
        for tool in reversed(r["tools"]):
            if tool["id"] == tool_id or (not tool["end"] and tool["id"] == ""):
                tool["end"] = t
                break

    elif "pre-prompt" in msg and "messages=" in msg:
        try:
            r["prompt_messages"] = int(msg.split("messages=")[1].split(" ")[0])
        except:
            pass
        if "sessionKey=" in msg:
            r["session_key"] = msg.split("sessionKey=")[1].split(" ")[0]
        # 从 sessionFile= 提取 session UUID，构造与 session_infer_events 一致的 key
        if "sessionFile=" in msg:
            _sf_path = msg.split("sessionFile=")[1].split(" ")[0]
            _sf_name = _sf_path.split("/")[-1].replace(".jsonl", "")
            _sf_agent = ""
            _sf_parts = _sf_path.replace("\\\\", "/").split("/")
            for _pi, _pp in enumerate(_sf_parts):
                if _pp == "agents" and _pi + 1 < len(_sf_parts):
                    _sf_agent = _sf_parts[_pi + 1]
                    break
            r["session_key"] = f"{_sf_agent}:{_sf_name}" if _sf_agent else _sf_name

# 收集 sendMessage 事件
sends = [(t, msg) for t, level, msg in events if "sendMessage" in msg]

# 收集错误
errors = [(t, msg) for t, level, msg in events if level == "ERROR"]

def parse_time(t):
    """Parse ISO timestamp to datetime, normalizing to UTC (naive datetime for comparison)."""
    if not t:
        return None
    try:
        # Handle various timezone formats: Z, +00:00, +08:00, etc.
        import re
        # Remove trailing Z
        s = t.replace("Z", "+00:00")
        # Parse with fromisoformat (Python 3.7+)
        dt = datetime.fromisoformat(s)
        # If timezone-aware, convert to UTC and strip tzinfo for comparison
        if dt.tzinfo is not None:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except:
        return None

def fmt_duration(ms):
    if ms >= 60000:
        return f"{ms/60000:.1f}min"
    elif ms >= 1000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms:.0f}ms"

def bar(ms, max_ms=30000, width=20):
    filled = min(int(ms / max_ms * width), width)
    return "#" * filled + "." * (width - filled)

# 按时间排序
sorted_runs = sorted(runs.items(), key=lambda x: x[1]["start"] or "")

# Agent 过滤：通过 session_uuid 和 session_key 判断 run 属于哪个 agent
if AGENT_FILTER:
    def _get_run_agent(r):
        # 优先通过 session_uuid 查 agent
        uuid = r.get("session_uuid", "")
        if uuid and uuid in session_uuid_to_agent:
            return session_uuid_to_agent[uuid]
        # 回退：从 session_key 提取 (agent:xxx:main)
        sk = r.get("session_key", "")
        if sk.startswith("agent:"):
            parts = sk.split(":")
            return parts[1] if len(parts) > 1 else ""
        return ""
    sorted_runs = [(rid, r) for rid, r in sorted_runs if _get_run_agent(r) == AGENT_FILTER or not _get_run_agent(r)]
    # 也过滤 errors/sends：仅保留明确包含目标 agent 的行
    errors = [(t, m) for t, m in errors if f'agent:{AGENT_FILTER}:' in m]
    sends = [(t, m) for t, m in sends if f'agent:{AGENT_FILTER}:' in m]

if LAST_N > 0:
    sorted_runs = sorted_runs[-LAST_N:]

# ============================================================
# 3.5 虚拟 Run 构造 (当无 debug 日志但有 session 数据时)
# ============================================================
virtual_runs_mode = False

if not sorted_runs and all_infer_events:
    virtual_runs_mode = True

    # 按日期过滤 session 事件
    date_filtered_events = []
    for evt in all_infer_events:
        send_ts = evt.get("send_ts", "")
        if DIAG_DATE and send_ts[:10] != DIAG_DATE:
            continue
        date_filtered_events.append(evt)

    # 按 session_key 分组
    session_groups = defaultdict(list)
    for evt in date_filtered_events:
        sk = evt["session_key"]
        # Agent 过滤（虚拟 Run: session_key 格式 waicode:uuid）
        if AGENT_FILTER:
            agent_part = sk.split(":")[0] if ":" in sk else ""
            if agent_part and agent_part != AGENT_FILTER:
                continue
        session_groups[sk].append(evt)

    # 为每个 session_key 构造虚拟 Run
    virtual_run_id = 0
    for sk, evts in sorted(session_groups.items(), key=lambda x: min(e["send_ts"] for e in x[1])):
        virtual_run_id += 1
        vrun_id = f"virtual-{virtual_run_id}"

        sorted_evts = sorted(evts, key=lambda e: e["send_ts"])
        v_start = sorted_evts[0]["send_ts"]
        v_end = sorted_evts[-1]["recv_ts"]
        v_model = ""
        for e in sorted_evts:
            if e.get("model"):
                v_model = e["model"]
                break

        # 从 tool_params 和 tool_details 中按时间窗口匹配工具调用
        v_start_dt = parse_time(v_start)
        v_end_dt = parse_time(v_end)
        v_tools = []
        if v_start_dt and v_end_dt:
            # 收集此 session 所有推理事件的 tool_ids
            matched_tool_ids = set()
            for e in sorted_evts:
                # 查找 inference_usage 中与此事件时间匹配的 tool_ids
                for tid, usage_rec in inference_usage.items():
                    if usage_rec.get("timestamp") == e["recv_ts"]:
                        matched_tool_ids.update(usage_rec.get("tool_ids", []))

            for tid in matched_tool_ids:
                tp = tool_params.get(tid, {})
                td = tool_details.get(tid, {})
                tname = tp.get("name", "") or td.get("toolName", "unknown")
                # 估算工具时间: 使用 tool_details 中的 durationMs
                t_dur_ms = td.get("durationMs") or td.get("tookMs") or 0
                v_tools.append({
                    "name": tname,
                    "start": "",  # 无精确时间
                    "end": "",
                    "id": tid,
                    "virtual_duration_ms": t_dur_ms,
                })

        runs[vrun_id] = {
            "start": v_start,
            "end": v_end,
            "events": [],
            "tools": v_tools,
            "model": v_model,
            "channel": "",
            "first_token": v_start,
            "prompt_messages": 0,
            "session_key": sk,
            "virtual": True,
        }

    # 重新排序
    sorted_runs = sorted(runs.items(), key=lambda x: x[1]["start"] or "")
    # Agent 过滤（虚拟 Run 的 session_key 格式: waicode:uuid）
    if AGENT_FILTER:
        sorted_runs = [(rid, r) for rid, r in sorted_runs if r.get("session_key", "").startswith(AGENT_FILTER + ":") or not r.get("session_key")]
    if LAST_N > 0:
        sorted_runs = sorted_runs[-LAST_N:]

# ============================================================
# 3.6 日期过滤全局数据 (虚拟 Run 模式下，确保统计只包含目标日期)
# ============================================================
# 将日期转换为 UTC 日期范围进行比较（考虑时区偏移，最多 ±14 小时）
def date_matches_utc(ts, target_date):
    """检查 UTC 时间戳的日期部分是否严格匹配目标日期。
    时间戳本身就是 UTC，无需 ±1 天容差。"""
    if not ts or not target_date:
        return True  # 无日期过滤
    return ts[:10] == target_date

if DIAG_DATE:
    # 收集目标日期所有 session 推理事件的 tool_ids 和 timestamps
    date_valid_tool_ids = set()
    date_valid_timestamps = set()
    for evt in all_infer_events:
        send_ts = evt.get("send_ts", "")
        recv_ts = evt.get("recv_ts", "")
        if date_matches_utc(send_ts, DIAG_DATE) or date_matches_utc(recv_ts, DIAG_DATE):
            date_valid_timestamps.add(recv_ts)
    # 从 inference_usage 中收集日期匹配的 tool_ids
    for tid, u in list(inference_usage.items()):
        if date_matches_utc(u.get("timestamp", ""), DIAG_DATE):
            date_valid_tool_ids.update(u.get("tool_ids", []))
            date_valid_tool_ids.add(tid)
    # 只在有日志 Run 时过滤 tool_params（虚拟 Run 模式保留所有，因为已通过 session 筛选）
    if not virtual_runs_mode and date_valid_tool_ids:
        tool_params = {k: v for k, v in tool_params.items() if k in date_valid_tool_ids}
        tool_details = {k: v for k, v in tool_details.items() if k in date_valid_tool_ids}
    # 始终按日期过滤 inference_usage 和 text_reply_usage（包括虚拟 Run 模式）
    inference_usage = {k: v for k, v in inference_usage.items() if date_matches_utc(v.get("timestamp", ""), DIAG_DATE)}
    text_reply_usage = [(ts, u) for ts, u in text_reply_usage if date_matches_utc(ts, DIAG_DATE)]
    # 虚拟 Run 模式下也按日期过滤 tool_params/tool_details
    if virtual_runs_mode:
        # 收集日期匹配的 tool_ids（从已过滤的 inference_usage 中提取）
        vr_valid_tool_ids = set()
        for tid, u in inference_usage.items():
            vr_valid_tool_ids.update(u.get("tool_ids", []))
            vr_valid_tool_ids.add(tid)
        tool_params = {k: v for k, v in tool_params.items() if k in vr_valid_tool_ids}
        tool_details = {k: v for k, v in tool_details.items() if k in vr_valid_tool_ids}
    # 过滤 all_infer_events (用于后续统计)
    all_infer_events = [e for e in all_infer_events if date_matches_utc(e.get("send_ts", ""), DIAG_DATE) or date_matches_utc(e.get("recv_ts", ""), DIAG_DATE)]

# ============================================================
# 4. 摘要统计
# ============================================================
print("=" * 68)
print(f"{'[摘要统计]':^64}")
print("=" * 68)

if virtual_runs_mode:
    print()
    print("  ⚠️  未检测到 debug 日志，使用 session 数据构建时间线（精度有限）")
    print()

total_runs = len(sorted_runs)
total_tools = sum(len(r["tools"]) for _, r in sorted_runs)
total_errors = len(errors)
total_sends = len(sends)

def calc_inference_segments(r):
    """精确计算每段推理时间，合并批量工具调用 (gap < 500ms)。
    返回: (segments_list, total_inference_ms, total_tool_ms)
    segments_list: [(label, ms, tool_indices)]  tool_indices = list of int
    """
    BATCH_GAP_MS = 500
    segments = []  # [(label, ms, tool_indices)]
    total_tool_ms = 0

    if not r["first_token"]:
        return segments, 0, 0

    ft = parse_time(r["first_token"])
    if not ft:
        return segments, 0, 0

    tools = r["tools"]

    if not tools:
        if r["end"]:
            run_end = parse_time(r["end"])
            if run_end:
                total_ms = (run_end - ft).total_seconds() * 1000
                segments.append(("推理#1(生成回复)", total_ms, []))
        return segments, sum(ms for _, ms, _ in segments), 0

    # Parse all tool times
    parsed = []  # [(start_dt, end_dt, index)]
    for idx, tool in enumerate(tools):
        ts = parse_time(tool["start"])
        te = parse_time(tool["end"]) if tool["end"] else None
        if ts:
            parsed.append((ts, te, idx))

    if not parsed:
        return segments, 0, 0

    # Group into batches by gap < 500ms
    batches = []  # each batch = [(start_dt, end_dt, tool_idx), ...]
    current_batch = [parsed[0]]
    for i in range(1, len(parsed)):
        prev_end = current_batch[-1][1]  # end of previous tool
        cur_start = parsed[i][0]
        if prev_end and cur_start and (cur_start - prev_end).total_seconds() * 1000 < BATCH_GAP_MS:
            current_batch.append(parsed[i])
        else:
            batches.append(current_batch)
            current_batch = [parsed[i]]
    batches.append(current_batch)

    # Calculate tool_ms
    for batch in batches:
        for ts, te, idx in batch:
            if ts and te:
                total_tool_ms += (te - ts).total_seconds() * 1000

    # Build inference segments
    prev_end = ft  # starts at agent_start (first_token)

    for b_idx, batch in enumerate(batches):
        batch_start = batch[0][0]  # first tool start in batch
        tool_indices = [item[2] for item in batch]

        # Inference before this batch
        infer_ms = (batch_start - prev_end).total_seconds() * 1000
        if infer_ms > 0:
            segments.append((f"推理#{len(segments)+1}", infer_ms, tool_indices))

        # Update prev_end to end of last tool in batch
        last_end = batch[-1][1]
        if last_end:
            prev_end = last_end
        else:
            prev_end = batch[-1][0]

    # Final segment: last batch end -> run_end
    if r["end"] and prev_end:
        run_end = parse_time(r["end"])
        if run_end:
            last_ms = (run_end - prev_end).total_seconds() * 1000
            if last_ms > 0:
                segments.append((f"推理#{len(segments)+1}(生成回复)", last_ms, []))

    total_infer = sum(ms for _, ms, _ in segments)
    return segments, total_infer, total_tool_ms

run_durations = []
model_times = []
tool_times = []

for run_id, r in sorted_runs:
    if r["start"] and r["end"]:
        s = parse_time(r["start"])
        e = parse_time(r["end"])
        if s and e:
            run_durations.append((e - s).total_seconds() * 1000)

    # 从 session 数据计算推理总时间
    session_uuid_g = r.get("session_uuid", "")
    matched_g = []
    
    # 策略1: 通过 session_uuid 匹配
    if session_uuid_g:
        run_start_g = parse_time(r["start"])
        run_end_g = parse_time(r["end"])
        for sk, evts in session_infer_events.items():
            if session_uuid_g in sk:
                if run_start_g and run_end_g:
                    for evt_g in evts:
                        evt_s_g = parse_time(evt_g["send_ts"])
                        evt_r_g = parse_time(evt_g["recv_ts"])
                        if evt_s_g and evt_r_g and evt_s_g >= run_start_g and evt_r_g <= run_end_g:
                            matched_g.append(evt_g)
                else:
                    matched_g.extend(evts)
                break
    
    # 策略2: 通过 session_key 匹配 (虚拟 Run)
    if not matched_g:
        session_key_g = r.get("session_key", "")
        if session_key_g in session_infer_events:
            matched_g = list(session_infer_events[session_key_g])
    
    # 策略3: 时间窗口匹配 (fallback)
    if not matched_g and r["start"] and r["end"]:
        run_start_g = parse_time(r["start"])
        run_end_g = parse_time(r["end"])
        if run_start_g and run_end_g:
            for evt_g in all_infer_events:
                try:
                    evt_s_g = parse_time(evt_g["send_ts"])
                    evt_r_g = parse_time(evt_g["recv_ts"])
                    if evt_s_g and evt_r_g and evt_s_g >= run_start_g and evt_r_g <= run_end_g:
                        matched_g.append(evt_g)
                except:
                    pass
    total_infer_g = sum(e["inference_ms"] for e in matched_g)
    if total_infer_g > 0:
        model_times.append(total_infer_g)

    for tool in r["tools"]:
        if tool["start"] and tool["end"]:
            ts = parse_time(tool["start"])
            te = parse_time(tool["end"])
            if ts and te:
                tool_times.append((te - ts).total_seconds() * 1000)
        elif tool.get("virtual_duration_ms", 0) > 0:
            tool_times.append(tool["virtual_duration_ms"])

print(f"  Run 总数:        {total_runs}")
print(f"  工具调用总数:    {total_tools}")
print(f"  消息发送总数:    {total_sends}")
print(f"  错误总数:        {total_errors}")
if tool_params:
    print(f"  工具参数已加载:  {len(tool_params)} 条 (来自会话文件)")
else:
    print(f"  工具参数:        未加载 (会话目录未找到或为空)")

# 工具调用成功率统计 (基于 tool_details)
if tool_details:
    td_total = len(tool_details)
    td_errors = sum(1 for d in tool_details.values() if d.get("isError"))
    td_success_rate = ((td_total - td_errors) / td_total * 100) if td_total > 0 else 0
    td_durations = [d["durationMs"] for d in tool_details.values() if d.get("durationMs") is not None and d["durationMs"] > 0]
    avg_ms_str = f"{sum(td_durations)/len(td_durations):.0f}ms" if td_durations else "N/A"
    # Top 3 工具
    td_name_counts = defaultdict(int)
    for d in tool_details.values():
        if d.get("toolName"):
            td_name_counts[d["toolName"]] += 1
    top3 = sorted(td_name_counts.items(), key=lambda x: -x[1])[:3]
    top3_str = ", ".join(f"{n}({c})" for n, c in top3)
    print(f"  工具调用:        {td_total} 次 (失败 {td_errors}, 成功率 {td_success_rate:.0f}%)")
    print(f"  工具平均耗时:    {avg_ms_str}")
    if top3_str:
        print(f"  Top 工具:        {top3_str}")
print()

if run_durations:
    avg_run = sum(run_durations) / len(run_durations)
    max_run = max(run_durations)
    min_run = min(run_durations)
    print(f"  Run 耗时:    平均 {fmt_duration(avg_run)}  最短 {fmt_duration(min_run)}  最长 {fmt_duration(max_run)}")

if model_times:
    avg_model = sum(model_times) / len(model_times)
    max_model = max(model_times)
    print(f"  模型推理:    平均 {fmt_duration(avg_model)}  最长 {fmt_duration(max_model)}")

# 从 session-based per-call 数据计算平均推理延迟和吞吐量
all_inference_ms = []
all_tokens_per_sec = []
for u in inference_usage.values():
    if u.get("inference_ms", 0) > 0:
        all_inference_ms.append(u["inference_ms"])
    if u.get("tokens_per_sec", 0) > 0:
        all_tokens_per_sec.append(u["tokens_per_sec"])
for _, u in text_reply_usage:
    if u.get("inference_ms", 0) > 0:
        all_inference_ms.append(u["inference_ms"])
    if u.get("tokens_per_sec", 0) > 0:
        all_tokens_per_sec.append(u["tokens_per_sec"])
# 去重 (同一 usage_record 可能被多个 toolCallId 引用)
seen_ids = set()
dedup_inference_ms = []
dedup_tokens_per_sec = []
for u in inference_usage.values():
    if id(u) in seen_ids:
        continue
    seen_ids.add(id(u))
    if u.get("inference_ms", 0) > 0:
        dedup_inference_ms.append(u["inference_ms"])
    if u.get("tokens_per_sec", 0) > 0:
        dedup_tokens_per_sec.append(u["tokens_per_sec"])
for _, u in text_reply_usage:
    if id(u) in seen_ids:
        continue
    seen_ids.add(id(u))
    if u.get("inference_ms", 0) > 0:
        dedup_inference_ms.append(u["inference_ms"])
    if u.get("tokens_per_sec", 0) > 0:
        dedup_tokens_per_sec.append(u["tokens_per_sec"])
if dedup_inference_ms:
    avg_inf = sum(dedup_inference_ms) / len(dedup_inference_ms)
    print(f"  推理延迟:    平均 {fmt_duration(avg_inf)}  (基于 session 时间戳, {len(dedup_inference_ms)} 次调用)")
if dedup_tokens_per_sec:
    avg_tps = sum(dedup_tokens_per_sec) / len(dedup_tokens_per_sec)
    print(f"  Token 吞吐:  平均 {avg_tps:.1f} tok/s  (基于 session 时间戳, {len(dedup_tokens_per_sec)} 次调用)")

if tool_times:
    avg_tool = sum(tool_times) / len(tool_times)
    max_tool = max(tool_times)
    print(f"  工具执行:    平均 {fmt_duration(avg_tool)}  最长 {fmt_duration(max_tool)}")

# 工具使用统计
if total_tools > 0:
    tool_counts = defaultdict(int)
    tool_dur = defaultdict(list)
    for _, r in sorted_runs:
        for tool in r["tools"]:
            tool_counts[tool["name"]] += 1
            if tool["start"] and tool["end"]:
                ts = parse_time(tool["start"])
                te = parse_time(tool["end"])
                if ts and te:
                    tool_dur[tool["name"]].append((te - ts).total_seconds() * 1000)
            elif tool.get("virtual_duration_ms", 0) > 0:
                tool_dur[tool["name"]].append(tool["virtual_duration_ms"])

    print()
    print("  工具使用排行:")
    for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        avg = sum(tool_dur.get(name, [0])) / max(len(tool_dur.get(name, [1])), 1)
        print(f"    {name:<20} {count:>3}次  平均耗时 {fmt_duration(avg)}")

# Agent 活动分布
agent_stats = defaultdict(lambda: {"infer_count": 0, "total_infer_ms": 0, "total_output": 0, "tool_count": 0, "sessions": set()})
for sk, evts in session_infer_events.items():
    agent_name = sk.split(":")[0] if ":" in sk else "unknown"
    for evt in evts:
        if not (date_matches_utc(evt.get("send_ts", ""), DIAG_DATE) or date_matches_utc(evt.get("recv_ts", ""), DIAG_DATE)):
            continue
        agent_stats[agent_name]["infer_count"] += 1
        agent_stats[agent_name]["total_infer_ms"] += evt.get("inference_ms", 0)
        agent_stats[agent_name]["total_output"] += evt.get("output_tokens", 0)
        agent_stats[agent_name]["sessions"].add(sk)
# 工具统计（从 tool_details）
for td in tool_details.values():
    # 尝试从 session_key 推导 agent
    td_sk = td.get("session_key", "")
    td_agent = td_sk.split(":")[0] if ":" in td_sk else ""
    if td_agent:
        agent_stats[td_agent]["tool_count"] += 1

if len(agent_stats) > 1 or (len(agent_stats) == 1 and list(agent_stats.keys())[0] != "main"):
    print()
    print("  Agent 活动分布:")
    for agent_name in sorted(agent_stats.keys()):
        s = agent_stats[agent_name]
        infer = s["infer_count"]
        total_ms = s["total_infer_ms"]
        total_out = s["total_output"]
        sessions = len(s["sessions"])
        avg_ms_str = fmt_duration(total_ms / infer) if infer > 0 else "N/A"
        tps = total_out / (total_ms / 1000) if total_ms > 0 else 0
        tps_str = f"{tps:.1f} tok/s" if tps > 0 else "N/A"
        print(f"    {agent_name:<15} 推理 {infer:>3}次  平均 {avg_ms_str:>8}  吞吐 {tps_str:>10}  会话 {sessions}")

if SUMMARY_ONLY:
    if errors:
        print()
        print("  最近错误:")
        for t, emsg in errors[-5:]:
            display = emsg
            try:
                pj = json.loads(emsg)
                if isinstance(pj, dict):
                    for k in ("error", "message", "msg"):
                        if k in pj:
                            display = f"{k}: {pj[k]}"; break
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            if len(display) > 100:
                display = display[:97] + "..."
            print(f"    {t[11:19]} [ERROR] {display}")
    sys.exit(0)

# ============================================================
# 5. 每个 Run 详情
# ============================================================
print()
print("=" * 68)
print(f"{'[Run 详情]':^64}")
print("=" * 68)

for i, (run_id, r) in enumerate(sorted_runs):
    if not r["start"]:
        continue

    start_time = parse_time(r["start"])
    end_time = parse_time(r["end"]) if r["end"] else None
    total_ms = (end_time - start_time).total_seconds() * 1000 if end_time and start_time else None

    print()
    if r["end"]:
        status = "[完成]"
    else:
        status = "[进行中]"
    if r.get("virtual"):
        status = "[虚拟]"
    total_str = fmt_duration(total_ms) if total_ms else "进行中"
    print(f"  Run #{i+1}  {status}  总耗时: {total_str}")
    print(f"  {'-' * 62}")
    print(f"  Run ID:     {run_id}")
    print(f"  模型:       {r['model']}")
    print(f"  渠道:       {r['channel']}")
    if r["session_key"]:
        print(f"  会话:       {r['session_key']}")
    if r["prompt_messages"]:
        print(f"  历史消息数: {r['prompt_messages']}")
    _start_dt = parse_time(r['start'])
    _end_dt = parse_time(r['end']) if r['end'] else None
    _start_str = _start_dt.strftime("%H:%M:%S.%f")[:-3] if _start_dt else r['start'][11:23]
    _end_str = _end_dt.strftime("%H:%M:%S.%f")[:-3] if _end_dt else (r['end'][11:23] if r['end'] else "")
    print(f"  开始时间:   {_start_str}", end="")
    if _end_str:
        print(f"  结束时间: {_end_str}")
    else:
        print()

    # 时间线
    print()
    print(f"  {'时间':>12} {'间隔':>9}  {'步骤说明'}")
    print(f"  {'─'*12} {'─'*9}  {'─'*42}")

    timeline = []

    timeline.append((r["start"], "[RUN-START]  开始处理请求"))

    for t, msg in r["events"]:
        if "pre-prompt" in msg:
            detail = ""
            if "messages=" in msg:
                detail = f", 包含 {msg.split('messages=')[1].split(' ')[0]} 条历史消息"
            timeline.append((t, f"[PROMPT]     构建提示词{detail}"))
            break

    # 收集所有 model send/recv 事件（支持多轮推理）
    # 从 session 获取推理事件
    matched_session_events = []
    session_key = r.get("session_key", "")
    session_uuid = r.get("session_uuid", "")

    # 策略1: 通过 session_uuid 匹配 (session_infer_events keyed by "{agent}:{uuid}")
    # session_uuid 来自日志的 sessionId=
    if session_uuid:
        for sk, evts in session_infer_events.items():
            # sk format: "main:b5a65d81-..." or just "b5a65d81-..."
            if session_uuid in sk:
                # 按 Run 时间窗口过滤
                run_start_dt = parse_time(r["start"])
                run_end_dt = parse_time(r["end"])
                if run_start_dt and run_end_dt:
                    for evt in evts:
                        evt_send_dt = parse_time(evt["send_ts"])
                        evt_recv_dt = parse_time(evt["recv_ts"])
                        if evt_send_dt and evt_recv_dt:
                            if evt_send_dt >= run_start_dt and evt_recv_dt <= run_end_dt:
                                matched_session_events.append(evt)
                else:
                    matched_session_events.extend(evts)
                break

    # 策略2: 通过 session_key 精确匹配 (虚拟 Run 使用)
    if not matched_session_events and session_key and session_key in session_infer_events:
        matched_session_events = list(session_infer_events[session_key])
        # 对虚拟 Run，按日期过滤（session 可能跨天）
        if r.get("virtual") and DIAG_DATE:
            matched_session_events = [e for e in matched_session_events if e["send_ts"][:10] == DIAG_DATE]

    # 策略3: 时间窗口匹配 (fallback)
    if not matched_session_events and r["start"] and r["end"]:
        run_start_dt = parse_time(r["start"])
        run_end_dt = parse_time(r["end"])
        if run_start_dt and run_end_dt:
            for evt in all_infer_events:
                try:
                    evt_send_dt = parse_time(evt["send_ts"])
                    evt_recv_dt = parse_time(evt["recv_ts"])
                    if evt_send_dt and evt_recv_dt:
                        if evt_send_dt >= run_start_dt and evt_recv_dt <= run_end_dt:
                            matched_session_events.append(evt)
                except:
                    pass

    if matched_session_events:
        # 使用 session 推理事件
        for idx_evt, evt in enumerate(matched_session_events, 1):
            send_ts = evt["send_ts"]
            recv_ts = evt["recv_ts"]
            inf_ms = evt["inference_ms"]
            in_tok = evt["input_tokens"]
            out_tok = evt["output_tokens"]
            cache_read = evt.get("cache_read", 0)
            tps = evt["tokens_per_sec"]
            timeline.append((send_ts, f"[MODEL-SEND] 模型推理开始 (第{idx_evt}次)"))
            recv_detail = f"[MODEL-RECV] 模型推理完成 (第{idx_evt}次) 耗时 {fmt_duration(inf_ms)}"
            if in_tok or out_tok:
                tok_parts = [f"in={in_tok}", f"out={out_tok}"]
                if cache_read:
                    tok_parts.append(f"cache={cache_read}")
                recv_detail += f" | {' '.join(tok_parts)}"
            if tps > 0:
                recv_detail += f" ({tps:.1f} tok/s)"
            timeline.append((recv_ts, recv_detail))
        # 标记已使用 session 数据，避免日志重复
        used_session_model_events = True

    for tool in r["tools"]:
        tid = tool["id"]
        tname = tool["name"]

        # 从会话文件获取工具参数
        param_info = tool_params.get(tid, {})
        param_summary = param_info.get("summary", "")
        param_workdir = param_info.get("workdir", "")

        # 构建工具开始的描述
        start_label = f"[TOOL-START] 开始执行工具: {tname}"
        if param_summary:
            start_label += f"\n               {'':>9}  {'':>13}{param_summary}"
        if param_workdir:
            start_label += f"\n               {'':>9}  {'':>13}工作目录: {param_workdir}"

        # 虚拟 Run 的工具没有精确时间戳，跳过 timeline 添加
        if not tool["start"]:
            # 对虚拟 Run，在 timeline 不添加工具的时间戳行
            # 但在汇总中通过 virtual_duration_ms 计入
            continue

        timeline.append((tool["start"], start_label))

        if tool["end"]:
            ts = parse_time(tool["start"])
            te = parse_time(tool["end"])
            dur = fmt_duration((te - ts).total_seconds() * 1000) if ts and te else "?"
            # 附加 details 信息
            detail_extra = ""
            td = tool_details.get(tid, {})
            if td:
                if tname == "exec":
                    ec = td.get("exitCode")
                    dm = td.get("durationMs")
                    parts = []
                    if ec is not None:
                        if ec != 0:
                            parts.append(f"\033[31mexitCode={ec}\033[0m")
                        else:
                            parts.append(f"exitCode={ec}")
                    if dm is not None:
                        parts.append(f"duration={dm}ms")
                    if parts:
                        detail_extra = "  " + " ".join(parts)
                elif tname == "edit":
                    diff = td.get("diff", "")
                    if diff:
                        diff_short = diff.replace("\n", " ")[:60]
                        detail_extra = f"  diff: {diff_short}"
                elif tname == "web_fetch":
                    took = td.get("tookMs")
                    if took is not None:
                        detail_extra = f"  took={took}ms"
                elif tname == "sessions_spawn":
                    csk = td.get("childSessionKey", "")
                    if csk:
                        detail_extra = f"  child={csk}"
                if td.get("isError"):
                    detail_extra += "  \033[31m[FAILED]\033[0m"
            timeline.append((tool["end"], f"[TOOL-END]   工具执行完成: {tname} (耗时 {dur}){detail_extra}"))

    if r["end"]:
        timeline.append((r["end"], "[RUN-END]    处理完成, 准备返回结果"))

    timeline.sort(key=lambda x: parse_time(x[0]) or datetime.min)

    prev = None
    for t, label in timeline:
        curr = parse_time(t)
        ts = curr.strftime("%H:%M:%S.%f")[:-3] if curr else t[11:23]
        if prev:
            delta_ms = (curr - prev).total_seconds() * 1000
            delta_str = fmt_duration(delta_ms)
            if delta_ms > 5000:
                marker = "  << 慢"
            elif delta_ms > 1000:
                marker = "  < 较慢"
            else:
                marker = ""
        else:
            delta_str = "---"
            marker = ""
        prev = curr

        # 处理多行标签（工具参数）
        lines = label.split("\n")
        print(f"  {ts:>12} {delta_str:>9}  {lines[0]}{marker}")
        for extra_line in lines[1:]:
            print(f"  {extra_line}")

    # ========== Run 汇总 (纯 session 数据) ==========
    print()

    # 从 matched_session_events 计算推理/token 汇总
    run_total_input = 0
    run_total_output = 0
    run_total_cache_read = 0
    run_total_cache_write = 0
    run_total_tokens = 0
    run_inference_count = len(matched_session_events)

    total_infer = 0
    for evt_s in matched_session_events:
        total_infer += evt_s["inference_ms"]
        run_total_input += evt_s["input_tokens"]
        run_total_output += evt_s["output_tokens"]
        run_total_cache_read += evt_s.get("cache_read", 0)
        run_total_cache_write += evt_s.get("cache_write", 0)

    # 工具总耗时
    total_tool = 0
    for tool in r["tools"]:
        if tool["start"] and tool["end"]:
            ts_t = parse_time(tool["start"])
            te_t = parse_time(tool["end"])
            if ts_t and te_t:
                total_tool += (te_t - ts_t).total_seconds() * 1000
        elif tool.get("virtual_duration_ms", 0) > 0:
            total_tool += tool["virtual_duration_ms"]

    run_total_tokens = run_total_input + run_total_output + run_total_cache_read + run_total_cache_write

    # --- 汇总输出 ---
    print(f"  {'─'*62}")
    print(f"  [Run 汇总]")
    print()
    if total_ms:
        print(f"    端到端耗时:     {fmt_duration(total_ms)}")
    print(f"    模型推理总耗时: {fmt_duration(total_infer)}", end="")
    if total_ms and total_infer > 0:
        print(f" ({total_infer/total_ms*100:.0f}%)", end="")
    print()
    if total_tool > 0:
        print(f"    工具执行总耗时: {fmt_duration(total_tool)}", end="")
        if total_ms:
            print(f" ({total_tool/total_ms*100:.0f}%)", end="")
        print()
    if total_ms:
        other_ms = total_ms - total_infer - total_tool
        if other_ms > 200:
            print(f"    其他开销:       {fmt_duration(other_ms)} ({other_ms/total_ms*100:.0f}%)")
    print(f"    推理调用次数:   {run_inference_count}")
    print(f"    工具调用次数:   {len(r['tools'])}")
    print()

    # token 统计
    print(f"    Token 统计:")
    print(f"      输入 token:   {run_total_input:>8}")
    print(f"      输出 token:   {run_total_output:>8}")
    print(f"      缓存读取:     {run_total_cache_read:>8}")
    print(f"      缓存写入:     {run_total_cache_write:>8}")
    if run_total_output > 0 and total_infer > 0:
        tps = run_total_output / (total_infer / 1000)
        print(f"      输出速率:     {tps:>7.1f} tokens/s")

    # 耗时分布条形图
    if total_ms and total_ms > 0:
        print()
        print(f"    耗时分布:")
        print(f"      模型推理 {bar(total_infer, total_ms)}  {fmt_duration(total_infer):>8}")
        if total_tool > 0:
            print(f"      工具执行 {bar(total_tool, total_ms)}  {fmt_duration(total_tool):>8}")

    # 推理分段明细 (纯 session 数据)
    if matched_session_events:
        print()
        print(f"    推理分段明细:")
        print(f"      {'段':^24} {'耗时':>8} {'输出token':>10} {'速率':>12}")
        print(f"      {'─'*24} {'─'*8} {'─'*10} {'─'*12}")
        for idx_s, evt in enumerate(matched_session_events, 1):
            inf_ms = evt["inference_ms"]
            out_tok = evt["output_tokens"]
            tps = evt["tokens_per_sec"]
            label = f"推理#{idx_s}"
            dur_str = fmt_duration(inf_ms) if inf_ms > 0 else "-"
            out_str = str(out_tok) if out_tok > 0 else "(未知)"
            rate_str = f"{tps:.1f} tok/s" if tps > 0 else "-"
            print(f"      {label:<24} {dur_str:>8} {out_str:>10} {rate_str:>12}")

# ============================================================
# 6. 错误列表
# ============================================================
if errors:
    print()
    print("=" * 68)
    print(f"{'[错误列表]':^64}")
    print("=" * 68)
    shown = min(len(errors), 20)
    print(f"  共 {len(errors)} 条错误，显示最近 {shown} 条:")
    print()
    INDENT = "      "
    MAX_WIDTH = 120
    for idx, (t, emsg) in enumerate(errors[-20:], 1):
        # 尝试从 JSON 格式消息中提取关键字段
        display_msg = emsg
        try:
            parsed_json = json.loads(emsg)
            if isinstance(parsed_json, dict):
                key_parts = []
                for k in ("error", "message", "msg", "reason", "description"):
                    if k in parsed_json:
                        key_parts.append(f"{k}: {parsed_json[k]}")
                if key_parts:
                    display_msg = " | ".join(key_parts)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        print(f"  #{idx:<3} {t[11:19]}  [ERROR]")
        # 自动换行缩进
        line = display_msg
        while len(line) > MAX_WIDTH:
            # 找一个合适的断点
            cut = MAX_WIDTH
            # 尝试在空格处断开
            sp = line.rfind(" ", 0, cut)
            if sp > cut // 2:
                cut = sp + 1
            print(f"{INDENT}{line[:cut]}")
            line = line[cut:]
        if line:
            print(f"{INDENT}{line}")
        print()

print()
print("=" * 68)
PYEOF
