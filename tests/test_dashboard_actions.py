from html.parser import HTMLParser
from pathlib import Path


class PlaceholderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "button" and attrs.get("class") == "dashboard-action-placeholder":
            self.current = {"attrs": attrs, "text": ""}

    def handle_data(self, text):
        if self.current is not None:
            self.current["text"] += text

    def handle_endtag(self, tag):
        if tag == "button" and self.current is not None:
            self.buttons.append(self.current)
            self.current = None


def test_seven_dashboard_actions_are_ordered_and_available_overlays_are_enabled():
    parser = PlaceholderParser()
    parser.feed(Path("web/templates/channel/dashboard.html").read_text(encoding="utf-8"))
    assert [button["text"] for button in parser.buttons] == [
        "Polls", "Predictions", "Raid browser", "Stream Together", "Shouts", "Whispers", "Points redeems"]
    for button in parser.buttons:
        assert button["attrs"]["type"] == "button"
        if button["text"] == "Raid browser":
            assert "disabled" not in button["attrs"]
            assert "data-raid-browser-open" in button["attrs"]
            assert button["attrs"]["aria-haspopup"] == "dialog"
            continue
        if button["text"] in {"Polls", "Predictions"}:
            assert "disabled" not in button["attrs"]
            assert button["attrs"]["data-engagement-open"] == button["text"].lower()
            assert button["attrs"]["aria-haspopup"] == "dialog"
            assert button["attrs"]["aria-controls"] == "dashboard-engagement"
            continue
        assert "disabled" in button["attrs"]
        assert "coming soon" in button["attrs"]["title"]
        assert not any(key.startswith("data-") for key in button["attrs"])


def test_unavailable_actions_are_visually_disabled():
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    disabled = styles.split(".dashboard-action-placeholder:disabled {", 1)[1].split("}", 1)[0]
    assert "opacity: .35" in disabled
    assert "border-style: dashed" in disabled
    assert "background: transparent" in disabled
    assert "cursor: not-allowed" in disabled


def test_predictions_uses_crystal_ball_with_a_legible_question_dot():
    template = Path("web/templates/channel/dashboard.html").read_text(encoding="utf-8")
    button = template.split('title="Predictions"', 1)[1].split('</button>', 1)[0]
    assert '<circle cx="12" cy="10" r="8"/>' in button
    assert 'M9.5 8a2.5 2.5' in button
    assert '<circle cx="12" cy="14" r="1.1" fill="currentColor" stroke="none"/>' in button


def test_wide_feeds_have_a_single_icon_column_to_the_right():
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    assert '"player queue chat" "lower lower chat"' in styles
    assert '"stats stats" "player queue" "lower lower" "chat chat"' in styles
    lower = styles.split(".dashboard-lower-panels {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: minmax(0,1fr) 44px" in lower
    assert 'grid-template-areas: "activities actions"' in lower
    assert '"activities activities"' not in styles
    rule = styles.split(".dashboard-actions-panel {", 1)[1].split("}", 1)[0]
    assert "grid-area: actions" in rule
    assert "grid-template-columns: minmax(0,1fr)" in rule
    assert "grid-template-rows: repeat(7,minmax(0,1fr))" in rule


def test_mobile_actions_sit_under_queue_in_the_queue_card():
    script = Path("web/static/js/dashboard-carousel.js").read_text(encoding="utf-8")
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    assert 'selectors: [".dashboard-ads-panel", "[data-viewer-queue-panel]", ".dashboard-actions-panel"]' in script
    assert 'slide.setAttribute("aria-label", `${cards[index].name}, ${index + 1} of ${cards.length}`)' in script
    assert ".dashboard-carousel-slide > .dashboard-actions-panel { height: auto; min-height: 0; flex: 0 0 auto;" in styles


def test_actions_are_compact_without_a_surrounding_panel():
    template = Path("web/templates/channel/dashboard.html").read_text(encoding="utf-8")
    styles = Path("web/static/css/style.css").read_text(encoding="utf-8")
    assert 'class="dashboard-actions-panel"' in template
    assert 'class="panel dashboard-actions-panel"' not in template
    rule = styles.split(".dashboard-actions-panel {", 1)[1].split("}", 1)[0]
    assert "gap: 8px" in rule
    assert "flex: 0 0 auto" in rule
    button = styles.split("\n.dashboard-action-placeholder {", 1)[1].split("}", 1)[0]
    assert "border-radius: 50%" in button
    assert "aspect-ratio: 1" in button
    assert "max-width: 44px" in button
    assert "padding: 8px" in button
    assert 'class="dashboard-lower-panels"' in template
    assert template.index('class="dashboard-activity-grid"') < template.index('class="dashboard-actions-panel"') < template.index('class="channel-dashboard-side viewer-queue-column"')
    actions = template.split('class="dashboard-actions-panel"', 1)[1].split('</section>', 1)[0]
    assert actions.count('<svg viewBox="0 0 24 24" aria-hidden="true">') == 7
    assert actions.count('<span class="sr-only">') == 7
    parser = PlaceholderParser()
    parser.feed(actions)
    # The section opening was removed, but every icon button retains its name.
    assert all(button["attrs"].get("aria-label") for button in parser.buttons)
