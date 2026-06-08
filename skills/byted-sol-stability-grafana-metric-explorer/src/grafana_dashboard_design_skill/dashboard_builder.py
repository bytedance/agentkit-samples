# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List, Tuple

from .models import DashboardIA, GrafanaDashboardDoc, GrafanaPanelDTO, PanelSpec


LAYER_ORDER = ["api", "gateway", "conversation", "queue", "agent", "llm", "cron"]


def _slug(text: str) -> str:
    result = []
    for ch in text.strip().lower():
        result.append(ch if ch.isalnum() else "-")
    slug = "".join(result)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "dashboard"


def _zone_prefix(zone_type: str) -> str:
    if zone_type == "health":
        return "[HEALTH]"
    if zone_type == "diagnostic":
        return "[DIAGNOSTIC]"
    return "[EVENT]"


def _threshold_steps(spec: PanelSpec) -> List[Dict[str, float | str | None]]:
    steps: List[Dict[str, float | str | None]] = [{"color": "green", "value": None}]
    for rule in spec.thresholds:
        steps.append({"color": rule.color, "value": rule.value})
    return steps


def _panel_size(spec: PanelSpec) -> Tuple[int, int]:
    if spec.chart_type == "stat":
        return 4, 5
    if spec.chart_type == "table":
        return 8, 6
    if spec.chart_type == "state-timeline":
        return 12, 6
    return 12, 6


def _layout_overview_row1(section_panels: List[PanelSpec], y_start: int) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    by_id = {panel.panel_id: panel for panel in section_panels}

    stat_ids = [
        "overview-kpi-availability",
        "overview-kpi-slo-attainment",
        "overview-kpi-error-budget",
        "overview-kpi-active-alerts",
    ]
    x = 0
    for panel_id in stat_ids:
        panel = by_id.get(panel_id)
        if panel is None:
            continue
        positions[panel.panel_id] = {"x": x, "y": y_start, "w": 4, "h": 5}
        x += 4

    oncall = by_id.get("overview-kpi-oncall-topn")
    if oncall is not None:
        positions[oncall.panel_id] = {"x": 16, "y": y_start, "w": 8, "h": 5}

    return positions, y_start + 6


def _layout_overview_row2(section_panels: List[PanelSpec], y_start: int) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    by_id = {panel.panel_id: panel for panel in section_panels}

    scorecards = by_id.get("overview-sli-scorecards")
    trend = by_id.get("overview-sli-trend")
    topn_ids = [
        "overview-topn-impact-tenant",
        "overview-topn-impact-model",
        "overview-topn-impact-channel",
        "overview-topn-impact-agent",
    ]

    if scorecards is not None:
        positions[scorecards.panel_id] = {"x": 0, "y": y_start, "w": 6, "h": 12}
    if trend is not None:
        positions[trend.panel_id] = {"x": 6, "y": y_start, "w": 10, "h": 12}

    topn_y = y_start
    for topn_id in topn_ids:
        panel = by_id.get(topn_id)
        if panel is None:
            continue
        positions[panel.panel_id] = {"x": 16, "y": topn_y, "w": 8, "h": 3}
        topn_y += 3

    return positions, y_start + 13


def _layout_overview_row3(section_panels: List[PanelSpec], y_start: int) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    by_id = {panel.panel_id: panel for panel in section_panels}

    panel_ids = [
        "overview-events-alert-stream",
        "overview-events-reliability",
        "overview-events-change",
    ]
    x = 0
    for panel_id in panel_ids:
        panel = by_id.get(panel_id)
        if panel is None:
            continue
        positions[panel.panel_id] = {"x": x, "y": y_start, "w": 8, "h": 7}
        x += 8

    return positions, y_start + 8


def _layer_from_panel_id(panel_id: str) -> str:
    if not panel_id.startswith("service-layers-"):
        return ""
    parts = panel_id.split("-")
    if len(parts) < 4:
        return ""
    return parts[2]


def _layout_service_layers_health(
    section_panels: List[PanelSpec],
    y_start: int,
) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    grouped: Dict[str, Dict[str, PanelSpec]] = {key: {} for key in LAYER_ORDER}

    for panel in section_panels:
        layer = _layer_from_panel_id(panel.panel_id)
        if layer in grouped:
            if panel.panel_id.endswith("-scorecards"):
                grouped[layer]["scorecards"] = panel
            elif panel.panel_id.endswith("-availability"):
                grouped[layer]["availability"] = panel

    y = y_start
    for layer in LAYER_ORDER:
        scorecards = grouped[layer].get("scorecards")
        availability = grouped[layer].get("availability")
        if scorecards is not None:
            positions[scorecards.panel_id] = {"x": 0, "y": y, "w": 6, "h": 5}
        if availability is not None:
            positions[availability.panel_id] = {"x": 6, "y": y, "w": 18, "h": 5}
        y += 6

    return positions, y


def _layout_service_layers_diagnostic(
    section_panels: List[PanelSpec],
    y_start: int,
) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    ordered_panels: List[PanelSpec] = []
    grouped: Dict[str, PanelSpec] = {}

    for panel in section_panels:
        layer = _layer_from_panel_id(panel.panel_id)
        if layer in LAYER_ORDER and panel.panel_id.endswith("-latency"):
            grouped[layer] = panel

    for layer in LAYER_ORDER:
        panel = grouped.get(layer)
        if panel is not None:
            ordered_panels.append(panel)

    x = 0
    y = y_start
    row_height = 0
    for panel in ordered_panels:
        width = 6
        height = 5
        if x + width > 24:
            x = 0
            y += row_height + 1
            row_height = 0

        positions[panel.panel_id] = {"x": x, "y": y, "w": width, "h": height}
        x += width
        row_height = max(row_height, height)

    if ordered_panels:
        y += row_height

    return positions, y


