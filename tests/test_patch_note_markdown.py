from web.shared.markdown import render_markdown


def test_render_markdown_supports_patch_note_formatting() -> None:
    rendered = str(render_markdown("## Weapons\n\n- **Sword**\n- [Guide](https://ratsboombot.com/raid/test)"))

    assert "<h2>Weapons</h2>" in rendered
    assert "<li><strong>Sword</strong></li>" in rendered
    assert '<a href="https://ratsboombot.com/raid/test">Guide</a>' in rendered


def test_render_markdown_removes_unsafe_html_and_urls() -> None:
    rendered = str(render_markdown('<script>alert("x")</script><img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))'))

    assert "<script" not in rendered
    assert "<img" not in rendered
    assert "javascript:" not in rendered
