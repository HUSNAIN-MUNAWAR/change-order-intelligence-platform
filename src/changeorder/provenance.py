"""Map normalized lines back to exact page-local character spans."""

from dataclasses import dataclass

from .normalization import clean_line
from .schemas import Evidence, PageText, Source


@dataclass(frozen=True)
class Line:
    number: int
    start: int
    end: int
    raw: str
    clean: str


def lines(page: PageText) -> list[Line]:
    result = []
    offset = 0
    for number, raw in enumerate(page.raw_text.splitlines(keepends=True), 1):
        result.append(Line(number, offset, offset + len(raw), raw, clean_line(raw)))
        offset += len(raw)
    return result


def text_origin_for_span(page: PageText, start: int, end: int) -> str:
    """Return the origin for an evidence span, including mixed pages."""
    origins = {
        origin for left, right, origin in page._origin_ranges if start < right and end > left
    }
    if len(origins) == 1:
        return next(iter(origins))
    return page.text_origin


def evidence(source: Source, page: PageText, first: Line, last: Line | None = None) -> Evidence:
    last = last or first
    return Evidence(
        source=source.identifier,
        page=page.page,
        line_start=first.number,
        line_end=last.number,
        char_start=first.start,
        char_end=last.end,
        text=page.raw_text[first.start : last.end],
        text_origin=text_origin_for_span(page, first.start, last.end),
    )


def locate_quote(source: Source, page_number: int | None, quote: str) -> Evidence | None:
    """Quotes must exist verbatim and be unique on the claimed page/source."""
    found = []
    if not quote.strip():
        return None
    for page in source.pages:
        if page.page != page_number:
            continue
        start = page.raw_text.find(quote)
        if start < 0 or page.raw_text.find(quote, start + 1) >= 0:
            continue
        found.append(
            Evidence(
                source=source.identifier,
                page=page.page,
                line_start=page.raw_text[:start].count("\n") + 1,
                line_end=page.raw_text[: start + len(quote) - 1].count("\n") + 1,
                char_start=start,
                char_end=start + len(quote),
                text=quote,
                text_origin=text_origin_for_span(page, start, start + len(quote)),
            )
        )
    return found[0] if len(found) == 1 else None
