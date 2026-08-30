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
