"""Presentation groups for the channel settings notebook."""

from bot.command_registry import get_registered_definitions, CommandVisibility
from bot.profiles import ChannelProfile

SECTIONS = (
    ("general", "General", "Channel-wide switches and dashboard preferences.", "M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0"),
    ("chat", "Chat", "Commands and chat responses.", "M21 11a8 8 0 0 1-8 8H7l-4 3V11a9 9 0 0 1 18 0ZM7 10h10M7 14h6"),
    ("loyalty", "Loyalty Points", "Your currency, command controls, and response wording.", "M20 6c0 2-4 3-8 3S4 8 4 6s4-3 8-3 8 1 8 3ZM4 6v12c0 2 4 3 8 3s8-1 8-3V6M4 12c0 2 4 3 8 3s8-1 8-3"),
    ("queue", "Viewer Queue", "Queue availability and who can join.", "M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"),
    ("pets", "Pets and Boss Hunt", "Pets and Boss Hunt settings.", "M6 8h12a3 3 0 0 1 3 3v7a2 2 0 0 1-3 1l-3-3H9l-3 3a2 2 0 0 1-3-1v-7a3 3 0 0 1 3-3ZM6 12h4M8 10v4M16 11h1M18 14h1"),
    ("events", "Stream Events", "Community messages, Twitch raids, shoutouts, and redeems.", "M4 10v5h4l10 5V4L8 10H4ZM8 15l2 6M21 9v6"),
    ("timers", "Timers", "Automated chat messages and their availability.", "M9 2h6M12 5v2M19 5l-2 2M20 14a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM12 10v5l3 2"),
    ("connections", "Connections", "Social links and bot identity.", "M9 15l6-6M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1"),
)

GROUP_SECTION = {
    "Commands": "chat", "Loyalty points": "loyalty", "Timers": "timers",
    "Community messages": "events", "Raid messages": "events", "Shoutouts": "events", "Redeems": "events",
    "League of Legends": "games", "Overwatch": "games", "Raid boss names": "pets", "Raid item names": "pets",
}
TOGGLE_SECTION = {
    "feature": {"points": "loyalty", "timers": "timers", "raid_bosses": "pets", "redeems": "events", "follow_responses": "events", "subscription_responses": "events", "resubscription_responses": "events", "gifted_subscription_responses": "events", "raid_responses": "events", "ad_announcements": "events"},
    "global_group": {"points": "loyalty", "viewer_queue": "queue", "shoutouts": "events", "socials": "connections", "clips": "chat", "settings": "chat"},
}
LABELS = {"raid_bosses": "Boss Hunt", "globals": "All global commands", "channel": "Channel profile", "points": "Loyalty Points", "league": "League of Legends"}


TOGGLE_DESCRIPTIONS = {
    ("feature", "channel"): "Enable this channel's bot profile and its features.",
    ("feature", "timers"): "Send your scheduled chat messages and announcements.",
    ("feature", "ad_announcements"): "Notify chat before a scheduled ad break starts.",
    ("feature", "points"): "Enable the channel's loyalty points features.",
    ("feature", "raid_bosses"): "Enable Boss Hunt battles and progression.",
    ("global_group", "globals"): "Allow shared bot commands; individual command switches still apply.",
    ("global_group", "points"): "Balance, gifting, gambling and points management commands.",
    ("global_group", "viewer_queue"): "Let viewers join the queue and moderators manage it.",
    ("global_group", "shoutouts"): "Promote another channel with a shoutout.",
    ("global_group", "socials"): "Share your configured community and social links.",
    ("global_group", "settings"): "Manage supported channel settings from chat.",
    ("global_group", "clips"): "Create clips and share clip links from chat.",
    ("profile_feature", "league"): "Enable League of Legends builds, ranks and lobby tools.",
    ("profile_feature", "overwatch"): "Enable commands for your configured Overwatch player.",
    **{("feature", f"redeem_{name}"): f"Let the bot process the channel's {name.upper() if name == 'vip' else name} reward." for name in ("daily", "first", "second", "vip")},
}


