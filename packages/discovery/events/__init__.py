"""Scout — events package: typed events with a closed taxonomy.

Only the closed-set taxonomy and the event schema ship at this gate. Ingestion
and event detection are a later step.
"""
from packages.discovery.events.schema import EventRecord
from packages.discovery.events.taxonomy import EVENT_KINDS, VALID_KINDS, is_valid

__all__ = ["EventRecord", "EVENT_KINDS", "VALID_KINDS", "is_valid"]
