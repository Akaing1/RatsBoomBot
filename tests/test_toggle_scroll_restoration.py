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


def test_streamer_dashboard_has_profile_customization_page() -> None:
    layout = (PROJECT_ROOT / "web/templates/channel/layout.html").read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "web/templates/channel/customization.html").read_text(encoding="utf-8")

    assert "/channel/customization" in layout
    assert "Save Changes" in template
    assert "Use Default" in template
    assert "Social links" in template
