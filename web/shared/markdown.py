import bleach
import markdown
from markupsafe import Markup


ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS | {
    "blockquote",
    "br",
    "code",
    "h1",
    "h2",
    "h3",
    "h4",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "ul"
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}
ALLOWED_PROTOCOLS = {"http", "https", "mailto"}


def render_markdown(body: str) -> Markup:
    rendered = markdown.markdown(body, extensions=("fenced_code", "sane_lists"))
    sanitized = bleach.clean(rendered, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS, strip=True)
    return Markup(sanitized)
