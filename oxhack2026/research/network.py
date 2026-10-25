"""HTTPS-only pinned connections, shared quotas, streaming limits and provenance."""

import http.client
import ipaddress
import logging
import re
import socket
import ssl
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from oxhack2026.api.research_v2_schemas import Capture
from oxhack2026.storage.artifacts import FileArtifactStore

logger = logging.getLogger(__name__)
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="research-dns")
_DNS_SLOTS = threading.BoundedSemaphore(8)
NETWORK_SLOTS = threading.BoundedSemaphore(8)


@contextmanager
def network_operation(deadline: float) -> Iterator[None]:
    """Reserve one shared network operation until the absolute deadline.

    Args:
        deadline: Monotonic absolute request deadline.
    Yields:
        Control while one of the eight process-wide network slots is held.
    Raises:
        BudgetExceeded: No slot was available within the remaining time.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not NETWORK_SLOTS.acquire(timeout=remaining):
        raise BudgetExceeded("network_deadline")
    try:
        yield
    finally:
        NETWORK_SLOTS.release()


class CollectionError(Exception):
    """Safe source failure reason, containing no request URL or credentials."""


class BudgetExceeded(CollectionError):
    """A collection request, time, or captured-byte budget was exhausted."""


def normalize_domain(value: str) -> str:
    """Normalize a bare domain or HTTPS URL; reject credentials and unsafe syntax.

    Args:
        value: User supplied domain or company URL.
    Returns:
        Lowercase ASCII hostname without a leading www label.
    Raises:
        ValueError: Input is not a public DNS hostname over HTTPS.
    """
    parsed = urlsplit(value.strip() if "://" in value else f"https://{value.strip()}")
    host = (parsed.hostname or "").rstrip(".").encode("idna").decode().lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or "." not in host
        or any(character.isspace() for character in value)
    ):
        message = "Supply a public domain or HTTPS URL without credentials or query"
        raise ValueError(message)
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        message = "Company identity must use a public DNS hostname"
        raise ValueError(message)
    from pydantic import TypeAdapter

    from oxhack2026.api.research_schemas import Domain

    return TypeAdapter(Domain).validate_python(host.removeprefix("www."))


def public_url(url: str) -> str:
    """Return a credential-free HTTPS URL without query or fragment; reject unsafe
    URLs."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise CollectionError("unsafe_url")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", "", ""))


def public_addresses(host: str, timeout: float = 5) -> tuple[str, ...]:
    """Resolve at connection time; reject answers containing nonpublic addresses.

    Raises:
        CollectionError: DNS fails or includes private, reserved or metadata addresses.
    """
    if not _DNS_SLOTS.acquire(timeout=timeout):
        raise CollectionError("dns_capacity_timeout")
    try:
        pending = _DNS_EXECUTOR.submit(
            socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM
        )
    except RuntimeError as error:
        _DNS_SLOTS.release()
        raise CollectionError("dns_worker_unavailable") from error
    pending.add_done_callback(lambda _future: _DNS_SLOTS.release())
    try:
        answers = pending.result(timeout=timeout)
    except (OSError, TimeoutError) as error:
        raise CollectionError("dns_unavailable") from error
    addresses = tuple(dict.fromkeys(str(answer[4][0]) for answer in answers))
    if not addresses or any(
        not ipaddress.ip_address(address).is_global
        or getattr(ipaddress.ip_address(address), "ipv4_mapped", None) is not None
        for address in addresses
    ):
        raise CollectionError("private_destination_rejected")
    return addresses


def _response_byte_limit(url: str) -> int:
    parsed = urlsplit(url)
    if parsed.hostname == "data.sec.gov" and re.fullmatch(
        r"/api/xbrl/companyfacts/CIK[0-9]{10}\.json", parsed.path
    ):
        return 16777216
    return 4194304


def _read_response(
    response: http.client.HTTPResponse,
    connection: http.client.HTTPSConnection,
    deadline: float,
    byte_limit: int,
) -> bytes:
    chunks = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BudgetExceeded("collection_deadline")
        if connection.sock is not None:
            connection.sock.settimeout(min(15, remaining))
        chunk = response.read1(min(65536, byte_limit + 1 - len(chunks)))
        if not chunk:
            return bytes(chunks)
        chunks.extend(chunk)
        if len(chunks) > byte_limit:
            raise BudgetExceeded("response_size_limit")


