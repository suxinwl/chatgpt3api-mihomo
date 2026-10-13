# 0001: Independent proxy and persistent subscription manager

Status: accepted

The requested deployment consists of two separate Compose applications and a published proxy image. Mihomo's controller can select proxies and reload configurations, but it does not own durable multi-subscription editing. A controller-only dashboard does not satisfy this requirement.

Bundle the unmodified, checksum-pinned Mihomo core with a small FastAPI manager and a Vue page in one independent image. Runtime owns profile persistence, scheduled refresh, configuration validation, activation, compensation and process supervision. Mihomo remains the only authority for connections, node selection and latency. The service does not share the platform database or app runtime volume.

Use a private `/data` bind mount for the profile manifest, node caches and signing keys. Only empty examples are published. Both Compose applications join one named Docker bridge; the platform uses the stable alias `mihomo:7890`. The manager is reverse-proxied through a host loopback port; the native controller is never published.

Imported routing, controller, listeners, TUN and DNS settings are intentionally ignored. This first release supports Clash/Mihomo YAML with inline nodes; provider-only configurations and raw URI/Base64 conversion are outside its contract. This avoids a separate conversion service and preserves a bounded import boundary.
