from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from jinja2 import Environment


class SpriteParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            self.attrs = dict(attrs)


@pytest.mark.parametrize('path', ["/assets/Witch's%20Cat.png", '/assets/Witch%27s%20Cat.png'])
def test_cat_sprite_renders_in_hero_and_collection(path):
    root = Path(__file__).resolve().parents[1]
    source = (root / 'web/templates/public/chatter_profile.html').read_text()
    env = Environment(autoescape=True)
    env.parse(source)
    pet = dict(pet_id='witch_cat', sprite_path=path, frame_count=4, display_name="Witch's Cat")
    sprites = [line.strip() for line in source.splitlines() if '<div class="chatter-pet-sprite' in line]
    assert len(sprites) == 2
    for sprite in sprites:
        rendered = env.from_string(sprite).render(profile={'pet': pet}, pet=pet, deployment_stamp=lambda: 'test')
        parser = SpriteParser()
        parser.feed(rendered)
        assert 'chatter-pet-sprite--cat' in parser.attrs['class'].split()
        style = parser.attrs['style']
        assert "url('/assets/Witch%27s%20Cat.png?v=test')" in style
        url = style.split("url('", 1)[1].split("')", 1)[0]
        assert (root / unquote(urlsplit(url).path).lstrip('/')).is_file()
