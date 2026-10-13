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
| `GET /health` | Minimal native-core readiness without authentication or private data |
| `/` and `/assets/*` | Compiled Vue static assets; all administrative data requires authentication |

`create_app` owns startup/shutdown through the ASGI lifespan. Runtime starts the validated core and a single supervisor, restarts a failed process and schedules subscription refresh. The image uses one Uvicorn worker to keep one lifecycle owner.

Mutation requests require `X-Manager-Request: 1`; browser origins must match `PUBLIC_ORIGIN`. Subscription fetching validates every redirect and connects to the validated public IP while preserving HTTP Host and TLS SNI. Input and download sizes are bounded. Controller calls ignore inherited proxy environment variables.
