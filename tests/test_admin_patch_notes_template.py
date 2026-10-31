from jinja2 import Environment, FileSystemLoader, select_autoescape

from web.shared.markdown import render_markdown


def render(notes):
    env = Environment(loader=FileSystemLoader('web/templates'), autoescape=select_autoescape())
    env.filters['markdown'] = render_markdown
    env.globals.update(url_for=lambda name, path: '/' + name + path,
                       deployment_stamp=lambda: 'test', app_version='17.0.1')
    return env.get_template('admin/patch_notes.html').render(
        active_page='patch_notes', administrator=None, csrf_token='test-token', notes=notes)


def note(**changes):
    return dict(slug='test-note', title='<Unsafe title>', synopsis='<Summary>',
                body='## Changes\n\n<script>bad()</script>\n\n- **New feature**',
                version=None, published_at=None) | changes


def test_draft_preview_is_sanitized_and_publish_form_keeps_csrf():
    html = render([note()])
    assert '&lt;Unsafe title&gt;' in html
    assert '&lt;Summary&gt;' in html
    assert '<script>' not in html
    assert '<h2>Changes</h2>' in html
    assert '<strong>New feature</strong>' in html
    assert 'action="/admin/patch-notes/test-note/publish"' in html
    publish_form = html.split('action="/admin/patch-notes/test-note/publish"', 1)[1].split('</form>', 1)[0]
    assert 'name="csrf_token" value="test-token"' in publish_form
    assert 'send its Discord announcement if configured?' in html


def test_published_note_links_to_public_page_without_publish_action():
    html = render([note(published_at='2026-10-30', version='17.0.0')])
    assert 'href="/patch-notes/test-note"' in html
    assert 'action="/admin/patch-notes/test-note/publish"' not in html
    assert 'Published 2026-10-30' in html


def test_empty_archive_still_allows_creating_a_draft():
    html = render([])
    assert 'No patch notes yet' in html
    assert 'action="/admin/patch-notes/save"' in html
