"""Database layer for RadioShaq.

Provides SQLAlchemy models, PostGIS integration, and data access layers.
"""

from radioshaq.database.gis import (
    haversine_km,
    propagation_note,
    propagation_prediction,
    suggest_bands_for_distance_km,
)
from radioshaq.database.models import (
    Base,
    CoordinationEvent,
    OperatorLocation,
    Transcript,
)
from radioshaq.database.postgres_gis import PostGISManager
from radioshaq.database.transcripts import TranscriptStorage, TranscriptStoreProtocol

__all__ = [
    "Base",
    "CoordinationEvent",
    "OperatorLocation",
    "Transcript",
    "PostGISManager",
    "DynamoDBStateStore",
    "TranscriptStorage",
    "TranscriptStoreProtocol",
    "haversine_km",
    "propagation_prediction",
    "propagation_note",
    "suggest_bands_for_distance_km",
]


def __getattr__(name: str):
    """Lazy-import DynamoDB (boto3) so gis/models/postgres/transcripts can be used without it."""
    if name == "DynamoDBStateStore":
        from radioshaq.database.dynamodb import DynamoDBStateStore
        return DynamoDBStateStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
