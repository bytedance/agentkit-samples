# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Iterable, List, Tuple

from .models import (
    DashboardIA,
    DrillDownLink,
    NormalizedInputs,
    PanelSpec,
    ThresholdRule,
)


def _select_metric_formula(
    keyword: str,
    code_metric_hints: List[str],
    fallback: str,
) -> Tuple[str, str]:
    for name in code_metric_hints:
        if keyword in name.lower():
            return f"sum(rate({name}[5m]))", "high"
    return fallback, "placeholder"


def _default_thresholds(zone_type: str) -> List[ThresholdRule]:
    if zone_type == "health":
        return [
            ThresholdRule(color="green", operator=">=", value=99),
            ThresholdRule(color="yellow", operator="<", value=99),
            ThresholdRule(color="red", operator="<", value=95),
        ]
    if zone_type == "event_overlay":
        return [
            ThresholdRule(color="green", operator="<=", value=5),
            ThresholdRule(color="yellow", operator=">", value=5),
            ThresholdRule(color="red", operator=">", value=20),
        ]
    return [
        ThresholdRule(color="green", operator="<=", value=1),
        ThresholdRule(color="yellow", operator=">", value=1),
        ThresholdRule(color="red", operator=">", value=5),
    ]


def _panel(
    panel_id: str,
    page_id: str,
    section_id: str,
    zone_type: str,
    title: str,
    chart_type: str,
    metric_formula: str,
    confidence: str,
    sli_link: str,
    path_link: str,
    evidence_refs: Iterable[str],
    refresh_interval: str = "30s",
    dimensions: List[str] | None = None,
) -> PanelSpec:
    return PanelSpec(
        panel_id=panel_id,
        page_id=page_id,
        section_id=section_id,
        title=title,
        chart_type=chart_type,
        metric_formula=metric_formula,
        dimensions=dimensions or ["service", "region", "tenant"],
        refresh_interval=refresh_interval,
        thresholds=_default_thresholds(zone_type),
        drilldown=DrillDownLink(title="View details", target=f"page:{page_id}"),
        sli_link=sli_link,
        path_link=path_link,
        zone_type=zone_type,
        confidence=confidence,
        evidence_refs=list(evidence_refs),
    )


