"""HTML -> plain-text rendering shared by every layer that reads email text.

The critical guarantee: text is split into lines ONLY at block-level element
boundaries (plus <br>). Inline elements (span, a, strong, ...) keep their
text on one line, so a title split across nested <span> elements never
fragments into garbage lines like "still av" / "ailable." — real digest
emails contain deeply nested inline markup (spec: never use arbitrary
surrounding text as a job title).

This is the single source of truth for:
  * the Gmail normalizer (HTML-only emails derive their plain_text here), and
  * BaseJobAlertParser (per-job container blocks in HTML-structured digests).

Inline elements do not introduce separators; a block element always starts on
its own line (a newline is inserted before it if the previous output does not
already end with whitespace). This keeps split-span words intact ("Re"+"mote"
-> "Remote") while keeping block siblings ("Promoted" badge, company line)
distinct lines.
"""

import re

from bs4 import BeautifulSoup, NavigableString
from bs4.element import Comment, PreformattedString

_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
# br handled separately (always a line break).
_NON_CONTENT_TAGS = frozenset(
    {"script", "style", "noscript", "head", "title", "svg", "template"}
)


def _is_invisible_string(node) -> bool:
    """True for string nodes that must NEVER render as visible text.

    Email HTML is full of Outlook/MSO conditional markup:
      <!--[if (gte mso 9)|(IE)]> <table ...><tr><td> ... <![endif]-->
    BeautifulSoup parses that as a Comment node — and Comment IS a
    NavigableString subclass, so without this guard the raw comment text
    ("[if (gte mso 9)|(IE)]", "<table ...>", "<tr>", "<td>", "[endif]")
    leaks into the rendered plain text and can end up stored as a job's
    title/company/posted-date. Doctype/PI/CDATA variants are all
    PreformattedString subclasses. Only plain text may render.
    """
    return isinstance(node, (Comment, PreformattedString))


def render_block_text(root) -> str:
    """Plain text of an HTML element/soup with a newline at every block
    boundary and NO separator inside inline runs (fragments are never minted).

    Whitespace is normalized: runs of spaces collapse, blank lines are removed
    — the parsers' line-per-field segmentation and block pairing both rely on
    this shape.
    """
    chunks: list[str] = []
    _walk(root, chunks)
    text = "".join(chunks)
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _walk(node, chunks: list[str]) -> None:
    for child in getattr(node, "children", []):
        if isinstance(child, NavigableString):
            if _is_invisible_string(child):
                # MSO conditional comments and friends never render —
                # only clean visible text reaches the parsers.
                continue
            value = str(child)
            if value:
                chunks.append(value)
            continue
        name = getattr(child, "name", None)
        if name is None or name in _NON_CONTENT_TAGS:
            continue
        if name == "br":
            chunks.append("\n")
            continue
        if name in _BLOCK_TAGS:
            if chunks and not chunks[-1].endswith(("\n", " ")):
                chunks.append("\n")
            _walk(child, chunks)
            chunks.append("\n")
        else:
            _walk(child, chunks)


def html_to_plain_text(html: str) -> str:
    """Block-aware plain text for an entire HTML email body."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(_NON_CONTENT_TAGS):
        element.decompose()
    # Strip MSO conditional comments etc. soup-wide so nothing downstream
    # (render_block_text, anchor get_text) can ever see raw comment markup.
    for invisible in soup.find_all(string=_is_invisible_string):
        invisible.extract()
    root = soup.body or soup
    return render_block_text(root)
