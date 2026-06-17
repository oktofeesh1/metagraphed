"""metagraphed — thin Python client for the Bittensor subnet registry API.

The sync client (``MetagraphedClient`` + ``metagraphed_*`` functions) and the
typed models are dependency-free. ``AsyncMetagraphedClient`` is imported lazily
and needs the optional ``httpx`` dependency: ``pip install metagraphed[async]``.
"""

from typing import Any

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    MetagraphedClient,
    MetagraphedError,
    __version__,
    metagraphed_fetch,
    metagraphed_fetch_all,
    metagraphed_paginate,
    metagraphed_rpc,
)
from .models import (
    AgentCatalogEntry,
    Endpoint,
    Provider,
    Subnet,
    Surface,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_USER_AGENT",
    "MetagraphedClient",
    "MetagraphedError",
    "metagraphed_fetch",
    "metagraphed_fetch_all",
    "metagraphed_paginate",
    "metagraphed_rpc",
    "Subnet",
    "Surface",
    "Provider",
    "Endpoint",
    "AgentCatalogEntry",
    # "AsyncMetagraphedClient" is intentionally NOT in __all__ so `import *`
    # stays zero-dep; import it explicitly (it pulls in httpx via [async]).
    "__version__",
]

_LAZY = {"AsyncMetagraphedClient"}


def __getattr__(name: str) -> Any:
    # PEP 562: keep httpx off the import path until the async client is actually
    # requested, so the sync surface never requires the [async] extra.
    if name in _LAZY:
        from . import async_client

        return getattr(async_client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
