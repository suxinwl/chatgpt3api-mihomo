# 0003: Inspect and probe subscriptions without activating them

Status: accepted

The user needs to inspect and test inactive subscriptions separately from the active node selector. The native controller only knows the loaded profile. Reloading it for a test would change live connections, while loading every subscription into it would mix inactive nodes into the exit configuration.

Extend Runtime, the existing lifecycle owner, with filtered per-profile node views and bounded temporary native-core probes. Inspection reads the saved cache; downloading remains the explicit refresh operation. Each probe starts the pinned Mihomo binary in a private temporary directory with a loopback authenticated controller, no proxy listeners, no TUN or DNS service, and no selection cache shared with the main core. Runtime permits at most two concurrent probes, terminates them on completion, failure or shutdown, and removes their temporary files. No new dependency, durable schema or controller routing is introduced.

Runtime binds test results to profile ID, immutable cache revision and node name. It rejects changed revisions, deleted profiles and foreign nodes before testing and before accepting a result. Transient results expose only name, protocol, delay, status and label; credentials and full source URLs remain private. Native timeouts and connection failures project as unavailable, while probe startup/control failures remain operation errors. The [native delay API](https://github.com/MetaCubeX/mihomo/blob/v1.19.32/hub/route/proxies.go) remains the latency authority.

Vue owns expansion, request cancellation and sequential bulk-test progress per subscription. Results stay under that subscription, with no selection action. Closing the list, logout and unmount cancel queued browser work; an already executing server probe completes within its bounded timeout and cleans up. The existing active selector and native selection API retain their membership boundary.
