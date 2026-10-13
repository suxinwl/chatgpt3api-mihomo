# 0002: Bounded VLESS URI and Base64 subscription import

Status: accepted

The user supplied a subscription endpoint whose response is Base64 containing VLESS/Reality/Vision share links. The YAML-only boundary in ADR 0001 rejects this response. This decision extends that import boundary without changing profile persistence, core lifecycle, HTTP endpoints or download security.

Runtime's existing `parse_nodes` interface normalizes YAML/JSON inline nodes, raw VLESS share links and their standard or URL-safe Base64 subscription representation into the same node list. Conversion uses Python's standard URI and Base64 parsers; there is no external conversion service. The VLESS URI adapter supports TCP, WebSocket and ordinary gRPC, with none/TLS/Reality security and TCP Vision. Unsupported URI protocols, transports, encryption and known unsupported transport options fail the whole import instead of removing nodes silently.

Imports remain bounded to 8 MB and 1–512 nodes. YAML aliases remain rejected and YAML node names remain unique. VLESS fragments are decoded as node names; missing names receive a deterministic fallback and conflicting or reserved names receive numbered suffixes. Only normalized node data enters immutable private caches. The actual Mihomo core must validate every imported profile before commit. Existing subscription fetch, refresh concurrency, compensation and private projections remain authoritative.

VLESS fields follow the [Xray share-link proposal](https://github.com/XTLS/Xray-core/discussions/716) and are mapped to [Mihomo VLESS fields](https://wiki.metacubex.one/config/proxies/vless/). Subscription URLs, responses and credentials remain private deployment data and are never sent to conversion services or included in examples, tests, logs or images.
