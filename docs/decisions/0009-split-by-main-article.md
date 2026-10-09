# 0009. Split by main article, not by item id

Date: 2026-09-30
Status: accepted (replaces the split rule of Phase 0); amended 2026-10-08 (groups by link)

## Context

Until now an item's split was a hash of its id. That keeps anyone from choosing splits, but it
ignores what items are about. The Phase 2 double check (items across splits citing the same
articles, then read on the dev side) found dev items whose answers contain a test item's answer:

- a dev item asking what one paragraph of an article says answered a test item on the hours of
  training a year;
- a dev item asking what an article says contained the answer to a test item on whether the
  employer may contact a worker who is resting, and a second dev item overlapped it too.

(Until 2026-10-08 these lines named the items and their articles; a test item's id beside its
article tells which article answers it, so they no longer do: ADR 0016's leak scan now refuses
it.)

A system tuned on dev would then have seen test answers. No system had been tuned yet: the two
baselines do not learn from dev, and their test numbers do not depend on the split rule's
reasoning, only on which items fall where.

## Decision

- An item's group is its main article, the first entry of `must_cite` (`lei-7-2009/131`), or
  its id if it cites nothing. The split is a hash of the group, so items about the same main
  article always share a split, and still nobody chooses it.
- The benchmark was re-split once under this rule: 46 dev, 54 test, 45 items moved. Review
  sheets were updated so no test item appears in one with content.
- The test results measured under the id-based split move to `results/test/superseded/`, and
  both baselines are measured again on the new test split.

## Consequences

- Fewer paraphrase leaks between splits. Items that share a secondary article can still land
  in different splits; the main article is where the answer lives in almost every item.
- Groups make the split lumpier: the largest groups have five items (articles 131.º and 251.º).
- Writing an item now means choosing its main article carefully, as the first `must_cite`.
- The Phase 0 rule "the split is a hash of the item id" is replaced; the principle (no one
  picks, and a split never changes afterwards) stays.

## Amendment, 2026-10-08: a group takes in the items linked to it

The main article left two ways for a dev item to give away a test answer: an item that must cite
another's main article (it is about that article too), and two items drawn from one ACT FAQ
entry, one about the present and one, temporal, about an earlier date. `validate` now lists every
dev and test pair that shares a source page or a `must_cite` article, by id and kind of link only.
On benchmark v3: 45 pairs. 14 of them share an article that is one item's main article, which
puts 13 test items in a group with dev items; 3 share secondary articles only; 28 share only a
page that holds many questions (an ACT guide, the DGAJ's page on eviction); none shares a FAQ
entry.

Decision:

- An item's group is its main article plus every item linked to it: one whose main article it
  must cite, or that must cite its main article, or that comes from the same FAQ entry, joined
  transitively (`lex.bench.splits.groups`). Sharing a secondary article or a page of many
  questions links nothing; those pairs stay listed for a person to read on the dev side.
- A group is in dev if any of its items' main articles hashes to dev, and in test otherwise.
  Nobody chooses, and a group that spans the splits goes to dev, never the reverse: dev is
  public on Hugging Face, so a dev item can never become a test item.
- `assign` puts an incoming item in the split of the group it joins, and refuses one that links
  groups already in both splits.
- The 13 test items move to dev once, as benchmark v4 (test 96, dev 105), at Phase 10's
  milestone (ROADMAP), with the test runs the move forces: `python -m lex.bench resplit`. Until
  then `validate` lists them as waiting, not as a fault; after it, a test item in a group with
  dev items is a fault again.

Consequences:

- Test loses 13 items, 12% of it, to a rule that reads only what items cite and where they come
  from. The secondary-article and shared-page pairs are not moved: a page of many questions, or
  an article cited beside the main one, is the weaker sign, and moving them would cost a further
  12 test items on no evidence that their answers overlap.
