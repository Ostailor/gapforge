"""Generic web metadata source placeholder."""

from __future__ import annotations

from gapforge.models import Paper
from gapforge.sources.base import FakeSourceMixin, ResearchSource


class WebSource(FakeSourceMixin, ResearchSource):
    name = "Web"

    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        # TODO: Wire to a vetted metadata provider or allowlisted web search API.
        return [self._fake_paper(query, 1, "Dataset and benchmark discovery")][:max_results]
