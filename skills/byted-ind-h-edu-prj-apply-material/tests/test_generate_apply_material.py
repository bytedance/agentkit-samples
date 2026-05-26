#!/usr/bin/env python3

import os
import sys
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.generate_apply_material import (
    load_project_templates,
    generate_basic_info,
    generate_abstract,
    generate_research_background,
    generate_research_status,
    generate_research_goals,
    generate_research_content,
    generate_research_methods,
    generate_innovations,
    generate_expected_results,
    generate_research_basis,
    generate_feasibility,
    generate_budget,
    generate_research_plan,
    generate_apply_material,
)


def test_load_project_templates():
    """测试加载课题模板"""
    templates = load_project_templates()
    assert isinstance(templates, dict)
    assert "national" in templates
    assert "provincial" in templates
    assert "school" in templates
    assert "horizontal" in templates
    assert "key" in templates["national"]
    assert "general" in templates["national"]
    assert "young" in templates["national"]


def test_generate_basic_info():
    """测试生成基本信息"""

    class Args:
        topic = "测试主题"
        project_type = "national"
        project_level = "general"
        applicant = "测试申请人"
        organization = "测试单位"
        duration = 24
        budget = 20

    args = Args()
    basic_info = generate_basic_info(args)
    assert "基本信息" in basic_info
    assert "测试主题" in basic_info
    assert "测试申请人" in basic_info
    assert "测试单位" in basic_info
    assert "24" in basic_info
    assert "20" in basic_info


def test_generate_abstract():
    """测试生成摘要"""
    topic = "测试主题"
    abstract = generate_abstract(topic)
    assert "摘要" in abstract
    assert topic in abstract
    assert "研究背景与意义" in abstract
    assert "国内外研究现状" in abstract


def test_generate_research_background():
    """测试生成研究背景与意义"""
    topic = "测试主题"
    background = generate_research_background(topic)
    assert "研究背景与意义" in background
    assert topic in background
    assert "研究背景" in background
    assert "研究意义" in background


def test_generate_research_status():
    """测试生成国内外研究现状"""
    status = generate_research_status()
    assert "国内外研究现状" in status
    assert "国外研究现状" in status
    assert "国内研究现状" in status
    assert "研究不足" in status
    assert "研究趋势" in status


def test_generate_research_goals():
    """测试生成研究目标"""
    goals = generate_research_goals()
    assert "研究目标" in goals
    assert "总体目标" in goals
    assert "具体目标" in goals


def test_generate_research_content():
    """测试生成研究内容"""
    topic = "测试主题"
    content = generate_research_content(topic)
    assert "研究内容" in content
    assert "主要研究内容" in content
    assert "关键科学问题" in content
    assert topic in content


def test_generate_research_methods():
    """测试生成研究方法"""
    methods = generate_research_methods()
    assert "研究方法与技术路线" in methods
    assert "研究方法" in methods
    assert "技术路线" in methods
    assert "关键技术" in methods


def test_generate_innovations():
    """测试生成创新点"""
    innovations = generate_innovations()
    assert "创新点与特色" in innovations
    assert "创新点" in innovations
    assert "特色" in innovations


def test_generate_expected_results():
    """测试生成预期成果"""
    results = generate_expected_results()
    assert "预期成果与效益" in results
    assert "预期成果" in results
    assert "预期效益" in results


def test_generate_research_basis():
    """测试生成研究基础"""
    basis = generate_research_basis()
    assert "研究基础与条件" in basis
    assert "研究基础" in basis
    assert "研究条件" in basis


def test_generate_feasibility():
    """测试生成可行性分析"""
    feasibility = generate_feasibility()
    assert "可行性分析" in feasibility
    assert "技术可行性" in feasibility
    assert "经济可行性" in feasibility
    assert "组织可行性" in feasibility
    assert "风险分析与应对措施" in feasibility


def test_generate_budget():
    """测试生成经费预算"""
    budget = 20
    budget_content = generate_budget(budget)
    assert "经费预算" in budget_content
    assert "预算编制原则" in budget_content
    assert "预算明细" in budget_content
    assert "20" in budget_content


def test_generate_research_plan():
    """测试生成研究计划"""
    duration = 24
    plan = generate_research_plan(duration)
    assert "研究计划与进度安排" in plan
    assert "总体研究计划" in plan
    assert "具体进度安排" in plan
    assert str(duration) in plan


def test_generate_apply_material():
    """测试生成申报材料"""

    class Args:
        project_type = "national"
        project_level = "general"
        topic = "测试主题"
        applicant = "测试申请人"
        organization = "测试单位"
        duration = 24
        budget = 20

    args = Args()
    material = generate_apply_material(args)
    assert "测试主题 课题申报书" in material
    assert "基本信息" in material
    assert "摘要" in material
    assert "研究背景与意义" in material
    assert "国内外研究现状" in material
    assert "研究目标" in material
    assert "研究内容" in material
    assert "研究方法与技术路线" in material
    assert "创新点与特色" in material
    assert "预期成果与效益" in material
    assert "研究基础与条件" in material
    assert "可行性分析" in material
    assert "经费预算" in material
    assert "研究计划与进度安排" in material


if __name__ == "__main__":
    pytest.main([__file__])
