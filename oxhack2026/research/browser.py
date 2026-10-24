"""Isolated local browser whose HTTP requests are fulfilled by the controlled
fetcher."""

import logging
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Route, sync_playwright

from oxhack2026.api.research_v2_schemas import Capture
from oxhack2026.research.network import CollectionError, Fetcher, public_url

logger = logging.getLogger(__name__)


def browser_available() -> bool:
    """Check local executable presence without launching Chromium or contacting
    vendors."""
    with sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path).is_file()


def render(fetcher: Fetcher, url: str) -> tuple[Capture, bytes]:
    """Render a public page through the controlled fetcher in an isolated context.

    Args:
        fetcher: Same budget and controlled HTTPS transport as ordinary collection.
        url: Public HTTPS navigation destination.
    Returns:
        Retained DOM capture with actual rendering time and exact artifact hash.
    Raises:
        CollectionError: Browser unavailable, network rejected or rendering timed out.
    """
    public_url(url)
    failures: list[str] = []

    def fulfill(route: Route) -> None:
        if route.request.method != "GET" or route.request.resource_type in {
            "image",
            "media",
            "font",
            "websocket",
        }:
            route.abort()
            return
        try:
            capture, content = fetcher.fetch(route.request.url)
            route.fulfill(
                status=capture.status_code,
                body=content,
                headers={"content-type": capture.content_type},
            )
        except CollectionError as error:
            failures.append(str(error))
            route.abort()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                proxy={"server": "http://127.0.0.1:9"},
                args=[
                    "--disable-background-networking",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                ],
            )
            try:
                context = browser.new_context(
                    service_workers="block",
                    accept_downloads=False,
                    permissions=[],
                    storage_state={"cookies": [], "origins": []},
                )
                context.route("**/*", fulfill)
                context.route_web_socket("**/*", lambda websocket: websocket.close())
                page = context.new_page()
                timeout = max(
                    1, min(20000, int((fetcher.deadline - time.monotonic()) * 1000))
                )
                page.goto(url, timeout=timeout, wait_until="networkidle")
                content = page.content().encode()
                if (
                    len(content) > 4194304
                    or fetcher.byte_count + len(content) > 33554432
                ):
                    raise CollectionError("browser_capture_size_limit")
                if failures:
                    raise CollectionError("browser_request_blocked")
                from datetime import UTC, datetime
                from uuid import uuid4

                fetcher.byte_count += len(content)
                capture = Capture(
                    capture_id=uuid4().hex,
                    url=public_url(url),
                    final_url=public_url(page.url),
                    status_code=200,
                    collected_at=datetime.now(UTC),
                    rendered=True,
                    artifact=fetcher.artifacts.write(
                        content, "application/octet-stream"
                    ),
                    content_type="text/html",
                )
                fetcher.captures.append(capture)
                return capture, content
            finally:
                browser.close()
    except PlaywrightError as error:
        logger.error("Local research browser unavailable or navigation failed")  # noqa: TRY400
        raise CollectionError("browser_unavailable_or_timeout") from error
