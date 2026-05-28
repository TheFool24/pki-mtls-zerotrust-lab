"""Entry point — concurrent heartbeat task + aiohttp metrics server in one
event loop. Single systemd unit, one restart unit, no inter-process plumbing."""
import asyncio
import signal

from aiohttp import web

from app.config import settings
from app.heartbeat import run as run_heartbeat
from app.logging_setup import configure as configure_logging, get_logger
from app.metrics_server import build_app, build_ssl_context

configure_logging()
log = get_logger("main")


async def _serve_metrics(stop_event: asyncio.Event) -> None:
    app = build_app()
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=settings.metrics_bind,
        port=settings.metrics_port,
        ssl_context=build_ssl_context(),
    )
    await site.start()
    log.info("metrics_server_listening",
             bind=settings.metrics_bind,
             port=settings.metrics_port,
             allowed_scrapers=sorted(settings.allowed_cns_set()))
    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    log.info("agent_starting",
             node_id=settings.node_id,
             common_name=settings.node_common_name,
             controller=settings.controller_url)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    heartbeat_task = asyncio.create_task(run_heartbeat(), name="heartbeat")
    metrics_task = asyncio.create_task(_serve_metrics(stop_event), name="metrics_server")
    stopper = asyncio.create_task(stop_event.wait(), name="stopper")

    # Wake on the FIRST of: a worker crashing, OR a shutdown signal. Using
    # FIRST_COMPLETED (not FIRST_EXCEPTION) so that SIGTERM — which completes
    # `stopper` without raising — actually tears the process down instead of
    # leaving the heartbeat loop running until systemd SIGKILLs it.
    workers = {heartbeat_task, metrics_task}
    done, pending = await asyncio.wait(
        workers | {stopper}, return_when=asyncio.FIRST_COMPLETED
    )

    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    if stopper in done:
        log.info("agent_stopped", reason="signal")
        return
    # Otherwise a worker finished first — only ever by crashing. Surface it so
    # systemd's Restart=on-failure kicks in.
    for t in done:
        if t is stopper:
            continue
        exc = t.exception()
        if exc:
            log.error("task_crashed", task=t.get_name(), error=str(exc))
            raise exc


if __name__ == "__main__":
    asyncio.run(main())
