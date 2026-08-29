"""Collector framework core.

This package provides the reusable building blocks that future
Microsoft Graph workload collectors (G07) will build on top of:

    models       -- EndpointSpec, CollectionResult, helpers
    errors       -- deterministic error classification
    retry        -- bounded retry policy honoring Retry-After
    transport    -- Microsoft Graph HTTP client abstraction
    pagination   -- @odata.nextLink paginator
    inventory    -- adapter over config/api_inventory.json
    collector    -- BaseCollector orchestrator

Security:
- No module stores or logs tokens, client secrets, or ``Authorization``
  header values.
- All credentials enter the framework as callables (token_provider,
  fetch functions) that are invoked at request time and never
  persisted.
"""
from .models import (
    COLLECTION_PATTERN_PAGED,
    COLLECTION_PATTERN_SINGLE,
    COLLECTION_PATTERN_UNKNOWN,
    CollectionResult,
    EndpointSpec,
    ENDPOINT_TYPE_SECURITY_ONLY,
    ENDPOINT_TYPE_WORKLOAD,
    ENDPOINT_TYPES,
    utcnow_iso,
)
from .errors import (
    API_ERROR,
    AUTH_FAILURE,
    NETWORK_ERROR,
    PASS,
    PERMISSION_REQUIRED,
    THROTTLED,
    UNKNOWN,
    ENTITY_IDENTITY_UNAVAILABLE,
    PERSISTENCE_ERROR,
    classify_http_status,
    classify_response,
    classify_transport_failure,
    is_retryable,
)
from .retry import RetryDecision, RetryPolicy
from .transport import (
    DEFAULT_TIMEOUT,
    GRAPH_BASE_V1,
    GraphHttpError,
    GraphNetworkError,
    GraphTransport,
    GraphTransportError,
    Response,
    build_endpoint_url,
)
from .pagination import (
    Page,
    Paginator,
    PaginationResult,
    make_fetch_from_transport,
)
from .inventory import (
    InventoryValidationError,
    enabled_specs,
    entry_to_spec,
    load_inventory,
)
from .collector import BaseCollector, CollectorRun
from .auth import (
    AUTH_ERROR_CLASSIFICATIONS,
    AUTH_ERROR_HTTP,
    AUTH_ERROR_INVALID_CLIENT,
    AUTH_ERROR_MALFORMED,
    AUTH_ERROR_MISSING_CONFIG,
    AUTH_ERROR_NETWORK,
    AuthError,
    CollectorAuthConfig,
    CollectorTokenProvider,
)
from .config import (
    AuthConfigError,
    REQUIRED_VARS,
    Source,
    dict_source,
    env_file_source,
    env_source,
    load_auth_config,
)
from .results import (
    auth_error_to_classification,
    auth_error_to_result,
    result_to_dict,
    safe_dumps,
)
from .runtime import (
    CollectorRuntime,
    NormalizedCollection,
    NormalizationError,
    RuntimeError_,
    RuntimeOptions,
    RuntimeSummary,
)
from .http import (
    CollectorHttpOpenError,
    CollectorHttpOpener,
    GRAPH_HOST,
    LOGIN_HOST,
    build_collector_http_open,
)

__all__ = [
    "API_ERROR",
    "AUTH_ERROR_CLASSIFICATIONS",
    "AUTH_ERROR_HTTP",
    "AUTH_ERROR_INVALID_CLIENT",
    "AUTH_ERROR_MALFORMED",
    "AUTH_ERROR_MISSING_CONFIG",
    "AUTH_ERROR_NETWORK",
    "AUTH_FAILURE",
    "AuthConfigError",
    "AuthError",
    "BaseCollector",
    "COLLECTION_PATTERN_PAGED",
    "COLLECTION_PATTERN_SINGLE",
    "COLLECTION_PATTERN_UNKNOWN",
    "CollectionResult",
    "CollectorAuthConfig",
    "CollectorHttpOpenError",
    "CollectorHttpOpener",
    "CollectorRun",
    "CollectorRuntime",
    "NormalizedCollection",
    "NormalizationError",
    "CollectorTokenProvider",
    "EndpointSpec",
    "ENDPOINT_TYPE_SECURITY_ONLY",
    "ENDPOINT_TYPE_WORKLOAD",
    "ENDPOINT_TYPES",
    "GRAPH_BASE_V1",
    "GRAPH_HOST",
    "GraphHttpError",
    "GraphNetworkError",
    "GraphTransport",
    "GraphTransportError",
    "InventoryValidationError",
    "LOGIN_HOST",
    "NETWORK_ERROR",
    "PASS",
    "PERMISSION_REQUIRED",
    "Page",
    "Paginator",
    "PaginationResult",
    "REQUIRED_VARS",
    "Response",
    "RetryDecision",
    "RetryPolicy",
    "RuntimeError_",
    "RuntimeOptions",
    "RuntimeSummary",
    "Source",
    "THROTTLED",
    "UNKNOWN",
    "ENTITY_IDENTITY_UNAVAILABLE",
    "PERSISTENCE_ERROR",
    "auth_error_to_classification",
    "auth_error_to_result",
    "build_endpoint_url",
    "build_collector_http_open",
    "classify_http_status",
    "classify_response",
    "classify_transport_failure",
    "DEFAULT_TIMEOUT",
    "dict_source",
    "enabled_specs",
    "entry_to_spec",
    "env_file_source",
    "env_source",
    "is_retryable",
    "load_auth_config",
    "make_fetch_from_transport",
    "result_to_dict",
    "safe_dumps",
    "utcnow_iso",
]
