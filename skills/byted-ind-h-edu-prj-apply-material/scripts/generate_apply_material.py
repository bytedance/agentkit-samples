#!/usr/bin/env python3
"""
byted-ind-h-edu-prj-apply-material — 课题申报材料生成脚本

针对各级各类课题申报要求，生成课题申报书框架、研究内容、技术路线、创新点、可行性分析等内容。

用法：
    python generate_apply_material.py --project-type national --project-level general --topic "人工智能在教育中的应用" --applicant "张三" --organization "某某大学" --duration 24 --budget 20 --output-format word --language 中文
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime


# ── 配置 ───────────────────────────────────────────────────────────
REFERENCES_DIR = os.path.join(os.path.dirname(__file__), "..", "references")
OUTPUT_DIR = "output"
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
DEFAULT_ENCODING = "utf-8"


# ── 工具函数 ───────────────────────────────────────────────────────
def log(msg):
    """统一日志输出"""
    print(msg, file=sys.stderr, flush=True)


def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def read_template(filename):
    """读取模板文件"""
    template_path = os.path.join(REFERENCES_DIR, filename)
    if not os.path.exists(template_path):
        log(f"❌ 模板文件不存在: {template_path}")
        return ""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        log(f"❌ 读取模板文件失败: {e}")
        return ""


def load_project_templates():
    """加载课题模板"""
    template_content = read_template("project-templates.md")
    if not template_content:
        return {}

    # 这里应该实现模板解析逻辑
    # 为了简化，返回一个默认模板结构
    return {
        "national": {
            "key": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 20000,
            },
            "general": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 15000,
            },
            "young": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 12000,
            },
        },
        "provincial": {
            "key": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 15000,
            },
            "general": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 12000,
            },
            "young": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 10000,
            },
        },
        "school": {
            "key": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 8000,
            },
            "general": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 6000,
            },
            "young": {
                "sections": [
                    "基本信息",
                    "摘要",
                    "研究背景与意义",
                    "国内外研究现状",
                    "研究目标",
                    "研究内容",
                    "研究方法",
                    "创新点",
                    "预期成果",
                    "研究基础",
                    "工作条件",
                    "经费预算",
                    "研究计划",
                ],
                "word_limit": 5000,
            },
        },
        "horizontal": {
            "key": {
                "sections": [
                    "基本信息",
                    "项目背景",
                    "研究内容",
                    "技术方案",
                    "交付成果",
                    "实施计划",
                    "经费预算",
                    "双方责任",
                    "知识产权",
                    "验收标准",
                ],
                "word_limit": 12000,
            },
            "general": {
                "sections": [
                    "基本信息",
                    "项目背景",
                    "研究内容",
                    "技术方案",
                    "交付成果",
                    "实施计划",
                    "经费预算",
                    "双方责任",
                    "知识产权",
                    "验收标准",
                ],
                "word_limit": 10000,
            },
            "young": {
                "sections": [
                    "基本信息",
                    "项目背景",
                    "研究内容",
                    "技术方案",
                    "交付成果",
                    "实施计划",
                    "经费预算",
                    "双方责任",
                    "知识产权",
                    "验收标准",
                ],
                "word_limit": 8000,
            },
        },
    }


def generate_basic_info(args):
    """生成基本信息部分"""
    basic_info = f"""
## 基本信息

| 项目 | 内容 |
|------|------|
| 项目名称 | {args.topic} |
| 课题类型 | {args.project_type} |
| 课题级别 | {args.project_level} |
| 申报人 | {args.applicant} |
| 依托单位 | {args.organization} |
| 研究周期 | {args.duration} 个月 |
| 经费预算 | {args.budget} 万元 |
| 申报日期 | {datetime.now().strftime("%Y-%m-%d")} |
"""
    return basic_info


def generate_abstract(topic):
    """生成摘要部分"""
    abstract = f"""
## 摘要

