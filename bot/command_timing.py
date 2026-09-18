import logging
from time import perf_counter

LOGGER = logging.getLogger("RatBoomBot")


def start_command_timing(ctx, text: str, prefix: str) -> None:
    command = text.split(maxsplit=1)[0].lower() if text else ""
    if command not in {f"{prefix}hi", f"{prefix}points"}:
        return
    ctx.command_timing_started = perf_counter()
    ctx.command_timing_name = command
    log_command_timing(ctx, "received")


def log_command_timing(ctx, stage: str, *, send_ms: float | None = None, result=None) -> None:
    started = getattr(ctx, "command_timing_started", None)
    if started is None:
        return
    broadcaster = ctx.broadcaster
    message = getattr(ctx, "message", None)
    LOGGER.info(
        "[CommandTiming] stage=%s channel=%s channel_id=%s message_id=%s command=%s elapsed_ms=%.1f send_ms=%s is_sent=%s",
        stage, getattr(broadcaster, "name", "unknown"), broadcaster.id,
        getattr(message, "id", "unknown"), ctx.command_timing_name,
        (perf_counter() - started) * 1000,
        f"{send_ms:.1f}" if send_ms is not None else "-",
        getattr(result, "is_sent", "-"),
        extra={"broadcaster_id": str(broadcaster.id), "markup": False}
    )
