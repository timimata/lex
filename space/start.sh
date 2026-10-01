#!/bin/sh
# Starts Postgres inside the container, fills it with the article versions and their
# embeddings, then serves the demo (ADR 0013). Nothing persists: every start rebuilds the store.
set -eu

export PGDATA=/tmp/pgdata
initdb -D "$PGDATA" -U lex --auth=trust --encoding=UTF8 --locale=C.UTF-8 > /dev/null
pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -k /tmp" -l /tmp/postgres.log -w start
createdb -h 127.0.0.1 -U lex lex
# As the ParadeDB image's own bootstrap does, which this container does not run.
psql -h 127.0.0.1 -U lex -d lex -q -c "ALTER DATABASE lex SET search_path TO public, paradedb;"

python -m lex.store load --versions data/versions.jsonl
python -m lex.store load-embeddings data/embeddings.jsonl
exec python -m lex.api --demo --host 0.0.0.0 --port 7860 --static web --results results
