# Railway outbound IP investigation — 2026-11-02

## Findings

Railway's live outbound-network status for the `Backend VOS` service in the `vos` environment reports static IPv4 enabled, high availability enabled, and IPv6 enabled. The backend is deployed in Railway's SFO (`us-west2`) region. Railway currently assigns this service a pool of three IPv4 addresses:

- `152.55.176.240`
- `162.220.232.252`
- `152.55.177.181`

Railway load-balances outbound traffic across the three addresses for throughput and resiliency. This is a stable IPv4 allowlist set, not one guaranteed source IP. Railway also says these addresses are not guaranteed to be exclusive to this service and may be shared. Moving the service to another region changes its assigned addresses. [Railway Static Outbound IPs](https://docs.railway.com/networking/static-outbound-ips)

Outbound IPv6 is enabled on the backend. Static Outbound IPs cover IPv4; the configured IPv4 pool does not identify the IPv6 source address. Railway documents IPv6 as a separate opt-in outbound feature that runs alongside IPv4. [Railway Outbound Networking](https://docs.railway.com/networking/outbound-networking)

## IP echo attempt

The first attempt to run an echo from the container was blocked because Railway SSH has no registered key. Later, the requested opt-in startup diagnostic was deployed and ran inside the actual backend container. At `2026-11-02 12:17:53 EST`, it reported:

- IPv4 echo (`https://ipv4.icanhazip.com`): `152.55.176.240`
- IPv6 echo (`https://ipv6.icanhazip.com`): `2607:99c0:800:1ce::1`
- `resva.readymode.com` A records: `104.18.0.65`, `104.18.1.65`
- `resva.readymode.com` AAAA records: unavailable (`getaddrinfo` returned `gaierror`)

The observed IPv4 address is one of Railway's three assigned static IPv4 egress addresses. The IPv6 echo confirms IPv6 outbound connectivity, but Railway's static IPv4 assignment does not describe that IPv6 address.

No normal ReadyMode login ran during the diagnostic deployment, so the client did not log a peer socket for the initial GET. Since the hostname returned A records but no AAAA record during the diagnostic, the initial GET would be expected to use IPv4; the peer address for an actual login request was not directly captured, and the earlier Cloudflare Ray ID cannot be mapped to one egress address from these results.

After collecting the output, `READYMODE_EGRESS_DIAGNOSTICS` was deleted from the Railway service and the backend was redeployed successfully. The flag is absent, so the diagnostic is off in the current deployment.

## What to give ReadyMode if you choose to ask

Provide the timestamp and timezone of a failed initial `GET https://resva.readymode.com/`, the final URL, HTTP 403, `CF-Mitigated: challenge`, the Cloudflare `CF-Ray` value, and the sanitized challenge classification. Include the three Railway IPv4 addresses above and explain that the service has IPv6 egress enabled. Ask whether the request was challenged based on one of those IPv4 addresses or an IPv6 source, and what source-address allowlisting or policy check is supported. Do not send credentials, cookies, session IDs, or CSRF values.

This evidence does not prove that any Railway address is blocked. The prior local-versus-Railway result, with matching runtime and request headers but different challenge outcome, is consistent with network-level policy, but the egress address for that specific request was not captured.

## Changes and approval

No Railway settings or authentication code were changed. Static outbound IPv4 is already enabled, so no change is needed to obtain the stable IPv4 pool. Changing the static-IP mode or pool, disabling IPv6 for an isolation test, or moving the service region would change deployment networking and require approval; changes that affect IP assignment require a redeploy. Railway's documentation describes management in the service Networking settings or with `railway outbound-network` CLI commands. [Railway Outbound Networking](https://docs.railway.com/networking/outbound-networking)