def _abort_socket(connection: socket.socket) -> None:
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        logger.debug("Research deadline socket was already closed")


class PinnedTransport(httpx.BaseTransport):
    """Direct TLS transport pinned to validated IPs; no proxy, cookie jar or DNS
    recheck."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Fetch one bounded response; validate DNS at the actual connection
        boundary."""
        public_url(str(request.url))
        host = request.url.host
        timeout_data = request.extensions.get("timeout", {})
        timeout = min(float(timeout_data.get("read", 15) or 15), 15)
        deadline = float(
            request.extensions.get("research_deadline", time.monotonic() + 15)
        )
        address = public_addresses(host, min(5, timeout))[0]
        timeout = min(timeout, deadline - time.monotonic())
        if timeout <= 0:
            raise BudgetExceeded("collection_deadline")
        connection = http.client.HTTPSConnection(host, timeout=timeout)
        timer: threading.Timer | None = None
        try:
            raw_socket = socket.create_connection((address, 443), timeout=timeout)
            try:
                connection.sock = ssl.create_default_context().wrap_socket(
                    raw_socket, server_hostname=host
                )
            except (OSError, ssl.SSLError):
                raw_socket.close()
                raise
            timer = threading.Timer(
                max(0, deadline - time.monotonic()), _abort_socket, (connection.sock,)
            )
            timer.daemon = True
            timer.start()
            connection.request(
                "GET",
                request.url.raw_path.decode("ascii"),
                headers=dict(request.headers.items()),
            )
            response = connection.getresponse()
            deadline = float(
                request.extensions.get("research_deadline", time.monotonic() + 15)
            )
            content = _read_response(
                response, connection, deadline, _response_byte_limit(str(request.url))
            )
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise CollectionError("unexpected_compressed_response")
            # Set-Cookie is intentionally discarded at the transport boundary.
            headers = [
                (key, value)
                for key, value in response.getheaders()
                if key.lower() not in {"set-cookie", "transfer-encoding"}
            ]
            return httpx.Response(response.status, headers=headers, content=content)
        except (OSError, http.client.HTTPException) as error:
            raise CollectionError("network_unavailable") from error
        finally:
            if timer is not None:
                timer.cancel()
            connection.close()


@dataclass
class Quotas:
    """Process-wide request gate; one instance is shared by all v2 jobs.

    Args:
        interval: Minimum per-host spacing, increased for unauthenticated GitHub.
    """

    interval: float = 1.0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _slots: threading.BoundedSemaphore = field(default_factory=lambda: NETWORK_SLOTS)
    _next: dict[str, float] = field(default_factory=dict)
    _github_requests: list[float] = field(default_factory=list)

    def reserve(self, host: str, deadline: float, authenticated: bool = False) -> None:
        """Reserve a host request slot; raise BudgetExceeded if it exceeds the
        deadline."""
        spacing = self.interval
        with self._lock:
            now = time.monotonic()
            if host == "api.github.com":
                self._github_requests = [
                    stamp for stamp in self._github_requests if now - stamp < 3600
                ]
                maximum = 5000 if authenticated else 60
                if len(self._github_requests) >= maximum:
                    raise BudgetExceeded("github_hourly_quota")
                self._github_requests.append(now)
            when = max(now, self._next.get(host, now))
            if when >= deadline:
                raise BudgetExceeded("provider_quota_deadline")
            self._next[host] = when + spacing
        delay = when - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def defer(self, host: str, seconds: float) -> None:
        """Honor rate-limit backoff globally, bounded to one hour."""
        with self._lock:
            self._next[host] = max(
                self._next.get(host, 0), time.monotonic() + min(max(seconds, 1), 3600)
            )


@dataclass
class FetchBudget:
    """Atomic request and captured-byte accounting across independent collectors."""

    max_requests: int
    max_bytes: int
    requests: int = 0
    byte_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def request(self) -> None:
        """Reserve one request or raise BudgetExceeded before network access."""
        with self.lock:
            if self.requests >= self.max_requests:
                raise BudgetExceeded("request_or_time_budget")
            self.requests += 1

    def capture(self, size: int) -> None:
        """Reserve captured bytes atomically; raise BudgetExceeded on overflow."""
        with self.lock:
            if self.byte_count + size > self.max_bytes:
                raise BudgetExceeded("capture_size_limit")
            self.byte_count += size


