# VLESS and Base64 subscription support

Status: pending-verification

The user needs the existing subscription form to accept an HTTP endpoint returning Base64 VLESS/Reality/Vision links. The previous YAML-only importer reports a format error for that response.

Scope: local normalization of raw VLESS links and standard/URL-safe Base64 into the existing inline-node cache, retaining TCP Vision, TLS/Reality and supported WS/gRPC fields. Both remote refresh and file/text import use the same interface. The form explains supported inputs. Other URI protocols, XHTTP/mKCP and provider-only YAML remain outside this change.

Ownership remains Runtime for parsing, immutable caches, validation, activation and refresh. Fetch remains responsible for public socket pinning, bounded downloads and certificate validation; Vue owns only input and rendering. HTTP routes and manifest schema remain unchanged. A malformed or unsupported node fails the entire operation and preserves the active profile and committed cache. Private URLs and node data must not enter Git, image contexts or public projections.

| Acceptance criterion | Evidence |
| --- | --- |
| Base64 variants preserve VLESS/Reality/Vision fields and names | Parser and real-core HTTP/runtime tests |
| Import, inactive-profile validation, switch, refresh and restart work | Isolated native-core tests |
| Malformed links, excess nodes, aliases and invalid refresh preserve configuration | Parser bounds and rollback regression |
| YAML and frontend file/text workflows still work | Full runtime regression and desktop/mobile browser smoke |
| Provided response is recognized without storing private payload in the repository | In-memory diagnosis verifies 32 nodes |
| Published image imports the endpoint on the user's server | v1.0.1 deployment: 32 nodes imported and manually refreshed through the authenticated manager API; existing active profile and node retained |

Runtime regression passed 62 tests; desktop/mobile browser smoke, Docker release smoke and production login/assets/platform-proxy checks passed. User confirmation of the production interface remains pending. Automated verification is separate from user acceptance. See [accepted import boundary](../adr/0002-vless-subscriptions.md).
