"""Microsoft Business Central API client (OAuth2 client-credentials).

Talks to the standard Business Central REST API (``api/v2.0``) with plain
``httpx`` — no SDK — mirroring how :mod:`app.core.ai` calls the AI REST APIs.

Auth flow (Azure AD client-credentials):
    POST {login_base}/{tenant}/oauth2/v2.0/token
        grant_type=client_credentials
        client_id, client_secret
        scope=https://api.businesscentral.dynamics.com/.default
    -> access_token (bearer), cached until shortly before it expires.

Data flow:
    GET {api_base}/{tenant}/{environment}/api/v2.0/companies
        -> pick the company (by BC_COMPANY name, else the first)
    GET .../companies({companyId})/{entity}
        -> records, following @odata.nextLink for paging.

When credentials are absent (or a live call fails), the client falls back to the
bundled :mod:`app.bc.sample_data` so the rest of the pipeline still works.
"""

from __future__ import annotations

import time
from urllib.parse import quote

import httpx

from app.core.config import settings

from .sample_data import sample_records

# Fields BC adds to every payload that carry no business meaning for retrieval.
_ODATA_NOISE = {"@odata.context", "@odata.etag", "@odata.nextLink"}

# Transient-failure retry policy for live data GETs (see _get_with_retry).
_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF = 1.5  # seconds; multiplied by the attempt number (1.5s, 3s, ...)

# Rows per $top+$skip window (see _fetch_live). Kept small on purpose: slow BC
# OData report pages drop a large response mid-stream, but ~1000-row windows
# return reliably. Trades more requests for far fewer failed/retried fetches.
_PAGE_SIZE = 1000


class BusinessCentralError(RuntimeError):
    """Raised when a live Business Central request cannot be completed."""


