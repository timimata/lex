# 0009. Split by main article, not by item id

Date: 2026-09-30
Status: accepted (replaces the split rule of Phase 0)

## Context

Until now an item's split was a hash of its id. That keeps anyone from choosing splits, but it
ignores what items are about. The Phase 2 double check (items across splits citing the same
articles, then read on the dev side) found dev items whose answers contain a test item's answer:

- ct-0017 (dev, "what does article 131.º, n.º 2 say?") answers ct-0016 (test, "how many hours
  of training a year?");
- ct-0014 (dev, "what does article 199.º-A say?") contains the answer to ct-0011 (test, "may
  the employer contact me while I am resting?"), and ct-0012 (dev) overlaps it too.

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
