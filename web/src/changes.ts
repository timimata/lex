// What changed between two versions of an article, readable for a person: line by line (an
// article's numbered paragraphs are its lines), word by word within a line that changed a little,
// and whole lines struck and added when a paragraph was rewritten.

import { diffArrays, diffWords } from "diff";

export type Piece = { text: string; kind: "same" | "added" | "removed" };
export type Line = Piece[];

const REWRITTEN = 0.5; // share of a line's characters changed above which it reads as rewritten

function wordsChanged(before: string, after: string): { pieces: Piece[]; share: number } {
  const parts = diffWords(before, after);
  const changed = parts.filter((p) => p.added || p.removed).reduce((n, p) => n + p.value.length, 0);
  const pieces = parts.map((p): Piece => ({
    text: p.value,
    kind: p.added ? "added" : p.removed ? "removed" : "same",
  }));
  return { pieces, share: changed / Math.max(1, before.length + after.length) };
}

/** A paragraph's own label, "3 -" or "a)", which pairs it with its new wording. */
function label(line: string): string | null {
  const match = line.match(/^\s*(\d+(?:\.º)?\s*-|[a-z]\))/);
  return match ? match[1].replace(/\s+/g, " ") : null;
}

/** Removed lines paired with the added lines that replace them: by paragraph label where both
 * have one, else in order among the unlabelled; what has no partner stands alone. */
function pair(removed: string[], added: string[]): Line[] {
  const lines: Line[] = [];
  const used = new Set<number>();
  const unlabelled = added.map((_, i) => i).filter((i) => label(added[i]) === null);
  for (const old of removed) {
    const mark = label(old);
    const j =
      mark === null
        ? (unlabelled.find((i) => !used.has(i)) ?? -1)
        : added.findIndex((a, i) => !used.has(i) && label(a) === mark);
    if (j < 0) {
      lines.push([{ text: old, kind: "removed" }]);
      continue;
    }
    used.add(j);
    const { pieces, share } = wordsChanged(old, added[j]);
    if (share <= REWRITTEN) lines.push(pieces);
    else lines.push([{ text: old, kind: "removed" }], [{ text: added[j], kind: "added" }]);
  }
  added.forEach((line, i) => {
    if (!used.has(i)) lines.push([{ text: line, kind: "added" }]);
  });
  return lines;
}

export function changes(before: string, after: string): Line[] {
  const lines: Line[] = [];
  const blocks = diffArrays(before.split("\n"), after.split("\n"));
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    const next = blocks[i + 1];
    if (!block.added && !block.removed) {
      lines.push(...block.value.map((text): Line => [{ text, kind: "same" }]));
    } else if (block.removed && next?.added) {
      lines.push(...pair(block.value, next.value));
      i++;
    } else {
      const kind = block.added ? "added" : "removed";
      lines.push(...block.value.map((text): Line => [{ text, kind }]));
    }
  }
  return lines;
}