本课题以"{topic}"为研究对象，针对当前研究中存在的问题，采用科学的研究方法，系统开展研究工作。研究内容包括：研究背景与意义、国内外研究现状、研究目标与内容、技术路线与方法、创新点与特色、预期成果与效益等。通过本课题的研究，预期将取得重要的学术成果和应用价值，为相关领域的发展提供理论支持和实践指导。
"""
    return abstract


def generate_research_background(topic):
    """生成研究背景与意义部分"""
    background = f"""
## 研究背景与意义

### 研究背景

随着社会的发展和科技的进步，"{topic}"已成为当前研究的热点领域。近年来，相关研究取得了显著进展，但仍存在一些问题和挑战，需要进一步深入研究。

### 研究意义

本课题的研究具有重要的理论意义和实践价值：

1. **理论意义**：通过系统研究，丰富和发展相关理论体系，为后续研究提供理论基础。
2. **实践价值**：解决实际问题，推动相关领域的发展，为社会经济发展做出贡献。
3. **学术价值**：促进学术交流与合作，提高学术水平和影响力。
"""
    return background


def generate_research_status():
    """生成国内外研究现状部分"""
    status = """
## 国内外研究现状

### 国外研究现状

国外在相关领域的研究起步较早，已取得了一系列重要成果。主要研究方向包括：理论研究、方法研究、应用研究等。国外研究的特点是注重理论创新和方法创新，研究水平较高。

### 国内研究现状

国内在相关领域的研究虽然起步较晚，但发展迅速，已形成了一定的研究体系。主要研究方向包括：应用研究、技术研究、政策研究等。国内研究的特点是注重实际应用和本土化创新。

### 研究不足

现有研究存在以下不足：
1. 理论研究不够深入，缺乏系统性和创新性。
2. 方法研究不够完善，缺乏科学的研究方法和技术路线。
3. 应用研究不够广泛，缺乏实际应用案例和效果评估。
4. 跨学科研究不够充分，缺乏多学科融合和交叉创新。

### 研究趋势

未来研究的发展趋势包括：
1. 理论研究将更加深入，注重系统性和创新性。
2. 方法研究将更加完善，注重科学的研究方法和技术路线。
3. 应用研究将更加广泛，注重实际应用案例和效果评估。
4. 跨学科研究将更加充分，注重多学科融合和交叉创新。
"""
    return status


def generate_research_goals():
    """生成研究目标部分"""
    goals = """
## 研究目标

### 总体目标

本课题的总体目标是：系统研究相关领域的理论和实践问题，提出创新的理论和方法，为相关领域的发展提供理论支持和实践指导。

### 具体目标

1. 深入研究相关领域的理论体系，提出创新的理论观点。
2. 完善相关领域的研究方法，建立科学的研究方法体系。
3. 开展相关领域的应用研究，验证研究成果的实际效果。
4. 培养相关领域的研究人才，提高研究队伍的整体水平。
"""
    return goals


def generate_research_content(topic):
    """生成研究内容部分"""
    content = f"""
## 研究内容

### 主要研究内容

1. **理论研究**：深入研究"{topic}"的理论体系，提出创新的理论观点和方法。
2. **方法研究**：完善"{topic}"的研究方法，建立科学的研究方法体系。
3. **应用研究**：开展"{topic}"的应用研究，验证研究成果的实际效果。
4. **案例研究**：选择典型案例进行深入分析，总结经验和教训。

### 关键科学问题

1. **理论问题**：如何构建科学的"{topic}"理论体系？
2. **方法问题**：如何建立有效的"{topic}"研究方法？
3. **应用问题**：如何将"{topic}"的研究成果应用到实际中？
4. **评价问题**：如何评价"{topic}"研究成果的实际效果？
"""
    return content


def generate_research_methods():
    """生成研究方法部分"""
    methods = """
## 研究方法与技术路线

### 研究方法

