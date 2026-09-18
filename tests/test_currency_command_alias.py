from dataclasses import replace
from types import SimpleNamespace

import pytest
from twitchio.ext.commands.view import StringView

from bot.context import ChannelContext
from bot.profiles import ChannelProfile, PointsConfig, activate_profile, clear_profiles
from bot.shared.commands.points import PointsCommands


@pytest.fixture(autouse=True)
def profiles():
    clear_profiles()
    yield
    clear_profiles()


def resolve(text, channel="1", extra=None):
    group = PointsCommands.points
    registered = {"points": group, **(extra or {})}
    ctx = object.__new__(ChannelContext)
    ctx._bot = SimpleNamespace(_commands=registered, get_command=registered.get)
    ctx._payload = SimpleNamespace(broadcaster=SimpleNamespace(id=channel))
    ctx._command = None
    ctx._prefix = "!"
    ctx._invoked_with = None
    ctx._prepare_called = False
    ctx._view = StringView(text)
    ctx._get_command()
    return ctx


def test_alias_resolves_points_group_and_preserves_arguments():
    activate_profile("1", ChannelProfile(channel_name="test", points=PointsConfig(display_name="bombs")))
    ctx = resolve("!BOMBS gamble 50")
    assert ctx.command is PointsCommands.points
    ctx._view.skip_ws()
    assert ctx._view.get_word() == "gamble"
    ctx._view.skip_ws()
    assert ctx._view.get_word() == "50"
    assert resolve("!points").command is PointsCommands.points
    assert resolve("!bomb").command is None
    assert resolve("!bombs", channel="2").command is None


def test_alias_changes_immediately_and_existing_commands_win():
    profile = ChannelProfile(channel_name="test", points=PointsConfig(display_name="bombs"))
    activate_profile("1", profile)
    existing = object()
    assert resolve("!bombs", extra={"bombs": existing}).command is existing
    activate_profile("1", replace(profile, points=replace(profile.points, display_name="coins")))
    assert resolve("!bombs").command is None
    assert resolve("!coins").command is PointsCommands.points
    activate_profile("1", replace(profile, points=PointsConfig()))
    assert resolve("!coins").command is None
    assert resolve("!points").command is PointsCommands.points


@pytest.mark.parametrize("name,alias", [("Stale Bread", "stalebread"), ("Sakura Petals!", "sakurapetals"), ("", "points")])
def test_currency_alias_normalizes_names(name, alias):
    assert PointsConfig(display_name=name).command_alias == alias
