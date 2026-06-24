"""ADR writer — persists Architecture Decision Records to LiteLLM Memory."""
from __future__ import annotations

from datetime import date as _date
from urllib.parse import quote

import httpx

from .cache import normalize_base_url


def write_adr(
    base_url: str,
    api_key: str,
    project_id: str,
    slug: str,
    content: str,
    date: str = "",
) -> None:
    """Write an ADR to LiteLLM Memory under project:{id}:octowiz:adr:{date}-{slug}.

    Args:
        base_url: LiteLLM Proxy base URL
        api_key: API key for Authorization: Bearer header
        project_id: Project namespace identifier
        slug: Short kebab-case name for this ADR
        content: Full ADR text to store
        date: ISO date string (YYYY-MM-DD); defaults to today
    """
    effective_date = date or str(_date.today())
    key = f"project:{project_id}:octowiz:adr:{effective_date}-{slug}"
    url = f"{normalize_base_url(base_url)}/v1/memory/{quote(key, safe=':')}"
    response = httpx.put(
        url,
        json={"content": content},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
