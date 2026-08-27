from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
from types import ModuleType
from types import SimpleNamespace

import pytest

import agent
import direct_observability
from direct_observability import (
    _parse_key_value_list,
    _signal_exporter_enabled,
    _signal_headers,
    _signal_protocol,
    _signal_timeout,
    build_direct_container_tracers,
    direct_resource_attributes,
)


class _FakeAgent:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.tools = kwargs["tools"]


def _prepare_agent_build(monkeypatch) -> None:
    import veadk

    monkeypatch.setattr(veadk, "Agent", _FakeAgent)
    monkeypatch.setattr(agent, "build_platform_knowledge", lambda _: None)
    monkeypatch.setattr(agent, "build_platform_memory", lambda _: None)
    monkeypatch.setattr(agent, "build_platform_mcp_router", lambda: None)
    monkeypatch.setattr(agent, "configured_skill_space_ids", lambda: [])
    monkeypatch.setattr(agent, "a2a_data_agent_configured", lambda: False)
    monkeypatch.setattr(agent, "platform_sandbox_configured", lambda: False)
    monkeypatch.setattr(agent, "normalize_knowledge_tool_metadata", lambda _: None)
    monkeypatch.setattr(agent, "normalize_memory_tool_metadata", lambda _: None)
    monkeypatch.setattr(
        agent,
        "settings",
        SimpleNamespace(model_name=None, model_api_key=None, model_api_base=None),
    )


def test_managed_runtime_does_not_enable_direct_tracers_by_default(monkeypatch) -> None:
    _prepare_agent_build(monkeypatch)
    monkeypatch.delenv("DIRECT_CONTAINER_MODE", raising=False)
    monkeypatch.setattr(
        direct_observability,
        "build_direct_container_tracers",
        lambda _: pytest.fail("managed Runtime must not build direct exporters"),
    )

    built = agent.build_agent()

    assert "tracers" not in built.kwargs
    assert built.kwargs["model_name"] == ""
    assert built.kwargs["model_api_key"] == ""
    assert built.kwargs["model_api_base"] == ""


def test_direct_container_mode_attaches_explicit_tracers(monkeypatch) -> None:
    _prepare_agent_build(monkeypatch)
    tracers = [object()]
    monkeypatch.setenv("DIRECT_CONTAINER_MODE", "true")
    monkeypatch.setattr(
        direct_observability,
        "build_direct_container_tracers",
        lambda app_name: tracers if app_name == "hybrid_cloud_customer_service" else [],
    )

    built = agent.build_agent()

    assert built.kwargs["tracers"] is tracers


def test_main_uses_configured_bind_host_in_demo_mode(monkeypatch) -> None:
    import uvicorn

    calls = []
    monkeypatch.setattr(agent, "settings", SimpleNamespace(effective_mode="demo"))
    monkeypatch.setenv("APP_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "18000")
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    agent.main()

    assert calls == [(("demo_app:app",), {"host": "127.0.0.1", "port": 18000})]


def test_main_attaches_direct_logging_handler_in_live_mode(monkeypatch) -> None:
    import agentkit.apps

    events = []
    middleware = []
    runs = []

    class FakeFastAPI:
        def __init__(self) -> None:
            self.router = SimpleNamespace(routes=[])

        def add_event_handler(self, event, handler) -> None:
            events.append((event, handler))

        def add_middleware(self, item) -> None:
            middleware.append(item)

    class FakeServer:
        def __init__(self, **kwargs) -> None:
            self.app = FakeFastAPI()

        def run(self, **kwargs) -> None:
            runs.append(kwargs)

    marker = object()
    monkeypatch.setattr(agent, "settings", SimpleNamespace(effective_mode="live"))
    monkeypatch.setattr(agent, "build_agent", lambda: marker)
    monkeypatch.setattr(agent, "build_short_term_memory", lambda _: marker)
    monkeypatch.setattr(agentkit.apps, "AgentkitAgentServerApp", FakeServer)
    monkeypatch.setenv("DIRECT_CONTAINER_MODE", "yes")
    monkeypatch.setenv("APP_BIND_HOST", "127.0.0.2")
    monkeypatch.setenv("PORT", "18001")

    agent.main()

    assert events == [("startup", direct_observability.ensure_direct_otel_logging_handlers)]
    assert middleware == [
        agent.RequestAuthorizationMiddleware,
        agent.PublicInvokeOriginMiddleware,
    ]
    assert runs == [{"host": "127.0.0.2", "port": 18001}]


def test_parse_otel_key_value_list_decodes_values() -> None:
    assert _parse_key_value_list("tenant=demo%20bank,region=cn-beijing,ignored") == {
        "tenant": "demo bank",
        "region": "cn-beijing",
    }


def test_service_name_overrides_resource_attribute(monkeypatch) -> None:
    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES",
        "service.name=old,apmplus.business_carrier=agentkit_runtime",
    )
    monkeypatch.setenv("OTEL_SERVICE_NAME", "direct-service")

    assert direct_resource_attributes("fallback") == {
        "service.name": "direct-service",
        "apmplus.business_carrier": "agentkit_runtime",
    }


