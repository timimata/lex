"""The store in memory: every article version read from versions.jsonl, for the serverless demo,
which has no Postgres (ADR 0014). It answers the same questions as lex.store.db, and
tests/test_memory.py checks that it answers them the same way.
"""

import datetime as dt
import hashlib
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from lex.store.models import ArticleVersion

# Words too common to tell articles apart.
_STOPWORDS = frozenset(
    {
        "que",
        "para",
        "com",
        "por",
        "uma",
        "uns",
        "umas",
        "dos",
        "das",
        "nos",
        "nas",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "sem",
        "sob",
        "sobre",
        "entre",
        "como",
        "mais",
        "menos",
        "quando",
        "onde",
        "qual",
        "quais",
        "seu",
        "sua",
        "seus",
        "suas",
        "este",
        "esta",
        "isto",
        "esse",
        "essa",
        "isso",
    }
)


def _plain(word: str) -> str:
    plain = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in plain if not unicodedata.combining(c))


def excerpt(text: str, query: str, width: int = 220) -> tuple[str, list[tuple[int, int]]]:
    """The line of `text` that holds most of the query's words, cut to about `width` characters
    around the first, and where in it each of those words is: what a word search shows under a
    hit, so the visitor sees why it matched."""
    wanted = {w for w in _words(query) if len(w) > 2 and w not in _STOPWORDS}
    best: tuple[int, str, list[tuple[int, int]]] = (0, "", [])
    for line in text.splitlines():
        spans = [
            (m.start(), m.end()) for m in re.finditer(r"\w+", line) if _plain(m.group()) in wanted
        ]
        found = len({_plain(line[a:b]) for a, b in spans})
        if found > best[0]:
            best = (found, line, spans)
    found, line, spans = best
    if not found:
        return "", []
    start = 0 if len(line) <= width else max(0, spans[0][0] - width // 4)
    if start:
        start = line.rfind(" ", 0, start) + 1
    end = min(len(line), start + width)
    if end < len(line):
        end = line.rfind(" ", start, end) if " " in line[start:end] else end
    cut = ("…" if start else "") + line[start:end].strip() + ("…" if end < len(line) else "")
    shift = (1 if start else 0) - start - (len(line[start:end]) - len(line[start:end].lstrip()))
    marks = [(a + shift, b + shift) for a, b in spans if a >= start and b <= end]
    return cut, marks


def _words(text: str) -> list[str]:
    """Lower-case words without accents: 'Férias' and 'ferias' are the same word."""
    plain = unicodedata.normalize("NFD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", plain)


def corpus_files(processed: Path) -> list[Path]:
    """Every diploma's ingestion output, processed/<code>/versions.jsonl, in folder order."""
    return sorted(processed.glob("*/versions.jsonl"))


# "(Revogado.)", "(Revogado pela Lei n.º 23/2012...)": a version that only records a revocation.
_REVOKED = re.compile(r"^\(?\s*revogad[oa]", re.IGNORECASE)


def _order(article: str) -> tuple[int, str]:
    """'199-A' after '199', before '200'."""
    number, _, suffix = article.partition("-")
    return int(number), suffix


class Corpus:
    def __init__(self, versions: list[ArticleVersion]) -> None:
        self.versions = versions  # in file order, which vectors files follow
        self.by_article: dict[tuple[str, str], list[ArticleVersion]] = defaultdict(list)
        for v in versions:
            self.by_article[(v.diploma, v.article)].append(v)
        for history in self.by_article.values():
            history.sort(key=lambda v: v.valid_from)

    @classmethod
    def load(cls, *paths: Path) -> "Corpus":
        """Every version in the given versions.jsonl files, in their order."""
        versions = []
        for path in paths:
            lines = path.read_text(encoding="utf-8").splitlines()
            versions += [ArticleVersion.model_validate_json(line) for line in lines if line]
        return cls(versions)

    def article_at(self, diploma: str, article: str, as_of: dt.date) -> ArticleVersion | None:
        """The version of an article in force on `as_of`, or None if there was none that day."""
        return next(
            (v for v in self.by_article.get((diploma, article), []) if v.in_force_on(as_of)), None
        )

    def changes(
        self, diploma: str, since: dt.date, until: dt.date
    ) -> list[tuple[ArticleVersion, str]]:
        """Every version of the diploma's articles that came into force after `since` and by
        `until`, with what it did: "original" (the diploma's own first text), "added" (an
        article that did not exist), "revoked" or "changed". By date, then article."""
        found = []
        for (d, _), history in self.by_article.items():
            if d != diploma:
                continue
            for i, v in enumerate(history):
                if not since < v.valid_from <= until:
                    continue
                if _REVOKED.match(v.text.strip()):
                    kind = "revoked"
                elif i == 0:
                    kind = "original" if v.introduced_by == diploma else "added"
                else:
                    kind = "changed"
                found.append((v, kind))
        return sorted(
            found, key=lambda f: (f[0].valid_from, f[0].introduced_by, _order(f[0].article))
        )

    def versions_of(self, diploma: str, article: str) -> list[ArticleVersion]:
        """Every version of an article, oldest first."""
        return list(self.by_article.get((diploma, article), []))

    def search_words(self, query: str, as_of: dt.date, k: int = 20) -> list[ArticleVersion]:
        """Articles in force on `as_of` whose heading or text contain the query's words, for a
        person browsing the code (no model, no quota): each word found in the heading counts
        three, in the text one; ties go to the lower article number. Accents and case do not
        matter, and short words ("de", "da") are left out."""
        words = [w for w in _words(query) if len(w) > 2 and w not in _STOPWORDS]
        if not words:
            return []
        scored = []
        for v in self.versions:
            if not v.in_force_on(as_of):
                continue
            heading, text = set(_words(v.heading)), set(_words(v.text))
            score = sum(3 * (w in heading) + (w in text) for w in dict.fromkeys(words))
            if score:
                scored.append((-score, _order(v.article), v))
        return [v for _, _, v in sorted(scored, key=lambda s: (s[0], s[1]))[:k]]

    def fingerprint(self) -> str:
        """A hash of every version's identity, dates and text, as db.fingerprint's purpose."""
        parts = sorted(
            "|".join([v.diploma, v.article, str(v.valid_from), str(v.valid_to or ""), v.text])
            for v in self.versions
        )
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()
