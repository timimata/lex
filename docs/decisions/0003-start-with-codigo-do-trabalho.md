# 0003. Start with the Código do Trabalho only

Date: 2026-09-29
Status: accepted; carried out, tenancy added by ADR 0017 (amended 2026-10-08)

## Context

The original scope was labour law, tenancy and IRS. Each brings a different structure: tenancy
spans the Código Civil and the NRAU, and IRS is a separate code with its own rhythm of amendments.
Taking all three at once multiplies the ingestion and benchmark work before anything works end
to end.

## Decision

Phases 1 to 5 cover the Código do Trabalho (approved by Lei n.º 7/2009) alone. Other diplomas
come in Phase 6, once ingestion, benchmark, system and demo work for one.

## Consequences

- The first real numbers arrive sooner.
- ACT's public guidance maps directly onto this corpus, which makes sourcing questions easier.
- Questions that need another diploma (e.g. labour law pointing to the Código Civil) are
  `unanswerable` until Phase 6.

## Amendment, 2026-10-08: tenancy came in Phase 6

As planned here, other diplomas came once the Código do Trabalho worked end to end: the Código
Civil's articles on leases and the NRAU joined the corpus on 2026-10-01
([ADR 0017](0017-tenancy.md)). Questions on them are answerable since then, and `validate` names
any earlier `unanswerable` item that speaks of tenancy for a person to review.
