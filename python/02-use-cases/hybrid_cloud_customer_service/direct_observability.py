"""OpenTelemetry metrics and logs for a directly-run Docker container.

AgentKit Runtime normally supplies an observability injection layer. A plain
``docker run`` deployment does not have that layer, so this module configures
the metrics and logs pipelines that VeADK's tracer setup does not own.

Connection details come from standard OpenTelemetry environment variables.
Values are never logged, and credential-bearing endpoints are never derived
from another signal URL.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from opentelemetry import metrics as metrics_api
from opentelemetry.metrics._internal import _ProxyMeterProvider
from opentelemetry.sdk import metrics as metrics_sdk
from opentelemetry.sdk._logs import LoggingHandler, LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from veadk.tracing.telemetry import portal_metrics

logger = logging.getLogger(__name__)

_SUPPORTED_PROTOCOLS = {"grpc", "http/protobuf"}
_DEFAULT_METRIC_EXPORT_INTERVAL_MS = 60_000
_DIRECT_LOG_HANDLER_MARKER = "_agentkit_direct_otel_handler"


def _parse_key_value_list(value: str) -> dict[str, str]:
    """Parse OTEL's comma-separated, percent-encoded key/value syntax."""
    parsed: dict[str, str] = {}
    for item in value.split(","):
        key, separator, item_value = item.partition("=")
        if separator and key.strip():
            parsed[unquote(key.strip())] = unquote(item_value.strip())
    return parsed


def direct_resource_attributes(default_service_name: str) -> dict[str, str]:
    """Build the resource shared by traces, metrics, and logs."""
    attributes = _parse_key_value_list(os.getenv("OTEL_RESOURCE_ATTRIBUTES", ""))
    attributes["service.name"] = os.getenv("OTEL_SERVICE_NAME", default_service_name)
    return attributes


def _signal_headers(signal: str) -> dict[str, str]:
    value = os.getenv(f"OTEL_EXPORTER_OTLP_{signal}_HEADERS")
    if value is None:
        value = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    return _parse_key_value_list(value)


def _signal_protocol(signal: str) -> str:
    return (
        os.getenv(
            f"OTEL_EXPORTER_OTLP_{signal}_PROTOCOL",
            os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
        )
        .strip()
        .lower()
    )


def _signal_exporter_enabled(signal: str) -> bool:
    value = os.getenv(f"OTEL_{signal}_EXPORTER", "").strip().lower()
    if not value:
        # An explicit endpoint is enough to enable a direct-container signal.
        return True
    exporters = {item.strip() for item in value.split(",") if item.strip()}
    if "none" in exporters:
        return False
    if "otlp" not in exporters:
        logger.warning("Direct-container OTLP %s disabled: exporter is not otlp.", signal.lower())
        return False
    return True


def _signal_timeout(signal: str) -> float | None:
    value = os.getenv(
        f"OTEL_EXPORTER_OTLP_{signal}_TIMEOUT",
        os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", ""),
    ).strip()
    if not value:
        return None
    try:
        timeout = float(value)
    except ValueError:
        logger.warning("Ignoring invalid OTEL %s timeout.", signal.lower())
        return None
    return timeout if timeout > 0 else None


def _metric_exporter(endpoint: str, protocol: str):
    kwargs: dict[str, Any] = {
        "endpoint": endpoint,
        "headers": _signal_headers("METRICS"),
    }
    timeout = _signal_timeout("METRICS")
    if timeout is not None:
        kwargs["timeout"] = timeout
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
    return OTLPMetricExporter(**kwargs)


def _log_exporter(endpoint: str, protocol: str):
    kwargs: dict[str, Any] = {
        "endpoint": endpoint,
        "headers": _signal_headers("LOGS"),
    }
    timeout = _signal_timeout("LOGS")
    if timeout is not None:
        kwargs["timeout"] = timeout
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    else:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    return OTLPLogExporter(**kwargs)


