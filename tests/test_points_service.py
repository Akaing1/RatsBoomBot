import asqlite
import pytest

from bot.services.engagement.points import PointsService


@pytest.mark.asyncio
async def test_transfer_points_moves_balance_between_viewers(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "sender-1", "sender", 100)

        remaining = await service.transfer_points("channel-1", "sender-1", "recipient-1", "recipient", 35)

        assert remaining == 65
        assert await service.get_points("channel-1", "sender-1") == 65
        assert await service.get_points("channel-1", "recipient-1") == 35


@pytest.mark.asyncio
async def test_transfer_points_rejects_insufficient_balance_without_crediting_recipient(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "sender-1", "sender", 20)

        remaining = await service.transfer_points("channel-1", "sender-1", "recipient-1", "recipient", 25)

        assert remaining is None
        assert await service.get_points("channel-1", "sender-1") == 20
        assert await service.get_points("channel-1", "recipient-1") == 0


@pytest.mark.asyncio
async def test_transfer_points_is_isolated_per_broadcaster(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "sender-1", "sender", 100)
        await service.add_points("channel-2", "sender-1", "sender", 100)

        await service.transfer_points("channel-1", "sender-1", "recipient-1", "recipient", 40)

        assert await service.get_points("channel-1", "sender-1") == 60
        assert await service.get_points("channel-2", "sender-1") == 100
        assert await service.get_points("channel-2", "recipient-1") == 0


@pytest.mark.asyncio
async def test_settle_wager_debits_bet_and_credits_total_payout(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "viewer-1", "viewer", 1000)

        balance = await service.settle_wager("channel-1", "viewer-1", "viewer", bet=100, payout=200)

        assert balance == 1100
        assert await service.get_points("channel-1", "viewer-1") == 1100


@pytest.mark.asyncio
async def test_settle_wager_rejects_insufficient_balance_without_changing_points(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "viewer-1", "viewer", 50)

        balance = await service.settle_wager("channel-1", "viewer-1", "viewer", bet=100, payout=200)

        assert balance is None
        assert await service.get_points("channel-1", "viewer-1") == 50


@pytest.mark.asyncio
async def test_settle_wager_tracks_and_credits_gambling_losses(tmp_path, monkeypatch) -> None:
    from config.settings import settings
    from storage.migrations.v023_gambling_loss_totals import migrate

    monkeypatch.setattr(settings, "BOT_ID", "ratsboombot")
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        async with database.acquire() as connection:
            await migrate(connection)

        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "viewer-1", "viewer", 100)

        balance = await service.settle_wager("channel-1", "viewer-1", "viewer", bet=40, payout=0)

        assert balance == 60
        assert await service.get_gambling_loss_total("channel-1") == 40
        assert await service.get_points("channel-1", "ratsboombot") == 40


@pytest.mark.asyncio
async def test_settle_wager_does_not_track_winning_wagers_as_losses(tmp_path, monkeypatch) -> None:
    from config.settings import settings
    from storage.migrations.v023_gambling_loss_totals import migrate

    monkeypatch.setattr(settings, "BOT_ID", "ratsboombot")
    async with asqlite.create_pool(str(tmp_path / "points.db")) as database:
        async with database.acquire() as connection:
            await migrate(connection)

        service = PointsService(bot=None, db=database)
        await service.setup()
        await service.add_points("channel-1", "viewer-1", "viewer", 100)

        await service.settle_wager("channel-1", "viewer-1", "viewer", bet=40, payout=80)

        assert await service.get_gambling_loss_total("channel-1") == 0
        assert await service.get_points("channel-1", "ratsboombot") == 0