class BusinessCentralClient:
    """Fetches records from Business Central, or sample data when unconfigured."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._company_id: str | None = None

    # ------------------------------------------------------------------ #
    # Capability
    # ------------------------------------------------------------------ #

    @property
    def configured(self) -> bool:
        """True when real BC credentials are present (else sample mode)."""
        return settings.bc_configured

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #

    def _access_token(self) -> str:
        """Return a cached bearer token, refreshing it shortly before expiry."""
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        url = f"{settings.bc_login_base}/{settings.bc_tenant_id}/oauth2/v2.0/token"
        try:
            response = httpx.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.bc_client_id,
                    "client_secret": settings.bc_client_secret,
                    "scope": settings.bc_scope,
                },
                timeout=60,
            )
        except httpx.HTTPError as exc:
            raise BusinessCentralError(f"BC token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise BusinessCentralError(
                f"BC token request failed: {response.status_code} {response.text}"
            )

        data = response.json()
        self._token = data.get("access_token")
        if not self._token:
            raise BusinessCentralError("BC token response did not contain an access_token.")
        # ``expires_in`` is seconds from now; default to 1h if BC omits it.
        self._token_expiry = now + float(data.get("expires_in", 3600))
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": "application/json",
        }

    @property
    def _env_root(self) -> str:
        """Root up to the environment: .../v2.0/{tenant}/{environment}."""
        return (
            f"{settings.bc_api_base}/{settings.bc_tenant_id}/{settings.bc_environment}"
        )

    @property
    def _api_root(self) -> str:
        """Standard REST API root: .../{environment}/api/v2.0."""
        return f"{self._env_root}/api/v2.0"

    @property
    def _odata_root(self) -> str:
        """OData V4 web-services root: .../{environment}/ODataV4."""
        return f"{self._env_root}/ODataV4"

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #

    def _company_guid(self) -> str:
        """Resolve and cache the target company's GUID."""
        if self._company_id:
            return self._company_id

        try:
            response = httpx.get(
                f"{self._api_root}/companies", headers=self._headers(), timeout=60
            )
        except httpx.HTTPError as exc:
            raise BusinessCentralError(f"BC companies request failed: {exc}") from exc
        if response.status_code >= 400:
            raise BusinessCentralError(
                f"BC companies request failed: {response.status_code} {response.text}"
            )

        companies = response.json().get("value") or []
        if not companies:
            raise BusinessCentralError("No companies found in this Business Central environment.")

        wanted = settings.bc_company.strip().lower()
        chosen = None
        if wanted:
            chosen = next(
                (c for c in companies if (c.get("name") or c.get("displayName", "")).lower() == wanted),
                None,
            )
        self._company_id = (chosen or companies[0]).get("id")
        if not self._company_id:
            raise BusinessCentralError("Selected Business Central company has no id.")
        return self._company_id

    def _entity_url(self, entity: str) -> str:
        """Build the collection URL for ``entity`` for the configured API style.

        * ``odata`` -> ``.../ODataV4/Company('{name}')/{service}`` (company by
          NAME, ``entity`` is a published web service / page name).
        * ``api``   -> ``.../api/v2.0/companies({guid})/{entity}`` (company by
          GUID, ``entity`` is a standard REST entity).
        """
        if settings.bc_api_style.lower() == "odata":
            if not settings.bc_company:
                raise BusinessCentralError(
                    "BC_COMPANY (company name) is required for OData V4 mode."
                )
            # OData escapes a single quote by doubling it, then URL-encode.
            company = quote(settings.bc_company.replace("'", "''"), safe="")
            return f"{self._odata_root}/Company('{company}')/{entity}"
        return f"{self._api_root}/companies({self._company_guid()})/{entity}"

    def _get_with_retry(self, url: str, params: dict | None, entity: str) -> httpx.Response:
        """GET ``url``, retrying transient network failures with backoff.

        Large OData pulls over chunked transfer occasionally get cut off
        mid-stream (``RemoteProtocolError``: "peer closed connection without
        sending complete message body") or time out. These are transient, so we
        re-attempt a few times before surfacing a :class:`BusinessCentralError`.
        HTTP 4xx/5xx status codes are *not* retried here — the caller inspects
        ``status_code`` and decides.
        """
        attempts = max(1, _RETRY_ATTEMPTS)
        last_exc: httpx.HTTPError | None = None
        for attempt in range(attempts):
            try:
                return httpx.get(url, headers=self._headers(), params=params, timeout=90)
            except (httpx.TransportError, httpx.RemoteProtocolError) as exc:
                # Transient: connection reset, read/connect timeout, incomplete
                # chunked read. Back off and retry unless this was the last try.
                last_exc = exc
                if attempt < attempts - 1:
                    time.sleep(_RETRY_BACKOFF * (attempt + 1))
                    continue
            except httpx.HTTPError as exc:
                # Non-transient client-side error (e.g. malformed URL) — no point
                # retrying; fail fast.
                raise BusinessCentralError(f"BC {entity} request failed: {exc}") from exc
        raise BusinessCentralError(
            f"BC {entity} request failed after {attempts} attempts: {last_exc}"
        ) from last_exc

    def _fetch_live(self, entity: str, max_records: int) -> list[dict]:
        """Fetch up to ``max_records`` records for ``entity`` from live BC.

        Pages with small ``$top`` + ``$skip`` windows of :data:`_PAGE_SIZE` rows.
        Some BC OData report pages (e.g. the *_Excel services) are slow and stream
        a big response unreliably — a single large ``$top`` request drops mid-body
        ("incomplete chunked read"), while a small window returns quickly and
        completely. ``$skip`` advances correctly on these services, so we page
        until a short page signals the end. :meth:`_get_with_retry` still retries
        any individual window that drops, and the ``max_records`` cap bounds the
        loop so it always terminates.
        """
        base_url = self._entity_url(entity)
        is_odata = settings.bc_api_style.lower() == "odata"

        records: list[dict] = []
        while len(records) < max_records:
            top = min(_PAGE_SIZE, max_records - len(records))
            params: dict = {"$top": top, "$skip": len(records)}
            if is_odata and settings.bc_odata_filter:
                params["$filter"] = settings.bc_odata_filter

            response = self._get_with_retry(base_url, params, entity)
            if response.status_code >= 400:
                raise BusinessCentralError(
                    f"BC {entity} request failed: {response.status_code} {response.text}"
                )

            batch = response.json().get("value") or []
            if not batch:
                break  # no more rows
            records.extend(batch)
            if len(batch) < top:
                break  # short page -> end of the data

        return records[:max_records]

    def fetch(
        self, entity: str, max_records: int | None = None
    ) -> tuple[list[dict], str, str | None]:
        """Return ``(records, source, error)`` for ``entity``.

        ``source`` is ``"live"`` when the data came from Business Central and
        ``"sample"`` when it came from the bundled fallback (creds absent or a
        live call failed). ``error`` is ``None`` on success; when a live fetch
        was attempted but failed, it carries the failure message and the caller
        gets sample data so the pipeline still runs. Records are cleaned of pure
        OData metadata keys.
        """
        limit = max_records or settings.bc_max_records

        error: str | None = None
        if self.configured:
            try:
                records = self._fetch_live(entity, limit)
                return [_clean(r) for r in records], "live", None
            except BusinessCentralError as exc:
                # Fall through to sample data rather than break the whole sync,
                # but keep the reason so callers can surface it to the user.
                error = str(exc)

        return [_clean(r) for r in sample_records(entity)][:limit], "sample", error


def _clean(record: dict) -> dict:
    """Drop OData-only metadata keys; keep every real business field."""
    return {k: v for k, v in record.items() if k not in _ODATA_NOISE}


# Shared instance (holds only a cached token/company id, no open connections).
bc_client = BusinessCentralClient()


def get_bc_client() -> BusinessCentralClient:
    """FastAPI dependency / accessor for the shared client."""
    return bc_client
