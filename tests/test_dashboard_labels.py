from pathlib import Path

from config.version import APP_VERSION
from web.shared.common import templates


def test_current_app_version_is_available_to_templates():
    assert templates.env.globals["app_version"] == APP_VERSION


def test_channel_and_admin_show_version_below_sign_out():
    for name in ("channel", "admin"):
        source = Path(f"web/templates/{name}/layout.html").read_text(encoding="utf-8")
        assert source.index('class="sidebar-logout"') < source.index('class="deployment-stamp sidebar-version"')
        assert 'v{{ app_version }}</p>' in source


def test_category_picker_expands_into_artwork_space_at_all_sizes():
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    start = styles.index(".channel-page-overview .dashboard-video-header:has([data-current-category-art]")
    end = styles.index("@media (prefers-reduced-motion: reduce)", start)
    expansion_rules = styles[start:end]
    assert "@media" not in expansion_rules
    assert "--category-art-space: 60px" in expansion_rules
    assert ".dashboard-video-header > .twitch-channel-field { width: 100%; transition: width" in expansion_rules
    assert ".is-category-selecting .dashboard-video-header > .twitch-channel-field { width: calc(100% + var(--category-art-space, 0px)); }" in expansion_rules
    assert ".twitch-current-category-art { visibility: hidden; pointer-events: none; }" in expansion_rules
    assert ".twitch-game-suggestions { position: absolute;" in styles
    assert "right: 0; left: calc(var(--metadata-label-width) + 1px)" in styles


def test_category_picker_uses_shared_scrollbar_styling():
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    assert ".twitch-game-options,\n.live-chat-feed," in styles
    for part in ("scrollbar", "scrollbar-track", "scrollbar-thumb", "scrollbar-thumb:hover", "scrollbar-button"):
        assert f".twitch-game-options::-webkit-{part}," in styles
    assert "overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }" in styles


def test_shared_overlay_scrollbars_do_not_reserve_space_or_cover_video():
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    assert "scrollbar-width: none !important; scrollbar-gutter: auto !important;" in styles
    assert ".overlay-scrollbars { display: contents; }" in styles
    assert ".overlay-scrollbar { position: fixed;" in styles
    assert ".overlay-scrollbar[hidden] { display: none; }" in styles
    for name in ("channel", "admin"):
        source = Path(f"web/templates/{name}/layout.html").read_text(encoding="utf-8")
        assert "/js/overlay-scrollbars.js" in source
