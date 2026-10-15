# 0023. Tracing answers with OpenTelemetry, off by default

Date: 2026-10-10
Status: accepted

## Context

Phase 7 of the roadmap lists tracing (Langfuse). Each answer already records its seconds per
stage, its tokens and its cost (`Answer.timings`, `tokens`; one JSON line per answer in the
platform's log, Phase 8), but nothing shows one answer's steps together, nested, beside the
others: which articles retrieval gave, each model call with its tokens, and the agent's requests.
Langfuse ingests OpenTelemetry over OTLP/HTTP (JSON or protobuf; not gRPC), authenticated with
Basic auth in `OTEL_EXPORTER_OTLP_HEADERS`, at `https://cloud.langfuse.com/api/public/otel` (EU),
`https://us.cloud.langfuse.com/api/public/otel`, or a self-hosted server
([its documentation](https://langfuse.com/integrations/native/opentelemetry), read 2026-10-10).

## Decision

- **OpenTelemetry, not a vendor's SDK**: `lex.tracing` opens spans with the OpenTelemetry API and
  exports them over OTLP/HTTP, so Langfuse or any other OTLP backend receives them by setting the
  standard variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`). The packages are
  an optional extra (`trace`, opentelemetry-sdk and the OTLP/HTTP exporter, 1.45.1).
- **Spans:** `answer` (the API's root: system, date, the question's length, refused, cited),
  `retrieve` (retriever, k, the articles given) and `model` (model id and tokens, for the answer
  model, the agent's every call and the judge).
- **Off unless configured:** without the endpoint, or without the extra, `span` does nothing and
  nothing leaves the machine. `python -m lex.api` configures it; the deployed demo does not install
  the extra, so it sends nothing.
- **No visitor's words by default:** a span carries the question's text only where
  `LEX_TRACE_CONTENT=1`; answers' texts are never put in spans.

## Consequences

- A trace shows one answer's retrieval and model calls nested and timed, in any OTLP backend.
- Tracing a public deployment would send what visitors ask to the backend where
  `LEX_TRACE_CONTENT=1`: ADR 0016's table lists the flow, and the page's privacy note would have
  to say so before that is turned on.
- Revisit if spans need the prompt and the reply (Langfuse's generation view): they hold the
  articles and, on test, test questions, so they would follow ADR 0016's rules for test runs.
