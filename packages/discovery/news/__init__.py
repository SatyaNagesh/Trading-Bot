"""Scout — news package: provenance-kept facts.

Facts are inputs to hypothesis generation, never standalone trading signals.
"""
from packages.discovery.news.schema import ArticleFact, FilingFact

__all__ = ["ArticleFact", "FilingFact"]