1. **文献研究法**：系统收集和分析相关文献，了解研究现状和发展趋势。
2. **实证研究法**：通过实验、调查等方式，获取第一手资料，验证研究假设。
3. **案例研究法**：选择典型案例进行深入分析，总结经验和教训。
4. **比较研究法**：比较不同国家和地区的研究成果，借鉴先进经验。
5. **系统分析法**：运用系统科学的方法，分析研究对象的整体结构和功能。

### 技术路线

1. **准备阶段**：收集资料，确定研究方案，组建研究团队。
2. **实施阶段**：开展文献研究、实证研究、案例研究等。
3. **分析阶段**：整理和分析研究数据，得出研究结论。
4. **总结阶段**：撰写研究报告，发表研究成果，推广研究经验。

### 关键技术

1. **数据采集技术**：运用现代信息技术，采集和处理研究数据。
2. **数据分析技术**：运用统计分析、机器学习等方法，分析研究数据。
3. **模型构建技术**：构建科学的理论模型和数学模型，模拟研究对象的行为。
4. **成果转化技术**：将研究成果转化为实际应用，产生经济效益和社会效益。
"""
    return methods


def generate_innovations():
    """生成创新点部分"""
    innovations = """
## 创新点与特色

### 创新点

1. **理论创新**：提出新的理论观点和方法，丰富和发展相关理论体系。
2. **方法创新**：建立新的研究方法和技术路线，提高研究的科学性和有效性。
3. **应用创新**：开发新的应用模式和技术方案，解决实际问题。
4. **跨学科创新**：融合多学科的理论和方法，产生交叉创新成果。

### 特色

1. **研究视角**：采用独特的研究视角，从新的角度分析研究对象。
2. **研究方法**：运用先进的研究方法和技术手段，提高研究的质量和水平。
3. **研究内容**：选择具有重要理论和实践意义的研究内容，突出研究的价值。
4. **预期成果**：预期产生具有重要影响的研究成果，为相关领域的发展做出贡献。
"""
    return innovations


def generate_expected_results():
    """生成预期成果部分"""
    results = """
## 预期成果与效益

### 预期成果

1. **学术成果**：发表高水平学术论文5-8篇，其中SCI/EI收录论文3-5篇。
2. **应用成果**：开发相关技术和产品1-2项，申请发明专利1-2项。
3. **人才培养**：培养研究生3-5名，提高研究团队的整体水平。
4. **平台建设**：建立相关研究平台和数据库，为后续研究提供支持。

### 预期效益

1. **经济效益**：通过技术转让、产品开发等方式，产生一定的经济效益。
2. **社会效益**：解决实际问题，提高社会服务能力，产生良好的社会效益。
3. **学术影响**：提高学术水平和影响力，促进学术交流与合作。
4. **应用价值**：为相关领域的发展提供理论支持和实践指导，具有重要的应用价值。
"""
    return results


def generate_research_basis():
    """生成研究基础部分"""
    basis = """
## 研究基础与条件

### 研究基础

1. **前期研究成果**：已发表相关学术论文10余篇，其中SCI/EI收录论文5篇。
2. **研究团队**：研究团队由具有丰富经验的专家学者组成，涵盖多个学科领域。
3. **相关项目**：已完成或正在进行相关研究项目2-3项，积累了丰富的研究经验。
4. **学术积累**：具有扎实的理论基础和丰富的研究经验，为课题研究提供了有力支撑。

### 研究条件

1. **实验设备**：拥有先进的实验设备和仪器，满足研究需要。
2. **图书资料**：拥有丰富的图书资料和数据库，为研究提供了充分的信息支持。
3. **合作单位**：与多家高校、科研机构和企业建立了良好的合作关系，为研究提供了广泛的支持。
4. **其他条件**：拥有良好的研究环境和工作条件，为研究的顺利开展提供了保障。
"""
    return basis


def generate_feasibility():
    """生成可行性分析部分"""
    feasibility = """
