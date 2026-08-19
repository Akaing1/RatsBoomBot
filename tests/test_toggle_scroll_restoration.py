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
