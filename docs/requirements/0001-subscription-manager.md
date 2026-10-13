# Independent subscription manager

Status: pending-verification

The user requested a separate GitHub project, a GHCR image, two Compose deployments, a subscription management UI and no publication of existing nodes. HTTPS access through a separate BaoTa domain is selected; the domain remains to be supplied for production deployment.

Scope: durable multiple Clash/Mihomo subscriptions, configuration import, edit/refresh/switch/delete, selection and latency; independent proxy deployment connected to the existing platform. Excludes ChatGPT account administration, provider-only configurations, raw-link conversion and automatic production migration.

Ownership and HTTP interfaces are defined by [CONTEXT](../../CONTEXT.md) and the [map](../maps/runtime.md). Download/validation failures must preserve existing nodes; unsuccessful activation must recover the committed configuration. Credentials stay in private data mounts.

| Acceptance criterion | Verification |
| --- | --- |
| Persistent import, switch and restart | Isolated real-core runtime tests and Docker smoke |
| Invalid config, reload timeout and persistence failure retain previous exit | Fault injection with actual native core |
| Login, origin checks and private projections | HTTP contract tests |
| Desktop/mobile subscription editing and node selection | Isolated browser smoke |
| No existing private nodes or URLs published | Git and image-context inspection before publication |
| Public multi-architecture image from verified commit | Release workflow and anonymous registry inspection |
| BaoTa domain and real subscription work on user's server | Pending production deployment and user confirmation |

Automated verification does not constitute user acceptance. This document remains pending-verification until the production deployment is reviewed by the user.
