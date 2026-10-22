"""Helpers shared by several test modules."""

from tiktokenizer_py import prices


def offline_fetcher(url: str) -> str | None:
    """Tests never reach the network: a refresh fails like an unreachable host."""
    raise prices.PricingFetchError(f"network disabled in tests ({url})")
