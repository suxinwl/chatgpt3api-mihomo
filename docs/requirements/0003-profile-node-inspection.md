# Independent subscription node inspection and testing

Status: pending-verification

Problem: inactive subscriptions cannot display their nodes or measure connectivity without switching the live exit. The user explicitly requires a separate display from the active node selector.

Outcome and scope: each subscription has an expandable saved-node list, single-node latency tests and a cancellable sequential bulk test. Active and inactive profiles use the same view. Tests do not activate profiles, reload the live core, select nodes or merge nodes into the active selector. Bandwidth benchmarks, source URL disclosure and automatic subscription switching are outside scope.

Runtime owns profile snapshots, result revisions, bounded probe processes and cleanup. Mihomo measures latency. App owns authentication and input validation. Vue owns expansion, loading, cancellation, progress, focus and responsive layout. New authenticated interfaces are `GET /api/profiles/{id}/nodes` and `POST /api/profiles/{id}/nodes/delay` with node name and revision. Unavailable nodes receive a safe result; missing profiles, foreign nodes, stale snapshots, saturation and control failures receive safe operation errors. No persistence changes are required.

| Acceptance criterion | Verification |
| --- | --- |
| Inactive lists remain separate and expose no credentials | HTTP projection tests and desktop/mobile browser checks |
| Tests retain the active profile, selected node and main process | Real-core runtime tests and production comparison |
| Same names in different subscriptions cannot share results | Profile/revision scoped runtime tests |
| Timeout, startup failure, concurrent limits and shutdown clean up | Real-core tests and fault injection |
| Refresh/delete invalidate old results; bulk work can stop | Revision tests and browser cancellation checks |
| Existing import, selection, refresh and recovery still work | Full regression, build and release smoke |

Local regression passed 70 tests, including real native probes, unavailable/timeout cleanup, controller-before-node startup, same-name isolation, stale refresh/deletion, admission limits, shutdown and authenticated projections. The production frontend build and isolated desktop 1440×1000/mobile 390×844 browser smoke passed, covering separate inactive views, single/bulk tests, cancellation, unchanged selection and existing import/edit/switch/delete workflows. Production deployment verification and user acceptance remain pending. See [ADR 0003](../adr/0003-profile-node-inspection.md).