def compile_panel_specs(inputs: NormalizedInputs, ia: DashboardIA) -> List[PanelSpec]:
    panels: List[PanelSpec] = []

    evidence_ids = [item.evidence_id for item in inputs.evidence_items[:8]]
    main_path = inputs.request_paths[0].path_id if inputs.request_paths else "request-main"
    main_sli = inputs.sli_indicators[0].indicator_id if inputs.sli_indicators else "sli-availability"

    availability_formula, availability_conf = _select_metric_formula(
        "success_rate",
        inputs.code_metric_hints,
        fallback="(sum(rate(service_success_total[5m])) / sum(rate(service_requests_total[5m]))) * 100",
    )
    slo_formula, slo_conf = _select_metric_formula(
        "slo",
        inputs.code_metric_hints,
        fallback="(sum(rate(slo_good_total[5m])) / sum(rate(slo_total[5m]))) * 100",
    )
    error_budget_formula, error_budget_conf = _select_metric_formula(
        "error",
        inputs.code_metric_hints,
        fallback="(sum(rate(service_error_total[5m])) / sum(rate(service_requests_total[5m]))) * 100",
    )

    panels.extend(
        [
            _panel(
                panel_id="overview-kpi-availability",
                page_id="overview",
                section_id="overview-row1-health-summary",
                zone_type="health",
                title="整体可用率",
                chart_type="stat",
                metric_formula=availability_formula,
                confidence=availability_conf,
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service"],
            ),
            _panel(
                panel_id="overview-kpi-slo-attainment",
                page_id="overview",
                section_id="overview-row1-health-summary",
                zone_type="health",
                title="SLO 达标率",
                chart_type="stat",
                metric_formula=slo_formula,
                confidence=slo_conf,
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service"],
            ),
            _panel(
                panel_id="overview-kpi-error-budget",
                page_id="overview",
                section_id="overview-row1-health-summary",
                zone_type="health",
                title="错误预算消耗",
                chart_type="stat",
                metric_formula=error_budget_formula,
                confidence=error_budget_conf,
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service"],
            ),
            _panel(
                panel_id="overview-kpi-active-alerts",
                page_id="overview",
                section_id="overview-row1-health-summary",
                zone_type="health",
                title="今日告警数",
                chart_type="stat",
                metric_formula="sum(increase(alert_events_total[1d]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["severity"],
            ),
            _panel(
                panel_id="overview-kpi-oncall-topn",
                page_id="overview",
                section_id="overview-row1-health-summary",
                zone_type="diagnostic",
                title="TOPN Oncall / 工单收敛率",
                chart_type="table",
                metric_formula="topk(10, sum by(oncall)(increase(oncall_closed_incidents_total[1d])))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["oncall"],
            ),
        ]
    )

    panels.extend(
        [
            _panel(
                panel_id="overview-sli-scorecards",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="health",
                title="控制面/数据面 SLI 评分卡",
                chart_type="table",
                metric_formula="sum by(sli)(rate(sli_good_total[5m])) / sum by(sli)(rate(sli_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["sli", "plane"],
            ),
            _panel(
                panel_id="overview-sli-trend",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="health",
                title="可用率趋势图",
                chart_type="timeseries",
                metric_formula="sum(rate(control_plane_requests_total[5m])) / sum(rate(control_plane_requests_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service", "plane"],
            ),
            _panel(
                panel_id="overview-topn-impact-tenant",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="diagnostic",
                title="TOPN 受损租户（成功率下降）",
                chart_type="table",
                metric_formula="topk(10, (1 - (sum by(tenant)(rate(request_success_total[5m])) / sum by(tenant)(rate(request_total[5m])))) * 100)",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["tenant"],
            ),
            _panel(
                panel_id="overview-topn-impact-model",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="diagnostic",
                title="TOPN 受损模型（成功率下降）",
                chart_type="table",
                metric_formula="topk(10, (1 - (sum by(model)(rate(request_success_total[5m])) / sum by(model)(rate(request_total[5m])))) * 100)",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["model"],
            ),
            _panel(
                panel_id="overview-topn-impact-channel",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="diagnostic",
                title="TOPN 受损渠道（成功率下降）",
                chart_type="table",
                metric_formula="topk(10, (1 - (sum by(channel)(rate(request_success_total[5m])) / sum by(channel)(rate(request_total[5m])))) * 100)",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["channel"],
            ),
            _panel(
                panel_id="overview-topn-impact-agent",
                page_id="overview",
                section_id="overview-row2-health-sli-detail",
                zone_type="diagnostic",
                title="TOPN 受损 Agent（成功率下降）",
                chart_type="table",
                metric_formula="topk(10, (1 - (sum by(agent)(rate(request_success_total[5m])) / sum by(agent)(rate(request_total[5m])))) * 100)",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["agent"],
            ),
        ]
    )

    panels.extend(
        [
            _panel(
                panel_id="overview-events-alert-stream",
                page_id="overview",
                section_id="overview-row3-event-overlay",
                zone_type="event_overlay",
                title="告警事件流",
                chart_type="table",
                metric_formula="topk(50, increase(alert_events_total[1h]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["severity", "service"],
            ),
            _panel(
                panel_id="overview-events-reliability",
                page_id="overview",
                section_id="overview-row3-event-overlay",
                zone_type="event_overlay",
                title="稳定性事件（故障/恢复）",
                chart_type="table",
                metric_formula="topk(50, increase(reliability_events_total[1h]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["event_type", "service"],
            ),
            _panel(
                panel_id="overview-events-change",
                page_id="overview",
                section_id="overview-row3-event-overlay",
                zone_type="event_overlay",
                title="变更事件",
                chart_type="table",
                metric_formula="topk(50, increase(change_events_total[1h]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["change_type", "service"],
            ),
        ]
    )

    layer_panels = [
        ("api", "API（网络层）", "api_success_total", "api_latency_ms"),
        ("gateway", "Channel / Gateway", "gateway_success_total", "gateway_latency_ms"),
        ("conversation", "Conversation / Message", "conversation_success_total", "conversation_latency_ms"),
        ("queue", "Message / Queue", "queue_success_total", "queue_latency_ms"),
        ("agent", "Agent", "agent_success_total", "agent_latency_ms"),
        ("llm", "LLM / Tool / Context", "llm_success_total", "llm_latency_ms"),
        ("cron", "CronJob / Skills", "cron_success_total", "cron_latency_ms"),
    ]

    for layer_id, layer_name, success_metric, latency_metric in layer_panels:
        panels.append(
            _panel(
                panel_id=f"service-layers-{layer_id}-scorecards",
                page_id="service-layers",
                section_id="service-layers-health",
                zone_type="health",
                title=f"{layer_name} 指标卡",
                chart_type="table",
                metric_formula=f"sum by(metric)(rate({success_metric}[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["metric", "region"],
            )
        )
        panels.append(
            _panel(
                panel_id=f"service-layers-{layer_id}-availability",
                page_id="service-layers",
                section_id="service-layers-health",
                zone_type="health",
                title=f"{layer_name} 可用率趋势",
                chart_type="timeseries",
                metric_formula=f"sum(rate({success_metric}[5m])) / sum(rate({success_metric.replace('_success_total', '_requests_total')}[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service", "region"],
            )
        )
        panels.append(
            _panel(
                panel_id=f"service-layers-{layer_id}-latency",
                page_id="service-layers",
                section_id="service-layers-diagnostic",
                zone_type="diagnostic",
                title=f"{layer_name} 延迟 P95/P99",
                chart_type="timeseries",
                metric_formula=f"histogram_quantile(0.95, sum(rate({latency_metric}_bucket[5m])) by (le, service))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["service", "region"],
            )
        )

    panels.extend(
        [
            _panel(
                panel_id="core-links-health-request-success",
                page_id="core-links",
                section_id="core-links-health",
                zone_type="health",
                title="核心链路成功率",
                chart_type="timeseries",
                metric_formula="sum(rate(request_success_total[5m])) / sum(rate(request_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["path", "service"],
            ),
            _panel(
                panel_id="core-links-diagnostic-latency",
                page_id="core-links",
                section_id="core-links-diagnostic",
                zone_type="diagnostic",
                title="链路分段时延 P99",
                chart_type="timeseries",
                metric_formula="histogram_quantile(0.99, sum(rate(request_duration_ms_bucket[5m])) by (le, hop))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["hop"],
            ),
            _panel(
                panel_id="dependencies-health",
                page_id="dependencies",
                section_id="dependencies-health",
                zone_type="health",
                title="强依赖可用率",
                chart_type="table",
                metric_formula="sum by(dependency)(rate(dependency_success_total[5m])) / sum by(dependency)(rate(dependency_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["dependency"],
            ),
            _panel(
                panel_id="dependencies-diagnostic-latency",
                page_id="dependencies",
                section_id="dependencies-diagnostic",
                zone_type="diagnostic",
                title="依赖延迟与容量热点",
                chart_type="timeseries",
                metric_formula="topk(10, histogram_quantile(0.99, sum(rate(dependency_duration_ms_bucket[5m])) by (le, dependency)))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["dependency"],
            ),
            _panel(
                panel_id="error-analysis-rate-volume",
                page_id="error-analysis",
                section_id="error-analysis-health",
                zone_type="health",
                title="错误率与错误量",
                chart_type="timeseries",
                metric_formula="sum(rate(error_total[5m])) / sum(rate(request_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
            ),
            _panel(
                panel_id="error-analysis-diagnostic-topn",
                page_id="error-analysis",
                section_id="error-analysis-diagnostic",
                zone_type="diagnostic",
                title="错误归因 TopN",
                chart_type="table",
                metric_formula="topk(20, sum by(error_code, component)(increase(error_total[1h])))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["error_code", "component"],
            ),
            _panel(
                panel_id="change-rollout-health",
                page_id="change-rollout-capacity",
                section_id="change-rollout-health",
                zone_type="health",
                title="灰度窗口稳定性",
                chart_type="timeseries",
                metric_formula="sum(rate(canary_success_total[5m])) / sum(rate(canary_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
            ),
            _panel(
                panel_id="change-rollout-events",
                page_id="change-rollout-capacity",
                section_id="change-rollout-events",
                zone_type="event_overlay",
                title="变更/告警事件叠加",
                chart_type="state-timeline",
                metric_formula="sum(rate(alert_events_total[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["event_type", "source"],
            ),
            _panel(
                panel_id="change-rollout-capacity-diagnostic",
                page_id="change-rollout-capacity",
                section_id="change-rollout-diagnostic",
                zone_type="diagnostic",
                title="容量与饱和度诊断",
                chart_type="timeseries",
                metric_formula="sum(rate(queue_backlog_count[5m]))",
                confidence="placeholder",
                sli_link=main_sli,
                path_link=main_path,
                evidence_refs=evidence_ids,
                dimensions=["resource", "cluster"],
            ),
        ]
    )

    by_page = {page.page_id: page for page in ia.pages}
    valid_panels = [panel for panel in panels if panel.page_id in by_page]

    for panel in valid_panels:
        if panel.sli_link == "sli-availability" and inputs.sli_indicators:
            panel.sli_link = inputs.sli_indicators[0].indicator_id
        if panel.path_link == "request-main" and inputs.request_paths:
            panel.path_link = inputs.request_paths[0].path_id

    return valid_panels