@dataclass
class Fetcher:
    """Per-job budgets and captures over the shared controlled network boundary.

    Args:
        artifacts: Destination for exact bounded response bytes.
        quotas: Shared process-wide provider limits.
        transport: Injected transport for deterministic tests; direct TLS by default.
        deadline: Monotonic deadline for this job.

    Ordinary responses are bounded to 4 MiB; exact SEC company-facts endpoints
    may return up to 16 MiB. The shared 32 MiB job capture limit still applies.
    """

    artifacts: FileArtifactStore
    quotas: Quotas
    transport: httpx.BaseTransport = field(default_factory=PinnedTransport)
    deadline: float = field(default_factory=lambda: time.monotonic() + 300)
    captures: list[Capture] = field(default_factory=list)
    shared_budget: FetchBudget | None = None
    max_requests: int = 120
    max_bytes: int = 33554432
    requests: int = 0
    byte_count: int = 0

    def _capture(
        self, response: httpx.Response, original: str, safe: str
    ) -> tuple[Capture, bytes]:
        chunks = bytearray()
        byte_limit = _response_byte_limit(original)
        for chunk in response.iter_bytes():
            chunks.extend(chunk)
            if len(chunks) > byte_limit:
                raise BudgetExceeded("response_size_limit")
            if self.byte_count + len(chunks) > self.max_bytes:
                raise BudgetExceeded("capture_size_limit")
            if time.monotonic() > self.deadline:
                raise BudgetExceeded("collection_deadline")
        content = bytes(chunks)
        if self.shared_budget:
            self.shared_budget.capture(len(content))
        self.byte_count += len(content)
        capture = Capture(
            capture_id=uuid4().hex,
            url=original,
            final_url=safe,
            status_code=response.status_code,
            collected_at=datetime.now(UTC),
            artifact=self.artifacts.write(content, "application/octet-stream"),
            content_type=response.headers.get("content-type", "")[:200],
        )
        self.captures.append(capture)
        return capture, content

    def fetch(
        self, url: str, headers: dict[str, str] | None = None
    ) -> tuple[Capture, bytes]:
        """Fetch bounded HTTPS redirects and retain captures, including HTTP denials.

        Raises:
            CollectionError: Unsafe URL, denial, timeout, or provider/network failure.
            BudgetExceeded: Per-job request, response, byte or time limits exceeded.
        """
        original = public_url(url)
        for _ in range(6):
            safe = public_url(url)
            host = urlsplit(url).hostname or ""
            if self.requests >= self.max_requests or time.monotonic() >= self.deadline:
                raise BudgetExceeded("request_or_time_budget")
            self.quotas.reserve(host, self.deadline, bool(headers))
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.quotas._slots.acquire(timeout=remaining):
                raise BudgetExceeded("network_deadline")
            try:
                if self.shared_budget:
                    self.shared_budget.request()
                self.requests += 1
                request_headers = {
                    "User-Agent": "SignalShiftResearch/2",
                    "Accept-Encoding": "identity",
                }
                request_headers.update(headers or {})
                request = httpx.Request(
                    "GET",
                    url,
                    headers=request_headers,
                    extensions={
                        "research_deadline": self.deadline,
                        "timeout": {"read": min(15, remaining)},
                    },
                )
                with closing(self.transport.handle_request(request)) as response:
                    capture, content = self._capture(response, original, safe)
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("location", ""))
                        if urlsplit(url).hostname != host:
                            headers = None
                        continue
                    if response.status_code in {403, 429}:
                        retry = response.headers.get("retry-after", "60")
                        self.quotas.defer(host, float(retry) if retry.isdigit() else 60)
                    if response.is_error:
                        raise CollectionError(f"http_{response.status_code}")
                    return capture, content
            except httpx.HTTPError as error:
                raise CollectionError("network_unavailable") from error
            finally:
                self.quotas._slots.release()
        raise CollectionError("redirect_limit")
