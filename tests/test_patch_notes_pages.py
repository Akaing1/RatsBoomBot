from types import SimpleNamespace

import pytest
from fastapi import Request

from web.shared.common import templates
from web.shared.markdown import render_markdown


def context():
    return dict(request=Request({'type': 'http', 'headers': []}),
                url_for=lambda name, path: ('/assets' if name == 'assets' else '/static') + path,
                deployment_stamp=lambda: 'test')


def note(slug='update'):
    return SimpleNamespace(slug=slug, version='16.1.25', published_at='2026-10-29 12:00:00',
                           title='A community update', synopsis='**New tools** for your stream.')


@pytest.mark.parametrize('count', [0, 1, 3])
def test_release_archive_handles_empty_and_published_history(count):
    html = templates.env.get_template('public/patch_notes.html').render(**context(), patch_notes=[note(str(i)) for i in range(count)])
    assert 'href="/me"' in html
    assert html.count('class="release-featured"') == min(1, count)
    assert html.count('class="release-card"') == max(0, count - 1)
    assert ('No published updates yet' in html) == (count == 0)
    assert '2026-10-29 12:00:00' not in html


def test_release_article_has_shared_navigation_and_safe_markdown():
    html = templates.env.get_template('public/patch_note.html').render(**context(), note=note(), body_html=render_markdown('## Pets\n\n<script>bad()</script>\n\nA new collection.'))
    assert '<title>A community update | RatsBoomBot Patch Notes</title>' in html
    assert 'data-release-outline hidden' in html
    assert 'href="/patch-notes"' in html
    assert '<script>bad()' not in html
    assert '<h2>Pets</h2>' in html
