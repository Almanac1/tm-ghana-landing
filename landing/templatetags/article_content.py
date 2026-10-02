import re
from urllib.parse import urlsplit

from django import template
from django.utils.html import escape, format_html, linebreaks
from django.utils.safestring import mark_safe


register = template.Library()
LINK = re.compile(r"\[([^\[\]\n]+)\]\(([^\s()]+)\)")


def is_link_url(url):
    if "\\" in url or any(ord(character) < 32 for character in url):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme in ("http", "https") and bool(parsed.netloc)
    ) or (url.startswith("/") and not url.startswith("//")) or url.startswith("#")


@register.filter
def article_content(value):
    """Preserve plain-text paragraphs and render only validated Markdown links."""
    parts = []
    position = 0
    for match in LINK.finditer(value):
        parts.append(str(escape(value[position:match.start()])))
        label, url = match.groups()
        if is_link_url(url):
            parts.append(str(format_html('<a href="{}">{}</a>', url, label)))
        else:
            parts.append(str(escape(match.group())))
        position = match.end()
    parts.append(str(escape(value[position:])))
    return mark_safe(linebreaks("".join(parts)))