def test_signal_configuration_follows_otel_precedence(monkeypatch, caplog) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "shared=value%201")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_HEADERS", "metric=value%202")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", "http/protobuf")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "9")

    assert _signal_headers("METRICS") == {"metric": "value 2"}
    assert _signal_headers("LOGS") == {"shared": "value 1"}
    assert _signal_protocol("METRICS") == "http/protobuf"
    assert _signal_protocol("LOGS") == "grpc"
    assert _signal_timeout("LOGS") == 9

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_TIMEOUT", "invalid")
    with caplog.at_level(logging.WARNING):
        assert _signal_timeout("LOGS") is None
    assert "Ignoring invalid OTEL logs timeout" in caplog.text


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", True), ("otlp", True), ("otlp,console", True), ("none", False)],
)
def test_signal_exporter_enablement(monkeypatch, value: str, expected: bool) -> None:
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", value)
    assert _signal_exporter_enabled("METRICS") is expected


def test_non_otlp_exporter_is_rejected(monkeypatch, caplog) -> None:
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "console")
    with caplog.at_level(logging.WARNING):
        assert _signal_exporter_enabled("LOGS") is False
    assert "exporter is not otlp" in caplog.text


@pytest.mark.parametrize("protocol", ["http/protobuf", "grpc"])
def test_metric_and_log_exporters_support_both_protocols(monkeypatch, protocol) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "tenant=demo")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "3")

    metric_exporter = direct_observability._metric_exporter(
        "http://127.0.0.1:4318/v1/metrics", protocol
    )
    log_exporter = direct_observability._log_exporter("http://127.0.0.1:4318/v1/logs", protocol)

    assert metric_exporter is not None
    assert log_exporter is not None


def test_signal_configuration_skips_missing_or_unsupported_endpoints(monkeypatch, caplog) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://collector/v1/logs")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", "json")
    monkeypatch.setattr(direct_observability._runtime, "logging_handler", None)

    with caplog.at_level(logging.INFO):
        direct_observability._configure_metrics({"service.name": "direct-test"})
        direct_observability._configure_logs({"service.name": "direct-test"})
        direct_observability.ensure_direct_otel_logging_handlers()

    assert "metrics disabled" in caplog.text
    assert "unsupported protocol json" in caplog.text


