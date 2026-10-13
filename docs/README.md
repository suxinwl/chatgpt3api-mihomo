# Documentation

Status: current

- [Domain ownership](../CONTEXT.md)
- [Accepted architecture](adr/0001-independent-manager.md)
- [VLESS URI and Base64 import boundary](adr/0002-vless-subscriptions.md)
- [Separate subscription inspection and probes](adr/0003-profile-node-inspection.md)
- [Runtime and HTTP map](maps/runtime.md)
- [Deployment, BaoTa, migration and recovery](runbooks/deployment.md)
- [Requirement and remaining acceptance](requirements/0001-subscription-manager.md)
- [VLESS subscription requirement and verification](requirements/0002-vless-subscriptions.md)
- [Per-subscription node inspection and testing](requirements/0003-profile-node-inspection.md)

Local development uses Python 3.13 and Node 22. Install `requirements.txt` from official PyPI, then run `npm ci` and `npm run build` in `web`. Start `uvicorn manager.app:create_app --factory --host 127.0.0.1 --port 8080 --no-access-log` with a downloaded official Mihomo binary in `MIHOMO_BINARY`, a private `DATA_DIR`, and a strong `MIHOMO_ADMIN_PASSWORD`. For local HTTP only, set `COOKIE_SECURE=false`.

Tests and browser fixtures live in ignored local directories. The release workflow builds the frontend, compiles Python, validates both Compose files and runs an isolated Docker startup/authentication/import/restart smoke. Publication runs only for `v*` tags, checks `VERSION`, and builds amd64 and arm64 images. Update `VERSION`, the web package version, the lockfile and CHANGELOG together for a release; never include runtime data in the build context.

The upstream binary source and SHA256 checksums are recorded in `upstream.json`. Docker builds fetch only official release artifacts and reject a digest mismatch before extraction. Updating the core requires new pinned artifacts and real-core validation.
