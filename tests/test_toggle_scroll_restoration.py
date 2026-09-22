from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_admin_channel_toggles_preserve_scroll_position() -> None:
    template = (PROJECT_ROOT / "web/templates/admin/channel_details.html").read_text(encoding="utf-8")

    assert "data-preserve-scroll" in template
    assert "window.sessionStorage.setItem(scrollKey" in template
    assert "window.scrollTo(0, Number(savedScroll))" in template


def test_streamer_channel_toggles_preserve_scroll_position() -> None:
    template = (PROJECT_ROOT / "web/templates/channel/features.html").read_text(encoding="utf-8")

    assert "data-preserve-scroll" in template
    assert "window.sessionStorage.setItem(scrollKey" in template
    assert "window.scrollTo(0, Number(savedScroll))" in template


def test_streamer_feature_page_lists_unique_profile_integrations() -> None:
    template = (PROJECT_ROOT / "web/templates/channel/features.html").read_text(encoding="utf-8")

    assert "Unique Features" in template
    assert '"profile_feature"' in template
    assert "League of Legends" in template
    assert "Overwatch" in template


def test_admin_feature_page_lists_unique_profile_integrations() -> None:
    template = (PROJECT_ROOT / "web/templates/admin/channel_details.html").read_text(encoding="utf-8")

    assert "Unique Features" in template
    assert '"profile_feature"' in template
    assert "League of Legends" in template
    assert "Overwatch" in template
    assert "Premium feature" in template
    assert "Enable Premium Access" in template
    assert "/admin/channels/{{ broadcaster.id }}/custom-bot/connect" not in template


def test_admin_channel_chat_is_read_only() -> None:
    template = (PROJECT_ROOT / "web/templates/admin/channel_details.html").read_text(encoding="utf-8")

    assert 'data-stream-url="/admin/channels/{{ broadcaster.id }}/api/chat/stream?view=both"' in template
    assert "live-chat-feed.js" in template
    assert "data-chat-composer" not in template
    assert "data-moderation-url" not in template
    assert "data-pinned-url" not in template


def test_admin_activity_matches_channel_dashboard_feeds() -> None:
    template = (PROJECT_ROOT / "web/templates/admin/channel_details.html").read_text(encoding="utf-8")

    for activity in ("redeems", "checkins", "commands", "mod-actions", "automod"):
        assert f'data-admin-activity-tab="{activity}"' in template
        assert f'data-admin-activity-panel="{activity}"' in template

    assert "api/chat/stream?view=commands" in template
    assert 'class="channel-dashboard-layout admin-channel-dashboard-layout"' in template
    assert 'class="channel-live-layout"' in template
    assert 'class="panel raid-monitor-panel admin-overview-raid-panel"' in template
    assert template.index('class="channel-live-layout"') < template.index("admin-overview-raid-panel")


def test_admin_channel_navigation_has_three_sections() -> None:
    navigation = (PROJECT_ROOT / "web/templates/admin/channel_page_switch.html").read_text(encoding="utf-8")

    assert ">Overview</a>" in navigation
    assert "/features" in navigation
    assert ">Features</a>" in navigation
    assert "/customization" in navigation
    assert ">Customization</a>" in navigation
    assert "channel-page-switch" not in navigation


def test_streamer_dashboard_has_profile_customization_page() -> None:
    layout = (PROJECT_ROOT / "web/templates/channel/layout.html").read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "web/templates/channel/customization.html").read_text(encoding="utf-8")
    template += (PROJECT_ROOT / "web/templates/shared/profile_inputs.html").read_text(encoding="utf-8")
    template += (PROJECT_ROOT / "web/templates/shared/timer_editor.html").read_text(encoding="utf-8")

    assert "/channel/customization" in layout
    assert "Save Changes" in template
    assert "Use Default" in template
    assert "Social links" in template
    assert "Channel default:" in template
    assert "Profile default:" not in template
    assert "Please contact the developer" in template
    assert "data-add-timer" in template
    assert "data-remove-timer" in template
    assert "full-width" in template
    assert "Generate Authorization Link" in template
    assert "/channel/custom-bot/connect" in template
    assert "/channel/custom-bot/disconnect" in template
    assert 'class="button danger" type="submit">Disconnect Account' in template
    assert "custom-bot-actions" in template

    link_template = (PROJECT_ROOT / "web/templates/channel/custom_bot_link.html").read_text(encoding="utf-8")
    result_template = (PROJECT_ROOT / "web/templates/channel/custom_bot_result.html").read_text(encoding="utf-8")

    assert "valid for 15 minutes" in link_template
    assert "Copy Link" in link_template
    assert "another device" in link_template
    assert "Custom Bot Authorization" in result_template


def test_stylesheets_use_deployment_stamp_for_cache_busting() -> None:
    template_paths = (
        "web/templates/admin/layout.html",
        "web/templates/admin/login.html",
        "web/templates/channel/connect.html",
        "web/templates/channel/layout.html",
        "web/templates/public/channel_commands.html",
        "web/templates/public/channel_commands_unavailable.html",
        "web/templates/public/home.html"
    )

    for template_path in template_paths:
        template = (PROJECT_ROOT / template_path).read_text(encoding="utf-8")
        assert "style.css') }}?v={{ deployment_stamp() }}" in template
