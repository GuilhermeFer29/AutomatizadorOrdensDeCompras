"""
Integration layer — external system connectors.

Provides:
* ``BaseConnector`` — abstract interface every connector must implement
* ``SyncResult`` — result DTO for sync operations
* ``get_connector()`` — factory to instantiate a connector by type
"""

from app.integrations.base import BaseConnector, SyncResult

# Registry: connector_type → class
_REGISTRY: dict[str, type[BaseConnector]] = {}


def register_connector(cls: type[BaseConnector]) -> type[BaseConnector]:
    """Class decorator to register a connector in the global registry."""
    _REGISTRY[cls.connector_type] = cls
    return cls


def get_connector(
    connector_type: str,
    integration_id: int,
    config: dict | None = None,
    credentials: dict | None = None,
) -> BaseConnector:
    """Factory: instantiate a connector by its type identifier.

    Raises:
        KeyError: If the connector_type is not registered.
    """
    cls = _REGISTRY.get(connector_type)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(none)"
        raise KeyError(
            f"Unknown connector_type={connector_type!r}. Available: {available}"
        )
    return cls(
        integration_id=integration_id,
        config=config,
        credentials=credentials,
    )


__all__ = [
    "BaseConnector",
    "SyncResult",
    "get_connector",
    "register_connector",
]