def test_metric_pipeline_registers_provider_before_veadk_recorder(monkeypatch) -> None:
    events = []

    class FakeProxy:
        pass

    class FakeProvider:
        def __init__(self, **kwargs) -> None:
            events.append(("provider", kwargs))

        def shutdown(self) -> None:
            events.append(("shutdown", {}))

    class FakeRecorder:
        def __init__(self, name) -> None:
            events.append(("recorder", {"name": name}))
            self.meter = object()
            self.llm_invoke_counter = object()

    current = FakeProxy()
    installed = []
    monkeypatch.setattr(direct_observability, "_ProxyMeterProvider", FakeProxy)
    monkeypatch.setattr(direct_observability, "_metric_exporter", lambda *args: object())
    monkeypatch.setattr(
        direct_observability,
        "PeriodicExportingMetricReader",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(direct_observability.metrics_sdk, "MeterProvider", FakeProvider)
    monkeypatch.setattr(
        direct_observability.metrics_api,
        "get_meter_provider",
        lambda: installed[-1] if installed else current,
    )
    monkeypatch.setattr(direct_observability.metrics_api, "set_meter_provider", installed.append)
    monkeypatch.setattr(direct_observability.portal_metrics, "PortalMetricRecorder", FakeRecorder)
    monkeypatch.setattr(
        direct_observability.portal_metrics,
        "portal_metric_recorder",
        direct_observability.portal_metrics.portal_metric_recorder,
    )
    monkeypatch.setenv("OTEL_METRIC_EXPORT_INTERVAL", "invalid")

    pipeline = direct_observability.DirectOTLPMeterPipeline(
        endpoint="http://collector/v1/metrics",
        protocol="http/protobuf",
        resource_attributes={"service.name": "direct-test"},
    )

    assert installed == [pipeline.provider]
    assert [name for name, _ in events] == ["provider", "recorder"]
    assert direct_observability.portal_metrics.portal_metric_recorder is pipeline.recorder


def test_direct_http_trace_exporter_uses_explicit_endpoint(monkeypatch) -> None:
    import opentelemetry.exporter.otlp.proto.http.trace_exporter as trace_exporter_module
    import opentelemetry.sdk.trace.export as trace_sdk_export
    import veadk.tracing.telemetry.exporters.base_exporter as base_exporter_module
    import veadk.tracing.telemetry.opentelemetry_tracer as tracer_module

    class FakeSpanExporter:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeProcessor:
        def __init__(self, exporter) -> None:
            self.exporter = exporter

    class FakeBaseExporter:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeTracer:
        def __init__(self, exporters) -> None:
            self.exporters = exporters

    monkeypatch.setattr(direct_observability, "configure_direct_observability", lambda _: None)
    monkeypatch.setattr(trace_exporter_module, "OTLPSpanExporter", FakeSpanExporter)
    monkeypatch.setattr(trace_sdk_export, "BatchSpanProcessor", FakeProcessor)
    monkeypatch.setattr(base_exporter_module, "BaseExporter", FakeBaseExporter)
    monkeypatch.setattr(tracer_module, "OpentelemetryTracer", FakeTracer)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "http/protobuf")

    tracers = build_direct_container_tracers("direct-test")

    assert tracers[0].exporters[0].kwargs["resource_attributes"] == {"service.name": "direct-test"}
    processor = tracers[0].exporters[0].kwargs["processor"]
    assert processor.exporter.kwargs["endpoint"] == "http://collector/v1/traces"


def test_direct_tracing_rejects_unsupported_protocol(monkeypatch) -> None:
    monkeypatch.setattr(direct_observability, "configure_direct_observability", lambda _: None)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector/v1/traces")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "grpc")

    with pytest.raises(ValueError, match="http/protobuf"):
        build_direct_container_tracers("direct-test")


def test_direct_tracing_can_be_disabled_without_affecting_managed_runtime(
    monkeypatch, caplog
) -> None:
    configured = []
    monkeypatch.setattr(
        direct_observability,
        "configure_direct_observability",
        lambda attributes: configured.append(attributes),
    )
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("ENABLE_APMPLUS", "false")

    with caplog.at_level(logging.WARNING):
        assert build_direct_container_tracers("direct-test") == []
    assert configured == [{"service.name": "direct-test"}]
    assert "no trace endpoint configured" in caplog.text


