"""From the way sources name a diploma to our diploma ids (see bench/README.md)."""

import re

# Checked in order; the first prefix that matches the label decides the kind.
_KINDS = (
    (r"acórdão do tribunal constitucional", "acordao-tc"),
    (r"decreto legislativo regional", "dlr"),
    (r"decreto-lei|dl\b", "dl"),
    (r"(declaração de )?re(c)?tificação|rect\.", "retificacao"),
    (r"lei\b", "lei"),
)
# The year in four digits, or in two in older labels ('DL n.º 47344/66', 'DL n.º 321-B/90').
# Letters after the number name another diploma: DL n.º 321-B/90 is not DL n.º 321/90.
_NUMBER = re.compile(r"n\.º\s*(\d+)(?:-([a-z]{1,2}))?/(\d{4}|\d{2})\b")


def diploma_id(label: str) -> str:
    """'Lei n.º 23/2012, de 25/06' -> 'lei-23-2012', 'Rect. n.º 21/2009' -> 'retificacao-21-2009',
    'DL n.º 47344/66' -> 'dl-47344-1966', 'DL n.º 321-B/90' -> 'dl-321-b-1990'.

    Suffixes after the year, such as the /A of Azorean regional decrees, are dropped."""
    low = " ".join(label.casefold().split())
    number = _NUMBER.search(low)
    if number is None:
        raise ValueError(f"no number/year in diploma label: {label!r}")
    letter, year = number.group(2), number.group(3)
    if len(year) == 2:  # no diploma we read is dated after 2029 in two digits
        year = ("19" if int(year) >= 30 else "20") + year
    for prefix, kind in _KINDS:
        if re.match(prefix, low):
            return f"{kind}-{int(number.group(1))}{f'-{letter}' if letter else ''}-{year}"
    raise ValueError(f"unknown kind of diploma: {label!r}")
