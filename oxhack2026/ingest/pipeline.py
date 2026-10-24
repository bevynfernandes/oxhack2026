"""Bounded, resumable npm cohort extraction and deterministic candidate assembly."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path

import httpx
import orjson

from oxhack2026.catalog.schemas import CatalogSnapshot, Contract, Identifier, TimeWindow
from oxhack2026.ingest.checkpoints import checkpointed_fetch
from oxhack2026.ingest.npm import NpmExtraction, NpmRequest, request_windows
from oxhack2026.storage.build import CandidateConfig, write_candidate
from oxhack2026.storage.datasets import DatasetBundle
from oxhack2026.storage.local import atomic_write, file_lock


class NpmRun(Contract):
    """Immutable request identity binding one run ID to its cohort and dates."""

    run_id: Identifier
    dataset_version: Identifier
    window: TimeWindow
    code_revision: Identifier
    feature_definition_version: Identifier = "downloads-features-v1"
    target_definition_version: Identifier = "targets-v1"


def extract_catalog(catalog: CatalogSnapshot, root: Path, run: NpmRun) -> DatasetBundle:
    """Extract verified npm representatives with at most four concurrent requests.

    Args:
        catalog: Frozen catalogue, selected independently of subsequent growth.
        root: Output bundle root; checkpoints persist through interrupted runs.
        run: Stable retry ID, dates, output identity and implementation revision.
    Returns:
        Validated candidate bundle without advancing the publication pointer.
    Raises:
        ValueError: For changed run configuration, missing mappings or invalid data.
        OSError: For persistence failures.
        httpx.HTTPError: For exhausted HTTP errors; completed checkpoints survive.
        RuntimeError: If the source requests a deferred retry.
    """
    configuration = orjson.dumps(
        {
            "catalog": catalog.model_dump(mode="json"),
            "run": run.model_dump(mode="json"),
        },
        option=orjson.OPT_SORT_KEYS,
    )
    folder = root / "checkpoints" / run.run_id
    with file_lock(folder / ".run.lock"):
        config_path = folder / "run.json"
        if config_path.exists():
            if config_path.read_bytes() != configuration:
                message = "Run ID is already bound to different catalogue/dates/code"
                raise ValueError(message)
        else:
            atomic_write(config_path, configuration)
    package_ids = {
        mapping.package_id
        for mapping in catalog.mappings
        if mapping.primary
        and mapping.organization_representative
        and mapping.verified
        and mapping.valid_from <= catalog.recorded_at
        and (mapping.valid_to is None or catalog.recorded_at < mapping.valid_to)
    }
    packages = tuple(
        package
        for package in catalog.packages
        if package.ecosystem == "npm" and package.package_id in package_ids
    )
    if not packages:
        message = "No verified npm organization representatives in this catalogue"
        raise ValueError(message)
    requests = tuple(
        NpmRequest(
            package=package, catalog_version=catalog.catalog_version, window=window
        )
        for package in packages
        for window in request_windows(run.window)
    )
    with httpx.Client(
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=4)
    ) as client:

        def fetch(request: NpmRequest) -> NpmExtraction:
            return checkpointed_fetch(request, client, root, run.run_id)

        with ThreadPoolExecutor(max_workers=4) as pool:
            extractions = tuple(pool.map(fetch, requests))
    config = CandidateConfig(
        dataset_version=run.dataset_version,
        created_at=max(
            catalog.recorded_at, *(item.checkpoint.retrieved_at for item in extractions)
        ),
        code_revision=run.code_revision,
        configuration_sha256=sha256(configuration).hexdigest(),
        feature_definition_version=run.feature_definition_version,
        target_definition_version=run.target_definition_version,
    )
    return write_candidate(catalog, extractions, root, config)
