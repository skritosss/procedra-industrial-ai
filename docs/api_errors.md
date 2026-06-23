# API Error Contract

All API errors use the same JSON envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [],
    "request_id": "..."
  }
}
```

Every response includes `X-Request-ID`. If the caller sends a safe `X-Request-ID`, the service preserves it; otherwise the service generates a UUID. Oversized or newline-containing values are rejected. This makes demo runs, logs, and future integrations easier to trace.

Common error codes:

- `bad_request` for invalid user input handled inside endpoints;
- `validation_error` for schema validation failures;
- `not_found` for unknown routes;
- `internal_error` for unexpected failures.

Unexpected failures intentionally return a generic message and do not expose stack traces or internal exception text to clients.
