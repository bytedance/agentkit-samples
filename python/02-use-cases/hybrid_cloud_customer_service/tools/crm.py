"""Synthetic CRM and idempotent work-order tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkOrder:
    order_id: str
    user_id: str
    channel: str
    status: str = "submitted"


class CRMTool:
    def __init__(self) -> None:
        self._orders: dict[str, WorkOrder] = {}

    def create_work_order(self, *, user_id: str, channel: str, idempotency_key: str) -> WorkOrder:
        if channel not in {"bank_account", "alipay", "wechat"}:
            raise ValueError("unsupported refund channel")
        if idempotency_key not in self._orders:
            order_id = f"WO-{len(self._orders) + 1:04d}"
            self._orders[idempotency_key] = WorkOrder(order_id, user_id, channel)
        return self._orders[idempotency_key]