def build_settings_sections(groups, channel_features, profile_features, global_groups, global_commands, profile=None):
    sections = {key: dict(key=key, label=label, description=description, icon=icon, groups={}, toggles=[]) for key, label, description, icon in SECTIONS}
    sections['games'] = dict(key='games', label='Games', description='Settings for your enabled game integrations.', icon=sections['pets']['icon'], groups={}, toggles=[])
    definitions = [command for command in get_registered_definitions(profile or ChannelProfile(channel_name="settings")) if command.visibility is CommandVisibility.PUBLIC]
    enabled_games = {name.value for name, state in profile_features.items() if state.effective_enabled}
    for name, entries in groups.items():
        game = {'League of Legends': 'league', 'Overwatch': 'overwatch'}.get(name)
        if game and game not in enabled_games:
            continue
        sections[GROUP_SECTION.get(name, "general")]["groups"][name] = entries
    for kind, states in (("feature", channel_features), ("profile_feature", profile_features), ("global_group", global_groups), ("global_command", global_commands)):
        for name, state in states.items():
            value = name.value
            if kind == "feature" and value in {"redeems", "timers"}:
                continue
            if kind == "profile_feature":
                section = "general"
            elif kind == "global_command":
                section = "pets" if value == "pets" else "chat"
            else:
                section = "events" if kind == "feature" and value.startswith("redeem_") else TOGGLE_SECTION.get(kind, {}).get(value, "general")
            label = "!" + value if kind == "global_command" else LABELS.get(value, value.replace("_", " ").title())
            if kind == "feature" and value.startswith("redeem_"):
                label = value.removeprefix("redeem_").title() + " redeem"
            if kind == "global_group" and value != "globals":
                label += " commands"
            commands = [command for command in definitions if (
                (kind == "global_group" and value == "globals" and (command.global_group is not None or command.global_command is not None))
                or getattr(command, kind, None) == name
            )]
            description = TOGGLE_DESCRIPTIONS.get((kind, value)) or (commands[0].description if commands else f"Enable {label.lower()} for this channel.")
            if section == "pets":
                panel = "Pets" if kind == "global_command" else "Boss Hunt"
            elif section == "general" and kind == "global_group":
                panel = "Commands"
            elif value == "quote" or kind == "global_group":
                panel = "Command groups"
            else:
                panel = {"feature": "Feature controls", "profile_feature": "Game integrations", "global_command": "Chat commands"}[kind]
            show_commands = (kind == "global_group" and value != "globals") or (kind == "global_command" and value == "quote")
            sections[section]["toggles"].append(dict(kind=kind, name=value, label=label, state=state,
                description=description, commands=commands if show_commands else [], panel=panel))
    group_controls = {
        ('feature', 'points'): 'Loyalty points', ('global_group', 'points'): 'Loyalty points',
        ('feature', 'raid_responses'): 'Raid messages',
        ('global_group', 'shoutouts'): 'Shoutouts', ('global_command', 'lurk'): 'Commands',
        **{('feature', name): 'Community messages' for name in (
            'follow_responses', 'subscription_responses', 'resubscription_responses', 'gifted_subscription_responses')},
    }
    setting_controls = {
        **{("feature", f"redeem_{name}"): f"redeems.{name}_title" for name in ("daily", "first", "second", "vip")},
        ('feature', 'follow_responses'): 'community_messages.follow',
        ('feature', 'subscription_responses'): 'community_messages.subscription',
        ('feature', 'resubscription_responses'): 'community_messages.resubscription',
        ('feature', 'gifted_subscription_responses'): 'community_messages.gifted_subscription',
        ('global_command', 'lurk'): 'lurk_message',
    }
    for section in sections.values():
        section['group_toggles'] = {}
        section['setting_toggles'] = {}
        setting_keys = {entry.definition.key for entries in section['groups'].values() for entry in entries}
        section['standalone_toggles'] = []
        section['blocked'] = any(getattr(t['state'], 'blocked_by_profile', False) or getattr(t['state'], 'blocked_by_globals', False) for t in section['toggles'])
        for toggle in section['toggles']:
            setting_key = setting_controls.get((toggle['kind'], toggle['name']))
            if setting_key in setting_keys:
                section['setting_toggles'][setting_key] = toggle
                continue
            group = group_controls.get((toggle['kind'], toggle['name']))
            if group in section['groups']:
                section['group_toggles'].setdefault(group, []).append(toggle)
            else:
                section['standalone_toggles'].append(toggle)
    order = ('general', 'chat', 'events', 'timers', 'connections', 'loyalty', 'queue', 'pets', 'games')
    return [sections[key] for key in order if key != 'games' or enabled_games]
