# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import List

from .models import DashboardIA, IAPage, IASection, NormalizedInputs


def _overview_sections() -> List[IASection]:
    return [
        IASection(
            section_id="overview-row1-health-summary",
            name="宏观稳定性与处置效率",
            zone_type="health",
            purpose="展示整体可用率、SLO 达标率、错误预算与告警收敛效率",
        ),
        IASection(
            section_id="overview-row2-health-sli-detail",
            name="SLI/SLO 明细与趋势",
            zone_type="health",
            purpose="展示控制面与数据面 SLI 指标趋势和受损 TopN 维度",
        ),
        IASection(
            section_id="overview-row3-event-overlay",
            name="告警与变更事件",
            zone_type="event_overlay",
            purpose="展示告警、值班处置、可靠性事件与变更事件清单",
        ),
        IASection(
            section_id="overview-row4-diagnostic-component-health",
            name="核心组件诊断",
            zone_type="diagnostic",
            purpose="展示 API、模型、队列、Agent 等组件的诊断信号",
        ),
    ]


def _core_links_sections() -> List[IASection]:
    return [
        IASection(
            section_id="core-links-health",
            name="核心链路健康",
            zone_type="health",
            purpose="展示核心请求链路成功率与流量规模",
        ),
        IASection(
            section_id="core-links-diagnostic",
            name="链路诊断",
            zone_type="diagnostic",
            purpose="展示链路分段时延与错误热点",
        ),
    ]


def _service_layers_sections() -> List[IASection]:
    return [
        IASection(
            section_id="service-layers-health",
            name="分层健康总览",
            zone_type="health",
            purpose="按 Channel/Gateway、Session/Message、Queue、Agent、LLM、CronJob 分层观察稳定性",
        ),
        IASection(
            section_id="service-layers-diagnostic",
            name="分层诊断",
            zone_type="diagnostic",
            purpose="按层观察时延、错误和饱和度变化",
        ),
    ]


def _dependencies_sections() -> List[IASection]:
    return [
        IASection(
            section_id="dependencies-health",
            name="依赖健康",
            zone_type="health",
            purpose="展示强依赖可用率与依赖稳定性风险",
        ),
        IASection(
            section_id="dependencies-diagnostic",
            name="依赖诊断",
            zone_type="diagnostic",
            purpose="展示依赖调用时延、错误和资源容量瓶颈",
        ),
    ]


def _error_analysis_sections() -> List[IASection]:
    return [
        IASection(
            section_id="error-analysis-health",
            name="错误健康信号",
            zone_type="health",
            purpose="展示错误率、错误量与错误预算消耗",
        ),
        IASection(
            section_id="error-analysis-diagnostic",
            name="错误归因诊断",
            zone_type="diagnostic",
            purpose="按错误码、组件、租户、模型、渠道分解受损范围",
        ),
    ]


def _change_rollout_capacity_sections() -> List[IASection]:
    return [
        IASection(
            section_id="change-rollout-health",
            name="变更与灰度健康",
            zone_type="health",
            purpose="展示灰度窗口稳定性与回滚风险",
        ),
        IASection(
            section_id="change-rollout-events",
            name="告警/变更事件叠加",
            zone_type="event_overlay",
            purpose="在健康指标上叠加关键告警和变更事件",
        ),
        IASection(
            section_id="change-rollout-diagnostic",
            name="容量与资源诊断",
            zone_type="diagnostic",
            purpose="展示 CPU、内存、队列、连接池饱和度与值班收敛",
        ),
    ]


def build_dashboard_ia(inputs: NormalizedInputs, dashboard_title: str | None = None) -> DashboardIA:
    title = dashboard_title or f"{inputs.repo_slug} Dashboard Design"
    pages = [
        IAPage(
            page_id="overview",
            page_type="overview",
            name="总览页",
            purpose="展示服务整体稳定性水平、问题处置效率和质量",
            sections=_overview_sections(),
        ),
        IAPage(
            page_id="core-links",
            page_type="core_links",
            name="核心链路页",
            purpose="展示核心用户链路、控制面链路与数据面链路",
            sections=_core_links_sections(),
        ),
        IAPage(
            page_id="service-layers",
            page_type="service_layers",
            name="服务分层页",
            purpose="按服务层次进行健康和诊断分析",
            sections=_service_layers_sections(),
        ),
        IAPage(
            page_id="dependencies",
            page_type="dependencies",
            name="依赖资源页",
            purpose="展示依赖服务、数据库、缓存、队列等资源健康",
            sections=_dependencies_sections(),
        ),
        IAPage(
            page_id="error-analysis",
            page_type="error_analysis",
            name="错误分析页",
            purpose="定位错误来源与受损范围",
            sections=_error_analysis_sections(),
        ),
        IAPage(
            page_id="change-rollout-capacity",
            page_type="change_rollout_capacity",
            name="变更 / 灰度 / 容量页",
            purpose="关联变更、灰度、容量与告警事件",
            sections=_change_rollout_capacity_sections(),
        ),
    ]

    variables = ["service", "region", "claw", "tenant", "agent", "model", "channel", "cluster"]
    if inputs.focus_service:
        variables.append("focus_service")

    return DashboardIA(title=title, pages=pages, global_variables=variables)
