# Runtime map

Status: current

| Entry | Owner and effects |
| --- | --- |
| `POST /api/login`, `POST /api/logout` | App validates login, rate-limits failures and issues/removes a signed HttpOnly cookie |
| `GET /api/overview` | Runtime projects profiles, allowed actions and filtered native node state |
| `POST /api/profiles`, `PUT /api/profiles/{id}` | App validates input; Runtime downloads/imports and validates before committing |
| `POST /api/profiles/{id}/refresh` | Runtime downloads outside lock; checks profile revision; keeps previous config on failure |
| `POST /api/profiles/{id}/activate`, `DELETE /api/profiles/{id}` | Runtime commits an activation or inactive-profile deletion |
| `PUT /api/nodes/selected`, `POST /api/nodes/delay` | Runtime checks membership then calls the native controller |
| `GET /api/profiles/{id}/nodes` | Runtime reads the saved cache and projects names, types and revision-scoped transient latency results |
| `POST /api/profiles/{id}/nodes/delay` | Runtime validates profile, node and revision, then probes through a separate temporary core without changing the active selector |
| `GET /health` | Minimal native-core readiness without authentication or private data |
| `/` and `/assets/*` | Compiled Vue static assets; all administrative data requires authentication |

`create_app` owns startup/shutdown through the ASGI lifespan. Runtime starts the validated core and a single supervisor, restarts a failed process and schedules subscription refresh. The image uses one Uvicorn worker to keep one lifecycle owner.

Mutation requests require `X-Manager-Request: 1`; browser origins must match `PUBLIC_ORIGIN`. Subscription fetching validates every redirect and connects to the validated public IP while preserving HTTP Host and TLS SNI. Input and download sizes are bounded. Controller calls ignore inherited proxy environment variables.

The import path is `Runtime.add/edit/refresh` → `parse_nodes` → normalized private YAML cache → native-core validation → profile commit. `parse_nodes` accepts inline YAML/JSON nodes and raw or Base64 VLESS links; `_vless_nodes` maps supported URI fields and assigns unique names. A malformed or unsupported link fails the entire profile. Existing caches retain the same schema and restart behavior.

`Runtime.profile_nodes` exposes only `id`, opaque `revision` and `nodes` with `name`, `type`, `delay`, `status` and `label`. `profile_delay` requires name and revision, rejects stale snapshots and stores the accepted result in memory. `_probe` admits two operations at most, starts the pinned core in a private temporary directory, waits at most six seconds for the target node to appear in its authenticated loopback controller, and requests the native five-second delay test. Controller readiness alone is insufficient because it can precede node installation. Proxy listeners, DNS and TUN are disabled. HTTP 503/504 means unavailable; startup/control errors remain safe operation errors. Cleanup terminates/waits for the process before removing files; shutdown terminates registered probes. No network work holds the main commit lock.

Vue keeps one expandable view and one abortable sequential test loop per profile. Refresh changes invalidate open snapshots; close, deletion, logout and unmount cancel browser work. Cancelling prevents further queued tests, while a running server request finishes within its bounded timeout. Transient results do not survive service restart and do not change native active-core history.
