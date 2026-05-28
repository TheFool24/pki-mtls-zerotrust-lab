"""Prometheus exposition — node-side metrics scraped over mTLS.

Heartbeats: explicit counter, incremented from the heartbeat loop.
System metrics: psutil values pulled fresh on each scrape (no background loop
needed — the exposition handler triggers `.collect()` per request)."""
import time

import psutil
from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Info
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest

from app.config import settings

# Dedicated registry — avoids polluting the global one with default
# process/python collectors we don't want exposed externally.
registry = CollectorRegistry()

node_info = Info(
    "thesis_node",
    "Static node identity",
    registry=registry,
)
node_info.info({
    "node_id": settings.node_id,
    "common_name": settings.node_common_name,
    "role": settings.node_role,
})

heartbeats_total = Counter(
    "thesis_node_heartbeats_total",
    "Heartbeat attempts by outcome",
    labelnames=["result"],  # success | failure
    registry=registry,
)

agent_start_time = Gauge(
    "thesis_node_agent_start_time_seconds",
    "Unix timestamp at which the agent process started",
    registry=registry,
)
agent_start_time.set(time.time())


class SystemCollector:
    """Lazy system metrics — pulled on each Prometheus scrape, not buffered.
    Keeps memory flat regardless of how often Prometheus scrapes."""

    def collect(self):  # noqa: ANN201 — prometheus_client interface
        cpu = psutil.cpu_percent(interval=None)
        yield GaugeMetricFamily(
            "thesis_node_cpu_percent",
            "Current CPU utilization (psutil cpu_percent)",
            value=cpu,
        )

        vm = psutil.virtual_memory()
        mem = GaugeMetricFamily(
            "thesis_node_memory_bytes",
            "Memory usage (psutil virtual_memory)",
            labels=["state"],
        )
        mem.add_metric(["total"], vm.total)
        mem.add_metric(["available"], vm.available)
        mem.add_metric(["used"], vm.used)
        yield mem

        du = psutil.disk_usage("/")
        disk = GaugeMetricFamily(
            "thesis_node_disk_bytes",
            "Root filesystem usage (psutil disk_usage / )",
            labels=["state"],
        )
        disk.add_metric(["total"], du.total)
        disk.add_metric(["free"], du.free)
        disk.add_metric(["used"], du.used)
        yield disk

        bt = psutil.boot_time()
        yield GaugeMetricFamily(
            "thesis_node_boot_time_seconds",
            "Unix timestamp at which the host booted",
            value=bt,
        )

        la1, la5, la15 = psutil.getloadavg()
        load = GaugeMetricFamily(
            "thesis_node_load_average",
            "System load average",
            labels=["window"],
        )
        load.add_metric(["1m"], la1)
        load.add_metric(["5m"], la5)
        load.add_metric(["15m"], la15)
        yield load


registry.register(SystemCollector())


def render() -> bytes:
    """Render the current registry state as Prometheus exposition format."""
    return generate_latest(registry)
