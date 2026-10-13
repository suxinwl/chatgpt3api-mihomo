# Domain and ownership

Status: current

This repository is an independent proxy service. It does not own or migrate the chatgpt3api Application Database, Upstream Accounts, Call Records, Image Tasks or Image Assets.

| Concept | Authority | Durable representation |
| --- | --- | --- |
| Subscription Profile, activation, refresh and rollback | `manager.runtime.Runtime` | `/data/profiles.json` and immutable YAML caches |
| Node connection, selection and latency | Mihomo native core | Native selection cache in `/data` |
| Fixed listeners and core lifecycle | `Runtime` | Generated `/data/config.yaml` from committed profiles |
| Subscription download bounds and public socket validation | `manager.fetch.fetch_subscription` | None |
| HTTP authentication and safe error projection | `manager.app.create_app` | Private session signing key in `/data` |
| Forms, dialogs, focus, polling and responsive layout | `web/src/App.vue` | Browser interaction state only |

The profile manifest is the recovery authority. Startup rebuilds the active configuration from the committed manifest and node cache. A configuration candidate is validated by the native core, applied, then committed atomically; failures trigger compensation to the last committed configuration. Download work runs outside the commit lock, with a revision check before committing.

The service imports only the `proxies` array. External subscriptions cannot choose listener ports, control credentials, DNS, rules or TUN. Native control calls use a private loopback listener; the manager returns a filtered public projection and never returns full subscription URLs or raw proxy credentials.

See [accepted decision](docs/adr/0001-independent-manager.md) and [current map](docs/maps/runtime.md).
