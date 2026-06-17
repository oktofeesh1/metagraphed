# metagraphed (Python)

Thin, dependency-free Python client for **metagraphed** — the operational +
integration registry for Bittensor subnets at `https://api.metagraph.sh`.

It mirrors the [npm client](https://www.npmjs.com/package/@jsonbored/metagraphed):
one generic GET helper over the uniform, read-only API surface, returning the
parsed `{ ok, schema_version, data, meta }` envelope. Stdlib only — no transitive
dependencies.

## Install

```bash
pip install metagraphed            # sync client + typed models (stdlib only)
pip install "metagraphed[async]"   # adds the async client (httpx)
```

## Usage

```python
from metagraphed import MetagraphedClient, metagraphed_fetch

client = MetagraphedClient()  # base_url defaults to https://api.metagraph.sh

# List subnets (query params; None values are dropped). The /subnets collection
# nests its rows under data.subnets:
subnets = client.fetch(
    "/api/v1/subnets",
    query={"limit": 10, "sort": "completeness_score", "order": "desc"},
)
print(subnets["data"]["subnets"][0]["name"])

# One subnet by netuid (path params)
detail = client.fetch("/api/v1/subnets/{netuid}", path_params={"netuid": 7})

# Which subnets are buildable? (integration readiness lives in the agent catalog)
catalog = client.fetch("/api/v1/agent-catalog")

# Health of the registry itself:
health = metagraphed_fetch("/api/v1/health")
```

Every response is the standard envelope:

```python
{"ok": True, "schema_version": 1, "data": ..., "meta": {...}}
```

On a network failure or non-2xx response, a `MetagraphedError` is raised (with
`.status` for HTTP errors, and the API error code/message in the message).

### Retries, pagination, and the RPC proxy

```python
from metagraphed import (
    MetagraphedClient,
    metagraphed_paginate,
    metagraphed_rpc,
)

# Opt-in retry/backoff for idempotent GETs (retries 429/5xx + network errors,
# honoring a numeric Retry-After). Disabled by default.
client = MetagraphedClient(retries=3)

# Iterate every page of a list endpoint (follows meta.pagination.next_cursor):
for page in client.paginate("/api/v1/subnets", query={"limit": 100}):
    for subnet in page["data"]["subnets"]:
        print(subnet["netuid"])

# Call the read-only Subtensor RPC proxy and get back the JSON-RPC result:
info = metagraphed_rpc("finney", "system_health")
```

### Collect every row (`fetch_all`)

List endpoints nest rows under `data.<collection>` (named by
`meta.pagination.collection`) and paginate via `meta.pagination.next_cursor`.
`fetch_all` follows the cursor and concatenates the rows for you:

```python
subnets = client.fetch_all("/api/v1/subnets")  # every subnet, across all pages
print(len(subnets), subnets[0]["name"])
```

There are also thin convenience wrappers over the canonical routes —
`client.subnets(...)`, `client.get_subnet(7)`, `client.providers(...)`,
`client.get_provider("synth")`, `client.surfaces(...)`, `client.endpoints(...)`,
`client.health()`, `client.agent_catalog()` — each returning the raw envelope.

### Typed models (optional)

`fetch`/`fetch_all` return plain dicts. For typed attribute access, parse rows
into the dependency-free dataclasses — the **full** payload always stays on
`.raw`, so nothing is lost:

```python
from metagraphed import MetagraphedClient, Subnet

client = MetagraphedClient()
subnets = [Subnet.from_dict(row) for row in client.fetch_all("/api/v1/subnets")]
subnets[0].name           # typed attribute
subnets[0].raw["tempo"]   # anything else, from the raw payload
```

Models: `Subnet`, `Surface`, `Provider`, `Endpoint`, `AgentCatalogEntry` — each
with `.from_dict()` / `.from_list()` and a `.raw` escape hatch.

### Async client (`metagraphed[async]`)

`AsyncMetagraphedClient` mirrors the sync client (`fetch` / `paginate` /
`fetch_all` / `rpc` + the same convenience methods), powered by `httpx`. The sync
path stays dependency-free; importing the async client is what pulls in httpx.

```python
import asyncio
from metagraphed import AsyncMetagraphedClient

async def main():
    async with AsyncMetagraphedClient(retries=2) as client:
        health = await client.health()
        subnets = await client.fetch_all("/api/v1/subnets")
        info = await client.rpc("finney", "system_health")

asyncio.run(main())
```

## Versioning & stability

Tracks the public `/api/v1` contract; changes are additive within v1. See the
backend's [API stability policy](https://github.com/JSONbored/metagraphed/blob/main/docs/api-stability.md).

## License

Apache-2.0 — see [LICENSE](./LICENSE). (The metagraphed backend itself is AGPL-3.0; this client SDK is permissively licensed so you can embed it freely.)
