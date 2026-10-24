"""Read port for Dev 1 adapters and Dev 2's authoritative shortlist scorer.

Implementations read published artifacts only. They translate storage failures into
RepositoryUnavailable and missing resources into ResourceNotFound. No method may
fetch vendor data, train, publish, or call an LLM. Construct DTOs using validation.
"""

from typing import Protocol

from oxhack2026.api.schemas import (
    Catalog,
    Cutoffs,
    DataHealth,
    Ecosystem,
    Evaluation,
    ForecastBatch,
    Health,
    History,
    Rankings,
    Reveal,
    RevealRequest,
    Target,
)


class RepositoryUnavailable(Exception):
    """Required storage, artifacts, or schema compatibility are unavailable."""


class ResourceNotFound(Exception):
    """A requested immutable identifier does not exist."""


class ImmatureOutcome(Exception):
    """The complete target window has not met outcome availability conditions."""


class PublishedRepository(Protocol):
    """Adapter boundary; methods must not return private storage metadata.

    All reads may raise RepositoryUnavailable; identifier reads may additionally
    raise ResourceNotFound. Reveal may raise ImmatureOutcome. The application owner
    manages connection pools and their lifecycle outside this read-only protocol.
    """

    def readiness(self) -> Health:
        """Return readiness of required schema, storage and published artifacts."""
        ...

    def catalog(self, ecosystem: Ecosystem | None, batch_id: str | None) -> Catalog:
        """Return verified identities for ecosystem and optional frozen batch ID."""
        ...

    def cutoffs(self, ecosystem: Ecosystem | None, target_id: Target | None) -> Cutoffs:
        """Return published combinations matching optional ecosystem/target filters."""
        ...

    def forecast(self, batch_id: str) -> ForecastBatch:
        """Return the immutable forecast identified by batch_id, without outcomes."""
        ...

    def rankings(self, batch_id: str) -> Rankings:
        """Return saved ordering and current reveal availability for batch_id."""
        ...

    def history(self, tool_id: str, batch_id: str, limit: int) -> History:
        """Return at most limit observations for tool_id in batch_id's dataset."""
        ...

    def reveal(self, batch_id: str, selection: RevealRequest) -> Reveal:
        """Return mature truth and Dev 2 scores for batch_id and exact selection.

        Check outcome completeness and publication/collection conditions first.
        Call the lightweight model-owned scorer or read an exact saved score.
        Never recompute forecasting or ranking policy in the storage adapter.
        """
        ...

    def evaluation(self, evaluation_id: str) -> Evaluation:
        """Return the immutable report identified by evaluation_id."""
        ...

    def data_health(self) -> DataHealth:
        """Return public source health, without internal exception strings."""
        ...
