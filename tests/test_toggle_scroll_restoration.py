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


def test_streamer_dashboard_has_profile_customization_page() -> None:
    layout = (PROJECT_ROOT / "web/templates/channel/layout.html").read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "web/templates/channel/customization.html").read_text(encoding="utf-8")

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
    assert "Connect Custom Bot Account" in template
    assert "/channel/custom-bot/connect" in template
    assert "/channel/custom-bot/disconnect" in template


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