## 可行性分析

### 技术可行性

1. **技术路线可行性**：技术路线科学合理，符合研究的实际需要。
2. **研究方法可行性**：研究方法先进有效，能够解决研究中的关键问题。
3. **关键技术可行性**：关键技术成熟可靠，能够支撑研究的顺利开展。

### 经济可行性

1. **经费预算合理性**：经费预算合理，符合研究的实际需要。
2. **经费来源可靠性**：经费来源稳定可靠，能够保障研究的顺利开展。
3. **经济效益预期**：预期产生一定的经济效益，具有良好的投资回报。

### 组织可行性

1. **研究团队能力**：研究团队具有较强的研究能力和丰富的研究经验。
2. **管理机制**：建立了科学的管理机制，能够保障研究的顺利开展。
3. **合作机制**：建立了良好的合作机制，能够充分整合各方资源。

### 风险分析与应对措施

1. **风险分析**：识别研究过程中可能面临的风险，如技术风险、经费风险、时间风险等。
2. **应对措施**：制定相应的应对措施，如技术储备、经费管理、时间规划等，降低风险的影响。
"""
    return feasibility


def generate_budget(budget):
    """生成经费预算部分"""
    budget_content = f"""
## 经费预算

### 预算编制原则

1. **合理性**：预算编制合理，符合研究的实际需要。
2. **必要性**：预算项目必要，与研究内容直接相关。
3. **真实性**：预算数据真实，有依据。
4. **合规性**：预算编制符合相关经费管理规定。

### 预算明细

| 预算项目 | 金额（万元） | 占总预算比例 | 说明 |
|---------|------------|------------|------|
| 设备费 | {budget * 0.15:.2f} | 15% | 设备购置和维护 |
| 材料费 | {budget * 0.25:.2f} | 25% | 实验材料和试剂 |
| 测试化验加工费 | {budget * 0.15:.2f} | 15% | 委托测试化验 |
| 燃料动力费 | {budget * 0.05:.2f} | 5% | 实验室水电费 |
| 差旅费 | {budget * 0.10:.2f} | 10% | 学术交流和调研 |
| 会议费 | {budget * 0.05:.2f} | 5% | 学术会议 |
| 国际合作与交流费 | {budget * 0.05:.2f} | 5% | 国际学术交流 |
| 出版/文献/信息传播/知识产权事务费 | {budget * 0.05:.2f} | 5% | 论文出版和专利申请 |
| 劳务费 | {budget * 0.10:.2f} | 10% | 研究生劳务费 |
| 专家咨询费 | {budget * 0.025:.2f} | 2.5% | 专家咨询费 |
| 其他费用 | {budget * 0.025:.2f} | 2.5% | 其他必要费用 |
| **总预算** | {budget:.2f} | **100%** | |
"""
    return budget_content


def generate_research_plan(duration):
    """生成研究计划部分"""
    plan = f"""
## 研究计划与进度安排

### 总体研究计划

本课题计划在{duration}个月内完成，分为准备阶段、实施阶段、分析阶段和总结阶段。

### 具体进度安排

