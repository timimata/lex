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
_NUMBER = re.compile(r"n\.º\s*(\d+)(?:-[a-z])?/(\d{4})")


def diploma_id(label: str) -> str:
    """'Lei n.º 23/2012, de 25/06' -> 'lei-23-2012', 'Rect. n.º 21/2009' -> 'retificacao-21-2009'.

    Suffixes such as the /A of Azorean regional decrees are dropped."""
    low = " ".join(label.casefold().split())
    number = _NUMBER.search(low)
    if number is None:
        raise ValueError(f"no number/year in diploma label: {label!r}")
    for prefix, kind in _KINDS:
        if re.match(prefix, low):
            return f"{kind}-{int(number.group(1))}-{number.group(2)}"
    raise ValueError(f"unknown kind of diploma: {label!r}")
