#!/bin/bash

# byted-ind-h-edu-prj-apply-material — 课题申报材料生成技能依赖安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log() {
    echo "[byted-ind-h-edu-prj-apply-material] $1"
}

log "开始安装依赖..."

# 创建虚拟环境（如果不存在）
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    log "创建虚拟环境..."
    python3 -m venv "$PROJECT_ROOT/venv"
fi

# 激活虚拟环境
source "$PROJECT_ROOT/venv/bin/activate"

# 升级pip
log "升级pip..."
pip install --upgrade pip

# 安装依赖
log "安装核心依赖..."
pip install -r "$PROJECT_ROOT/requirements.txt" || {
    log "警告：requirements.txt 不存在，安装默认依赖"
    pip install pandas numpy matplotlib seaborn
}

# 安装可选依赖
log "安装可选依赖..."
pip install --upgrade setuptools wheel

# 创建必要的目录
log "创建必要的目录..."
mkdir -p "$PROJECT_ROOT/output"
mkdir -p "$PROJECT_ROOT/output/figures"
mkdir -p "$PROJECT_ROOT/temp"

# 设置执行权限
log "设置执行权限..."
chmod +x "$SCRIPT_DIR/generate_apply_material.py"

log "依赖安装完成！"
log "使用方法："
log "  1. 激活虚拟环境：source venv/bin/activate"
log "  2. 运行脚本：python scripts/generate_apply_material.py --help"
log "  3. 示例：python scripts/generate_apply_material.py --project-type national --project-level general --topic \"人工智能在教育中的应用\" --applicant \"张三\" --organization \"某某大学\" --duration 24 --budget 20 --output-format word"