| 阶段 | 时间范围 | 主要任务 | 阶段目标 | 成果产出 |
|------|---------|---------|---------|----------|
| 准备阶段 | 第1-2个月 | 收集资料，确定研究方案，组建研究团队 | 完成研究准备工作 | 研究方案 |
| 实施阶段 | 第3-18个月 | 开展文献研究、实证研究、案例研究等 | 完成主要研究工作 | 研究数据 |
| 分析阶段 | 第19-22个月 | 整理和分析研究数据，得出研究结论 | 完成数据分析工作 | 分析报告 |
| 总结阶段 | 第23-24个月 | 撰写研究报告，发表研究成果，推广研究经验 | 完成研究总结工作 | 研究报告、学术论文 |
"""
    return plan


def generate_apply_material(args):
    """生成申报材料"""
    # 加载模板
    templates = load_project_templates()
    if not templates:
        log("❌ 加载模板失败")
        return ""

    # 确定模板
    project_type = args.project_type
    project_level = args.project_level
    if project_type not in templates:
        log(f"❌ 不支持的课题类型: {project_type}")
        return ""
    if project_level not in templates[project_type]:
        log(f"❌ 不支持的课题级别: {project_level}")
        return ""

    template = templates[project_type][project_level]
    sections = template["sections"]

    # 生成各部分内容
    content = f"# {args.topic} 课题申报书"

    if "基本信息" in sections:
        content += generate_basic_info(args)
    if "摘要" in sections:
        content += generate_abstract(args.topic)
    if "研究背景与意义" in sections:
        content += generate_research_background(args.topic)
    if "国内外研究现状" in sections:
        content += generate_research_status()
    if "研究目标" in sections:
        content += generate_research_goals()
    if "研究内容" in sections:
        content += generate_research_content(args.topic)
    if "研究方法" in sections or "技术方案" in sections:
        content += generate_research_methods()
    if "创新点" in sections or "创新之处" in sections:
        content += generate_innovations()
    if "预期成果" in sections or "交付成果" in sections:
        content += generate_expected_results()
    if "研究基础" in sections:
        content += generate_research_basis()
    if "可行性分析" in sections:
        content += generate_feasibility()
    if "经费预算" in sections:
        content += generate_budget(args.budget)
    if "研究计划" in sections or "实施计划" in sections:
        content += generate_research_plan(args.duration)

    return content


def export_material(content, output_format, output_file):
    """导出申报材料"""
    ensure_dir(OUTPUT_DIR)
    output_path = os.path.join(OUTPUT_DIR, output_file)

    if output_format == "markdown":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
    elif output_format == "word":
        # 这里应该实现导出为Word的逻辑
        with open(output_path.replace(".md", ".docx"), "w", encoding="utf-8") as f:
            f.write(content)
    elif output_format == "pdf":
        # 这里应该实现导出为PDF的逻辑
        with open(output_path.replace(".md", ".pdf"), "w", encoding="utf-8") as f:
            f.write(content)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="byted-ind-h-edu-prj-apply-material — 课题申报材料生成脚本"
    )

    # 项目基本信息
    parser.add_argument(
        "--project-type",
        choices=["national", "provincial", "school", "horizontal"],
        default="national",
        help="课题类型：national（国家级）、provincial（省部级）、school（校级）、horizontal（横向）",
    )
    parser.add_argument(
        "--project-level",
        choices=["key", "general", "young"],
        default="general",
        help="课题级别：key（重点）、general（一般）、young（青年）",
    )
    parser.add_argument("--topic", required=True, help="研究主题")
    parser.add_argument("--applicant", required=True, help="申报人")
    parser.add_argument("--organization", required=True, help="依托单位")
    parser.add_argument("--duration", type=int, default=24, help="研究周期（月）")
    parser.add_argument("--budget", type=float, default=20, help="经费预算（万元）")

    # 输出参数
    parser.add_argument(
        "--output-format",
        choices=["markdown", "word", "pdf"],
        default="word",
        help="输出格式：markdown、word、pdf",
    )
    parser.add_argument("--language", default="中文", help="输出语言")
    parser.add_argument("--output-file", default="project_apply.md", help="输出文件名")

    args = parser.parse_args()

    # 生成申报材料
    log("📝 生成课题申报材料...")
    material = generate_apply_material(args)

    if not material:
        log("❌ 生成申报材料失败")
        sys.exit(1)

    # 导出申报材料
    log("💾 导出申报材料...")
    output_path = export_material(material, args.output_format, args.output_file)

    log("✅ 课题申报材料生成完成！")
    log(f"📁 输出文件：{output_path}")

    sys.exit(0)


if __name__ == "__main__":
    main()