class DirectOTLPMeterPipeline:
    """Export VeADK 1.x Portal metrics through a direct OTLP endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        protocol: str,
        resource_attributes: dict[str, str],
    ) -> None:
        exporter = _metric_exporter(endpoint, protocol)
        try:
            interval = float(
                os.getenv(
                    "OTEL_METRIC_EXPORT_INTERVAL",
                    str(_DEFAULT_METRIC_EXPORT_INTERVAL_MS),
                )
            )
        except ValueError:
            interval = _DEFAULT_METRIC_EXPORT_INTERVAL_MS
            logger.warning("Ignoring invalid OTEL metric export interval.")

        self.reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=max(interval, 1_000),
        )
        self.provider = metrics_sdk.MeterProvider(
            metric_readers=[self.reader],
            resource=Resource.create(resource_attributes),
        )
        current_provider = metrics_api.get_meter_provider()
        if not isinstance(current_provider, _ProxyMeterProvider):
            self.provider.shutdown()
            raise RuntimeError(
                "Direct-container OTLP metrics must be configured before another "
                "MeterProvider is installed."
            )

        metrics_api.set_meter_provider(self.provider)
        if metrics_api.get_meter_provider() is not self.provider:
            self.provider.shutdown()
            raise RuntimeError("Direct-container OTLP MeterProvider registration failed.")

        # VeADK 1.x records LLM/tool/skill metrics through a module-level
        # recorder. Recreate it after installing the provider so its
        # instruments bind to this direct pipeline. Keep the scope used by the
        # existing AgentKit APM dashboard.
        self.recorder = portal_metrics.PortalMetricRecorder(name="apmplus_meter")
        portal_metrics.portal_metric_recorder = self.recorder
        self.meter = self.recorder.meter
        self.llm_invoke_counter = self.recorder.llm_invoke_counter


@dataclass
class DirectObservabilityRuntime:
    meter_pipeline: DirectOTLPMeterPipeline | None = None
    logger_provider: LoggerProvider | None = None
    logging_handler: LoggingHandler | None = None


_runtime = DirectObservabilityRuntime()


def _configure_metrics(resource_attributes: dict[str, str]) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "").strip()
    if not endpoint or not _signal_exporter_enabled("METRICS"):
        logger.info("Direct-container OTLP metrics disabled by environment configuration.")
        return
    protocol = _signal_protocol("METRICS")
    if protocol not in _SUPPORTED_PROTOCOLS:
        logger.warning("Direct-container OTLP metrics disabled: unsupported protocol %s.", protocol)
        return
    _runtime.meter_pipeline = DirectOTLPMeterPipeline(
        endpoint=endpoint,
        protocol=protocol,
        resource_attributes=resource_attributes,
    )
    logger.info("Direct-container OTLP metrics exporter initialized (%s).", protocol)


def _configure_logs(resource_attributes: dict[str, str]) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "").strip()
    if not endpoint or not _signal_exporter_enabled("LOGS"):
        logger.info("Direct-container OTLP logs disabled by environment configuration.")
        return
    protocol = _signal_protocol("LOGS")
    if protocol not in _SUPPORTED_PROTOCOLS:
        logger.warning("Direct-container OTLP logs disabled: unsupported protocol %s.", protocol)
        return

    provider = LoggerProvider(resource=Resource.create(resource_attributes))
    provider.add_log_record_processor(BatchLogRecordProcessor(_log_exporter(endpoint, protocol)))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    setattr(handler, _DIRECT_LOG_HANDLER_MARKER, True)
    _runtime.logger_provider = provider
    _runtime.logging_handler = handler
    ensure_direct_otel_logging_handlers()
    logger.info("Direct-container OTLP logs exporter initialized (%s).", protocol)


def ensure_direct_otel_logging_handlers() -> None:
    """Attach the OTLP handler after Uvicorn applies its log configuration."""
    handler = _runtime.logging_handler
    if handler is None:
        return

    level_name = os.getenv("OTEL_PYTHON_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    handler.setLevel(level)
    # VeADK configures the stdlib root logger at ERROR. Lower the effective
    # level so INFO/WARNING records reach the OpenTelemetry handler.
    logging.getLogger().setLevel(level)

    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        if any(getattr(item, _DIRECT_LOG_HANDLER_MARKER, False) for item in target.handlers):
            continue
        # Uvicorn loggers may have propagation disabled, so attach the same
        # handler to them explicitly.
        if name == "" or not target.propagate:
            target.addHandler(handler)


def configure_direct_observability(resource_attributes: dict[str, str]) -> None:
    """Configure explicitly requested metrics and logs for direct Docker mode."""
    _configure_metrics(resource_attributes)
    _configure_logs(resource_attributes)


def build_direct_container_tracers(default_service_name: str) -> list[Any]:
    """Build opt-in direct-container tracing after metrics/logs registration."""
    resource_attributes = direct_resource_attributes(default_service_name)
    configure_direct_observability(resource_attributes)

    trace_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if trace_endpoint:
        trace_protocol = _signal_protocol("TRACES")
        if trace_protocol != "http/protobuf":
            raise ValueError(
                "Direct-container traces currently require "
                "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf."
            )

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from veadk.tracing.telemetry.exporters.base_exporter import BaseExporter
        from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer

        exporter = BaseExporter(
            resource_attributes=resource_attributes,
            processor=BatchSpanProcessor(OTLPSpanExporter(endpoint=trace_endpoint)),
        )
        logger.info("Direct-container OTLP HTTP trace exporter initialized explicitly.")
        return [OpentelemetryTracer(exporters=[exporter])]

    if os.getenv("ENABLE_APMPLUS", "false").lower() == "true":
        from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
        from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer

        logger.info("Direct-container APMPlus exporter initialized explicitly.")
        return [OpentelemetryTracer(exporters=[APMPlusExporter()])]

    logger.warning("Direct-container tracing disabled: no trace endpoint configured.")
    return []
