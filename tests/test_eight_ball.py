import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.profiles import GlobalCommandName
from bot.services.engagement.eight_ball import EightBallService, question_category
from bot.shared.commands.utility import UtilityCommands
from storage.migration_runner import run_migrations


@pytest.mark.parametrize(("question", "category"), [
    ("Is Meinya short?", "statement"),
    ("  IS   meinya short?", "statement"),
    ("Isn't Meinya tall?", "statement"),
    ("Will we win?", "prediction"),
    ("Won’t we win?", "prediction"),
    ("Should I gamble all?", "advice"),
    ("Can I beat this boss?", "ability"),
    ("Can Meinya beat this boss?", "general"),
    ("Should Meinya gamble?", "general"),
    ("Can ice melt?", "general"),
    ("Something unexpected?", "general"),
])
def test_question_categories(question, category):
    assert question_category(question) == category


@pytest.mark.asyncio
async def test_answers_fit_question_type_and_choose_verdict_independently(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "8ball.db")) as db:
        await run_migrations(db)
        service = EightBallService(db)
        # Request known replies without depending on catalog order or pool size.
        monkeypatch.setattr("bot.services.engagement.eight_ball.random.choice",
                            lambda items: "yes" if isinstance(items, tuple) else next(
                                r for preferred in ('statement_yes_2', 'ability_yes_2', 'general_yes_4')
                                for r in items if r['id'] == preferred))
        assert await service.answer("a", "Is Meinya short?") == "That checks out."
        assert await service.answer("a", "Can I win?") == "Yeah, you've got a shot."
        assert await service.answer("a", "Can Meinya win?") == "I'd put cheese on it."
        async with db.acquire() as connection:
            rows = await connection.fetchall("SELECT category, outcome FROM eight_ball_history ORDER BY id")
        assert [row["category"] for row in rows] == ["statement", "ability", "general"]
        assert all(row["outcome"] == "yes" for row in rows)


@pytest.mark.asyncio
async def test_history_survives_restart_is_channel_scoped_and_bounded(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "history.db")) as db:
        await run_migrations(db)
        service = EightBallService(db)
        monkeypatch.setattr("bot.services.engagement.eight_ball.random.choice",
                            lambda items: "no" if isinstance(items, tuple) else items[0])
        first = await service.answer("a", "Is this working?")
        restarted = EightBallService(db)
        assert await restarted.answer("a", "Is this working?") != first
        assert await restarted.answer("b", "Is this working?") == first
        for _ in range(105):
            await restarted.answer("a", "Is this working?")
        async with db.acquire() as connection:
            rows = await connection.fetchall("SELECT broadcaster_id, COUNT(*) AS total FROM eight_ball_history GROUP BY broadcaster_id")
        assert {row["broadcaster_id"]: row["total"] for row in rows} == {"a": 100, "b": 1}


@pytest.mark.asyncio
async def test_concurrent_questions_do_not_repeat_immediately(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "concurrent.db")) as db:
        await run_migrations(db)
        service = EightBallService(db)
        monkeypatch.setattr("bot.services.engagement.eight_ball.random.choice",
                            lambda items: "maybe" if isinstance(items, tuple) else items[0])
        await asyncio.gather(*(service.answer("a", "Will we win?") for _ in range(12)))
        async with db.acquire() as connection:
            rows = await connection.fetchall("SELECT response_id FROM eight_ball_history ORDER BY id")
        ids = [row["response_id"] for row in rows]
        assert len(ids) == 12
        assert all(left != right for left, right in zip(ids, ids[1:]))


@pytest.mark.asyncio
@pytest.mark.parametrize(("enabled", "question", "expected"), [
    (True, "", "Ask me a yes/no question! Example: !8ball Will we win this game?"),
    (True, "   ", "Ask me a yes/no question! Example: !8ball Will we win this game?"),
    (True, "x" * 401, "Keep your question to 400 characters or fewer."),
    (False, "Will we win?", None),
    (True, "Will we win?", "Looking pretty good."),
])
async def test_command_validation_toggle_and_direct_reply(enabled, question, expected):
    answer = AsyncMock(return_value="Looking pretty good.")
    services = SimpleNamespace(
        features=SimpleNamespace(is_global_command_enabled=lambda channel, command: enabled),
        eight_ball=SimpleNamespace(answer=answer),
    )
    ctx = SimpleNamespace(chatter=SimpleNamespace(name="rat"), broadcaster=SimpleNamespace(id="a"), reply=AsyncMock())
    component = UtilityCommands(SimpleNamespace(services=services))
    await component.eight_ball.callback(component, ctx, question=question)
    if expected is None:
        ctx.reply.assert_not_awaited()
    else:
        ctx.reply.assert_awaited_once_with(expected)
    if expected == "Looking pretty good.":
        answer.assert_awaited_once_with("a", question)
    else:
        answer.assert_not_awaited()


def test_eight_ball_appears_in_command_help_and_uses_shared_slowmode():
    from bot.command_registry import UTILITY_COMMANDS, CommandSlowmode
    entry = next(c for c in UTILITY_COMMANDS.commands if c.syntax == "!8ball <question>")
    assert entry.global_command is GlobalCommandName.EIGHT_BALL
    assert entry.slowmode is CommandSlowmode.SHARED
    assert UtilityCommands.eight_ball.name == "8ball"


def test_response_library_has_broad_unique_pools():
    service = EightBallService(None)
    assert len(service.responses) >= 180
    assert len({r['text'].casefold() for r in service.responses}) == len(service.responses)
    for outcome in ('yes', 'maybe', 'no'):
        for category in ('general', 'statement', 'prediction', 'advice', 'ability'):
            eligible = [r for r in service.responses if r['outcome'] == outcome
                        and (category in r['categories'] or 'general' in r['categories'])]
            assert len(eligible) >= (20 if category == 'general' else 30)


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['yes', 'maybe', 'no'])
@pytest.mark.parametrize('question', ['Is Meinya short?', 'Something unexpected?'])
async def test_replies_use_full_pool_before_repeating_even_after_restart(tmp_path, monkeypatch, outcome, question):
    async with asqlite.create_pool(str(tmp_path / 'variety.db')) as db:
        await run_migrations(db)
        service = EightBallService(db)
        category = question_category(question)
        pool = [r for r in service.responses if r['outcome'] == outcome
                and (category in r['categories'] or 'general' in r['categories'])]
        monkeypatch.setattr('bot.services.engagement.eight_ball.random.choice',
                            lambda items: outcome if isinstance(items, tuple) else items[0])
        replies = []
        for index in range(len(pool)):
            if index == len(pool) // 2:
                service = EightBallService(db)
            replies.append(await service.answer('channel', question))
        assert len(set(replies)) == len(pool)
        assert await service.answer('channel', question) == replies[0]