def _layout_two_panel_page(
    page_panels: List[PanelSpec],
    y_start: int,
    first_panel_id: str,
    second_panel_id: str,
) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    by_id = {panel.panel_id: panel for panel in page_panels}

    first = by_id.get(first_panel_id)
    second = by_id.get(second_panel_id)

    if first is not None:
        positions[first.panel_id] = {"x": 0, "y": y_start, "w": 12, "h": 6}
    if second is not None:
        positions[second.panel_id] = {"x": 12, "y": y_start, "w": 12, "h": 6}

    return positions, y_start + 7


def _layout_change_rollout_page(
    page_panels: List[PanelSpec],
    y_start: int,
) -> Tuple[Dict[str, Dict[str, int]], int]:
    positions: Dict[str, Dict[str, int]] = {}
    by_id = {panel.panel_id: panel for panel in page_panels}

    panel_ids = [
        "change-rollout-health",
        "change-rollout-events",
        "change-rollout-capacity-diagnostic",
    ]

    x = 0
    for panel_id in panel_ids:
        panel = by_id.get(panel_id)
        if panel is None:
            continue
        positions[panel.panel_id] = {"x": x, "y": y_start, "w": 8, "h": 6}
        x += 8

    return positions, y_start + 7


def _build_grid_positions(panel_specs: List[PanelSpec]) -> Dict[str, Dict[str, int]]:
    positions: Dict[str, Dict[str, int]] = {}
    y = 0

    page_order: List[str] = []
    for panel in panel_specs:
        if panel.page_id not in page_order:
            page_order.append(panel.page_id)

    for page_id in page_order:
        page_panels = [panel for panel in panel_specs if panel.page_id == page_id]

        if page_id == "core-links":
            custom_positions, y = _layout_two_panel_page(
                page_panels,
                y,
                "core-links-health-request-success",
                "core-links-diagnostic-latency",
            )
            positions.update(custom_positions)
            y += 2
            continue

        if page_id == "dependencies":
            custom_positions, y = _layout_two_panel_page(
                page_panels,
                y,
                "dependencies-health",
                "dependencies-diagnostic-latency",
            )
            positions.update(custom_positions)
            y += 2
            continue

        if page_id == "error-analysis":
            custom_positions, y = _layout_two_panel_page(
                page_panels,
                y,
                "error-analysis-rate-volume",
                "error-analysis-diagnostic-topn",
            )
            positions.update(custom_positions)
            y += 2
            continue

        if page_id == "change-rollout-capacity":
            custom_positions, y = _layout_change_rollout_page(page_panels, y)
            positions.update(custom_positions)
            y += 2
            continue

        section_order: List[str] = []
        for panel in page_panels:
            if panel.section_id not in section_order:
                section_order.append(panel.section_id)

        for section_id in section_order:
            section_panels = [panel for panel in page_panels if panel.section_id == section_id]

            if section_id == "overview-row1-health-summary":
                custom_positions, y = _layout_overview_row1(section_panels, y)
                positions.update(custom_positions)
                continue

            if section_id == "overview-row2-health-sli-detail":
                custom_positions, y = _layout_overview_row2(section_panels, y)
                positions.update(custom_positions)
                continue

            if section_id == "overview-row3-event-overlay":
                custom_positions, y = _layout_overview_row3(section_panels, y)
                positions.update(custom_positions)
                continue

            if section_id == "service-layers-health":
                custom_positions, y = _layout_service_layers_health(section_panels, y)
                positions.update(custom_positions)
                continue

            if section_id == "service-layers-diagnostic":
                custom_positions, y = _layout_service_layers_diagnostic(section_panels, y)
                positions.update(custom_positions)
                continue

            x = 0
            row_height = 0
            for panel in section_panels:
                width, height = _panel_size(panel)
                if x + width > 24:
                    x = 0
                    y += row_height + 1
                    row_height = 0
                positions[panel.panel_id] = {"x": x, "y": y, "w": width, "h": height}
                x += width
                row_height = max(row_height, height)

            y += row_height + 1

        y += 2

    return positions


def build_grafana_dashboard(ia: DashboardIA, panel_specs: List[PanelSpec]) -> GrafanaDashboardDoc:
    positions = _build_grid_positions(panel_specs)
    panels: List[GrafanaPanelDTO] = []
    for spec in panel_specs:
        prefix = _zone_prefix(spec.zone_type)
        panels.append(
            GrafanaPanelDTO(
                panel_id=spec.panel_id,
                title=f"{prefix} {spec.title}",
                panel_type=spec.chart_type,
                expr=spec.metric_formula,
                grid_pos=positions[spec.panel_id],
                description=(
                    f"sli={spec.sli_link} path={spec.path_link} confidence={spec.confidence}"
                ),
                links=[{"title": spec.drilldown.title, "url": spec.drilldown.target}],
                threshold_steps=_threshold_steps(spec),
            )
        )

    tags = ["dashboard-design", "health", "diagnostic", "sli", "arkclaw-layout"]
    annotations = [
        {
            "name": "Alert Events",
            "datasource": {"type": "grafana", "uid": "-- Grafana --"},
            "enable": True,
            "iconColor": "red",
            "type": "dashboard",
        },
        {
            "name": "Change Events",
            "datasource": {"type": "grafana", "uid": "-- Grafana --"},
            "enable": True,
            "iconColor": "blue",
            "type": "dashboard",
        },
    ]

    return GrafanaDashboardDoc(
        title=ia.title,
        uid=_slug(ia.title)[:40],
        tags=tags,
        refresh="30s",
        time_from="now-6h",
        panels=panels,
        templating_variables=ia.global_variables,
        annotations=annotations,
    )
