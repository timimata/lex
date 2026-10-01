# The public demo (ADR 0013): Postgres with pg_search and pgvector, the API and the web page in
# one container, for a Hugging Face Docker Space. Built from the folder space/assemble.py writes.

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# The store's image (ADR 0006): Debian 13, Postgres 18, pg_search, pgvector, Python 3.13.
FROM paradedb/paradedb:0.25.11-pg18
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/*
# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/lib/postgresql/18/bin:$PATH \
    HF_HOME=/opt/hf \
    PYTHONUNBUFFERED=1
# The CPU build of the pinned torch: the default Linux wheel brings GPU libraries a Space lacks.
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
WORKDIR /app
# Layers ordered by how often they change: dependencies (pyproject), the model (its pinned
# revision), then the code, so a code change neither reinstalls nor downloads anything.
COPY pyproject.toml README.md ./
RUN mkdir -p src/lex && touch src/lex/__init__.py \
    && pip install --no-cache-dir ".[dense,llm,api]" && pip uninstall -y lex
# BGE-M3 at the revision dense.py pins (ADR 0007), fetched at build so the Space starts without it.
COPY src/lex/retrieval/dense.py /tmp/dense.py
RUN python -c "import re; from sentence_transformers import SentenceTransformer; \
src = open('/tmp/dense.py').read(); \
name = re.search(r'BGE_M3 = \"([^\"]+)\"', src)[1]; \
rev = re.search(r'BGE_M3_REVISION = \"([0-9a-f]+)\"', src)[1]; \
SentenceTransformer(name, revision=rev, device='cpu')"
COPY src/ src/
RUN pip install --no-cache-dir --no-deps . \
    && HF_HUB_OFFLINE=1 python -c "from lex.retrieval.dense import BgeM3; BgeM3()"
COPY data/ data/
COPY results/ results/
COPY --from=web /web/dist web/
COPY start.sh ./
RUN chown -R user /app /opt/hf
USER user
# The model is in the image: the Space never downloads one.
ENV DATABASE_URL=postgresql://lex@127.0.0.1:5432/lex HF_HUB_OFFLINE=1
EXPOSE 7860
CMD ["sh", "/app/start.sh"]
