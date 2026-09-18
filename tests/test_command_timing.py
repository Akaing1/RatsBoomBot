import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.command_timing import start_command_timing
from bot.context import ChannelContext


class TimingContext(ChannelContext):
    def __init__(self, sender):
        self._test_bot = SimpleNamespace(services=SimpleNamespace(chat_identity=SimpleNamespace(send_message=sender)))

    @property
    def bot(self):
        return self._test_bot

    @property
    def broadcaster(self):
        return SimpleNamespace(id="123", name="minamichimaa")

    @property
    def message(self):
        return SimpleNamespace(id="message-1")


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [True, False])
async def test_command_timing_records_stages_and_preserves_send(reply, caplog):
    result = SimpleNamespace(is_sent=True)
    sender = AsyncMock(return_value=result)
    ctx = TimingContext(sender)
    with caplog.at_level(logging.INFO, logger="RatBoomBot"):
        start_command_timing(ctx, "!hi", "!")
        actual = await ctx.reply("test reply") if reply else await ctx.send("test reply")
    assert actual is result
    expected = {"me": False}
    if reply:
        expected["reply_to_message_id"] = "message-1"
    sender.assert_awaited_once_with(ctx.broadcaster, "test reply", **expected)
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 3
    assert "stage=received" in messages[0]
    assert "stage=send_start" in messages[1]
    assert "stage=send_complete" in messages[2]
    assert "is_sent=True" in messages[2]
    assert all("message_id=message-1" in message for message in messages)
    assert "test reply" not in caplog.text


@pytest.mark.asyncio
async def test_timing_logs_failure_and_preserves_exception(caplog):
    ctx = TimingContext(AsyncMock(side_effect=RuntimeError("send failed")))
    with caplog.at_level(logging.INFO, logger="RatBoomBot"):
        start_command_timing(ctx, "!points", "!")
        with pytest.raises(RuntimeError, match="send failed"):
            await ctx.reply("test reply")
    assert "stage=send_failed" in caplog.text
    assert "stage=send_complete" not in caplog.text


@pytest.mark.asyncio
async def test_unrelated_commands_do_not_generate_timing_logs(caplog):
    ctx = TimingContext(AsyncMock())
    with caplog.at_level(logging.INFO, logger="RatBoomBot"):
        start_command_timing(ctx, "!lurk private arguments", "!")
        await ctx.reply("test reply")
    assert not caplog.records