def test_apmplus_fallback_is_built_lazily(monkeypatch) -> None:
    apm_module = ModuleType("veadk.tracing.telemetry.exporters.apmplus_exporter")
    tracer_module = ModuleType("veadk.tracing.telemetry.opentelemetry_tracer")

    class FakeAPMPlusExporter:
        pass

    class FakeTracer:
        def __init__(self, exporters) -> None:
            self.exporters = exporters

    apm_module.APMPlusExporter = FakeAPMPlusExporter
    tracer_module.OpentelemetryTracer = FakeTracer
    monkeypatch.setitem(sys.modules, apm_module.__name__, apm_module)
    monkeypatch.setitem(sys.modules, tracer_module.__name__, tracer_module)
    monkeypatch.setattr(direct_observability, "configure_direct_observability", lambda _: None)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("ENABLE_APMPLUS", "true")

    tracers = build_direct_container_tracers("direct-test")

    assert len(tracers) == 1
    assert isinstance(tracers[0], FakeTracer)
    assert isinstance(tracers[0].exporters[0], FakeAPMPlusExporter)


def test_logging_handlers_are_idempotent(monkeypatch) -> None:
    handler = logging.NullHandler()
    setattr(handler, direct_observability._DIRECT_LOG_HANDLER_MARKER, True)
    monkeypatch.setattr(direct_observability._runtime, "logging_handler", handler)
    monkeypatch.setenv("OTEL_PYTHON_LOG_LEVEL", "WARNING")
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        direct_observability.ensure_direct_otel_logging_handlers()
        direct_observability.ensure_direct_otel_logging_handlers()
        assert sum(item is handler for item in root.handlers) == 1
        assert root.level == logging.WARNING
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)


def test_http_traces_metrics_and_logs_export_protobuf_to_independent_endpoints() -> None:
    script = textwrap.dedent(
        """
        import logging
        import os
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from opentelemetry import trace

        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("content-length", "0")))
                received.append((self.path, self.headers.get("content-type"), len(body)))
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        os.environ.update(
            {
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": base + "/v1/traces",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": base + "/v1/metrics",
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": base + "/v1/logs",
                "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
                "OTEL_METRIC_EXPORT_INTERVAL": "60000",
            }
        )

        from direct_observability import _runtime, build_direct_container_tracers
        from veadk.tracing.telemetry import portal_metrics

        tracers = build_direct_container_tracers("direct-test")
        assert len(tracers) == 1
        assert _runtime.meter_pipeline.meter.name == "apmplus_meter"
        assert _runtime.meter_pipeline.recorder is portal_metrics.portal_metric_recorder
        _runtime.meter_pipeline.llm_invoke_counter.add(1, {"test": "yes"})
        logging.getLogger("direct-test").warning("LOG_EXPORT_CANARY")
        with trace.get_tracer("direct-test").start_as_current_span("TRACE_EXPORT_CANARY"):
            pass
        tracers[0].force_export()
        assert _runtime.meter_pipeline.provider.force_flush(timeout_millis=5000)
        assert _runtime.logger_provider.force_flush(timeout_millis=5000)
        assert any(
            path == "/v1/traces" and content_type == "application/x-protobuf" and size > 0
            for path, content_type, size in received
        )
        assert any(
            path == "/v1/metrics" and content_type == "application/x-protobuf" and size > 0
            for path, content_type, size in received
        )
        assert any(
            path == "/v1/logs" and content_type == "application/x-protobuf" and size > 0
            for path, content_type, size in received
        )
        _runtime.meter_pipeline.provider.shutdown()
        _runtime.logger_provider.shutdown()
        server.shutdown()
        """
    )
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("OTEL_EXPORTER_OTLP_") or key.startswith("OTEL_METRIC_"):
            env.pop(key)

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
