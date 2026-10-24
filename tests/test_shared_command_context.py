from types import SimpleNamespace as NS

import pytest

from bot.channels.component import ChannelComponent
from bot.shared.commands import helpers, settings, shoutout, viewer_queue


@pytest.mark.parametrize('ctx,expected', [
    (NS(broadcaster=NS(id=1), channel=NS(id=2)), '1'),
    (NS(channel=NS(id=2)), '2'),
    (NS(message=NS(broadcaster=NS(id=3))), '3'),
    (NS(), None),
])
def test_broadcaster_resolution_preserves_fallback_priority(ctx, expected):
    assert helpers.get_context_broadcaster_id(ctx) == expected
    assert ChannelComponent.get_context_broadcaster_id(ctx) == expected


@pytest.mark.parametrize('ctx,expected', [
    (NS(broadcaster=NS(id='1'), chatter=NS(id='2', name='mod', moderator=True)), True),
    (NS(channel=NS(id='1'), author=NS(id=1, name='owner')), True),
    (NS(channel=NS(id='1'), author=NS(id=2, name='viewer')), False),
    (NS(chatter=NS(id=2, name='mod', moderator=True)), False),
    (NS(broadcaster=NS(id='1')), False),
])
def test_shared_permissions_preserve_mod_owner_and_missing_context_rules(ctx, expected):
    for module in (helpers, settings, shoutout, viewer_queue):
        assert module.is_mod_or_broadcaster(ctx) == expected
    assert helpers.has_moderator_permission(ctx, 'test') == expected
