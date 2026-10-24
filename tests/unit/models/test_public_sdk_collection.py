"""Public collectors mock HTTP, subprocesses and files rather than hitting providers."""

from hashlib import sha256
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import orjson
import pytest

from tools.collect_public_sdk_data import (
    Capture,
    Subject,
    capture,
    collect_subject,
    main,
)


def test_capture_reuses_verified_cache_and_rejects_corruption() -> None:
    """A matching URL and byte digest are required before cached reuse."""
    metadata = Capture(
        url="https://example.org/data", sha256=sha256(b"raw").hexdigest(), byte_size=3
    )
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(
            Path,
            "read_bytes",
            side_effect=[b"raw", metadata.model_dump_json().encode()],
        ),
    ):
        assert capture(Path("mock"), metadata.url) == b"raw"
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(
            Path,
            "read_bytes",
            side_effect=[b"bad", metadata.model_dump_json().encode()],
        ),
        pytest.raises(ValueError, match="integrity"),
    ):
        capture(Path("mock"), metadata.url)


def test_capture_retains_new_http_bytes_and_requires_managed_client() -> None:
    """No implicit connection or unverified successful capture is invented."""
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = httpx.Response(
        200, content=b"raw", request=httpx.Request("GET", "https://example.org/data")
    )
    with (
        patch.object(Path, "exists", return_value=False),
        patch.object(Path, "mkdir"),
        patch.object(Path, "write_bytes") as write,
        patch.object(Path, "write_text") as metadata,
    ):
        assert (
            capture(Path("mock"), "https://example.org/data", client=client) == b"raw"
        )
        with pytest.raises(ValueError, match="managed"):
            capture(Path("missing"), "https://example.org/data")
    write.assert_called_once_with(b"raw")
    assert Capture.model_validate_json(metadata.call_args.args[0]).byte_size == 3


def test_collection_requires_actual_end_of_release_pagination() -> None:
    """An old timestamp in a full page cannot establish complete release history."""
    subject = Subject(subject_id="mock", package="@mock/sdk", segment="data")
    responses = [
        orjson.dumps({"repository": {"url": "git+https://github.com/mock/sdk.git"}}),
        *(b"{}" for _ in range(5)),
        orjson.dumps([{"published_at": "2020-01-01"}] * 100),
        b"[]",
    ]
    with (
        patch(
            "tools.collect_public_sdk_data.capture", side_effect=responses
        ) as download,
        patch.object(Path, "mkdir"),
        patch.object(Path, "write_bytes") as write,
    ):
        collect_subject(subject, Path("mock"), "mock-gh", MagicMock(spec=httpx.Client))

    assert download.call_count == 8
    assert orjson.loads(write.call_args.args[0])["release_pagination_complete"] is True


def test_collection_failure_is_logged_and_retained(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unavailable public data stays an error rather than an observed zero."""
    with (
        patch(
            "tools.collect_public_sdk_data.capture",
            side_effect=ValueError("invalid capture"),
        ),
        patch.object(Path, "mkdir"),
        patch.object(Path, "write_bytes") as write,
    ):
        collect_subject(
            Subject(subject_id="mock", package="mock", segment="data"),
            Path("mock"),
            "mock-gh",
            MagicMock(spec=httpx.Client),
        )

    assert orjson.loads(write.call_args.args[0])["errors"] == ["ValueError"]
    assert "Public SDK capture failed" in caplog.text


def test_main_submits_declared_cohort_with_bounded_workers() -> None:
    """CLI delegates only the declared subjects into a managed connection pool."""
    cohort = orjson.dumps(
        {"subjects": [{"subject_id": "mock", "package": "mock", "segment": "data"}]}
    )
    with (
        patch("sys.argv", ["collect", "cohort", "out"]),
        patch("tools.collect_public_sdk_data.shutil.which", return_value="mock-gh"),
        patch("tools.collect_public_sdk_data.httpx.Client"),
        patch("tools.collect_public_sdk_data.ThreadPoolExecutor") as executor,
        patch.object(Path, "read_bytes", return_value=cohort),
    ):
        main()

    executor.assert_called_once_with(max_workers=2)
    assert executor.return_value.__enter__.return_value.submit.call_count == 1
