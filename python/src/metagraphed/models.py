"""Optional typed models for the main metagraphed collections.

Dependency-free (stdlib ``dataclasses``). Each model exposes the common, stable
fields as typed attributes and keeps the **full** server payload on ``.raw`` —
so nothing the API returns is ever lost, and the plain ``dict`` path
(``client.fetch(...)``) stays available for callers who don't want models.

    from metagraphed import MetagraphedClient, Subnet

    client = MetagraphedClient()
    rows = client.fetch_all("/api/v1/subnets")
    subnets = [Subnet.from_dict(row) for row in rows]
    subnets[0].name          # typed attribute
    subnets[0].raw["tempo"]  # anything else, from the raw payload
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Type, TypeVar

_T = TypeVar("_T", bound="_Model")


class _Model:
    """Mixin: build an instance from a server ``dict``, mapping declared fields
    and stashing the complete payload on ``raw`` (unknown keys are preserved
    there, never dropped)."""

    raw: Dict[str, Any]

    @classmethod
    def from_dict(cls: Type[_T], data: Mapping[str, Any]) -> _T:
        names = {f.name for f in dataclasses.fields(cls) if f.name != "raw"}  # type: ignore[arg-type]
        kwargs = {key: value for key, value in data.items() if key in names}
        instance = cls(**kwargs)  # type: ignore[call-arg]
        instance.raw = dict(data)
        return instance

    @classmethod
    def from_list(cls: Type[_T], rows: Any) -> List[_T]:
        """Parse a list of payloads (e.g. a list endpoint's ``data``)."""
        return [cls.from_dict(row) for row in rows or []]


@dataclass
class Subnet(_Model):
    """A subnet row (``/api/v1/subnets`` index or ``/{netuid}`` detail)."""

    netuid: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None
    lifecycle: Optional[str] = None
    description: Optional[str] = None
    website_url: Optional[str] = None
    docs_url: Optional[str] = None
    source_repo: Optional[str] = None
    dashboard_url: Optional[str] = None
    logo_url: Optional[str] = None
    categories: Optional[List[str]] = None
    coverage_level: Optional[str] = None
    curation_level: Optional[str] = None
    subnet_type: Optional[str] = None
    integration_readiness: Optional[int] = None
    surface_count: Optional[int] = None
    gap_count: Optional[int] = None
    participant_count: Optional[int] = None
    symbol: Optional[str] = None
    social: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Surface(_Model):
    """A subnet surface (``/api/v1/surfaces`` or a subnet's ``surfaces[]``)."""

    id: Optional[str] = None
    netuid: Optional[int] = None
    name: Optional[str] = None
    kind: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None
    authority: Optional[str] = None
    classification: Optional[str] = None
    status: Optional[str] = None
    auth_required: Optional[bool] = None
    public_safe: Optional[bool] = None
    subnet_name: Optional[str] = None
    subnet_slug: Optional[str] = None
    schema_url: Optional[str] = None
    source_urls: Optional[List[str]] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Provider(_Model):
    """An operator / team profile (``/api/v1/providers``)."""

    id: Optional[str] = None
    name: Optional[str] = None
    kind: Optional[str] = None
    authority: Optional[str] = None
    website_url: Optional[str] = None
    docs_url: Optional[str] = None
    github_url: Optional[str] = None
    contact_url: Optional[str] = None
    team_url: Optional[str] = None
    logo_url: Optional[str] = None
    social: Optional[Dict[str, Any]] = None
    netuids: Optional[List[int]] = None
    subnet_count: Optional[int] = None
    surface_count: Optional[int] = None
    endpoint_count: Optional[int] = None
    public_notes: Optional[str] = None
    cluster_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Endpoint(_Model):
    """A callable endpoint resource (``/api/v1/endpoints``)."""

    id: Optional[str] = None
    netuid: Optional[int] = None
    kind: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None
    operator: Optional[str] = None
    network: Optional[str] = None
    layer: Optional[str] = None
    status: Optional[str] = None
    classification: Optional[str] = None
    auth_required: Optional[bool] = None
    public_safe: Optional[bool] = None
    pool_eligible: Optional[bool] = None
    score: Optional[int] = None
    latency_ms: Optional[int] = None
    latest_block: Optional[int] = None
    last_checked: Optional[str] = None
    last_ok: Optional[str] = None
    subnet_name: Optional[str] = None
    subnet_slug: Optional[str] = None
    surface_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class AgentCatalogEntry(_Model):
    """An agent-catalog entry (``/api/v1/agent-catalog``). Thin by design — the
    catalog shape evolves, so use ``.raw`` for fields beyond the basics."""

    netuid: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


__all__ = [
    "Subnet",
    "Surface",
    "Provider",
    "Endpoint",
    "AgentCatalogEntry",
]
