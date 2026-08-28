# Playbook — network and TLS

| Finding / symptom | Confirm with | Likely causes | Mitigation | Verify |
|---|---|---|---|---|
| `DNS_RESOLUTION_FAILED` | `net.dns --name <fqdn>`; try a known public name and an internal name | resolver down, wrong `/etc/resolv.conf`, split-horizon, search domain | Recommendation: fix resolver config; no allowlisted action | both names resolve |
| `DNS_SLOW` | `net.dns` timing repeated; `net.reach` to each nameserver port 53 | first nameserver unreachable (timeouts then fallback) | Recommendation: reorder/replace nameserver | duration < 200 ms |
| `NO_DEFAULT_ROUTE`, `INTERFACES_DOWN` | `net.route`; `host.journal --unit systemd-networkd` / NetworkManager | DHCP failure, cable/VM NIC, misapplied netplan | Recommendation: restore config; `service.restart` of the network unit only when the cause is a stuck daemon | default route present, interface UP |
| `TCP_UNREACHABLE` | `net.reach --host --port` from the client host **and** from the server host (`net.ports` there) | service not listening, bound to 127.0.0.1 only, firewall/security group, wrong port | Recommendation: bind address / firewall change; `service.restart` if the service died | reachable from client |
| `TLS_EXPIRING`, `TLS_VERIFY_FAILED` | `net.reach --tls` (reports `daysRemaining`, issuer, SANs, verify error) | expired cert, missing intermediate chain, hostname not in SANs, private CA not trusted on client, clock skew | Recommendation: renew/redeploy cert or fix chain/trust store; `service.restart` after a cert file was replaced so it is reloaded | `verified:true`, `daysRemaining` sane |
| Unexpected listener in `net.ports` | `net.ports` → pid → `host.processes`; `security.auth-events`; `change.recent` | new service, debug port left open, malware | If unexplained: security lane (stop, preserve, hand off to `soc-event-correlation`) | listener explained or removed |
| Exposed on all interfaces | `net.ports.exposedToAllInterfaces` | default bind `0.0.0.0` | Recommendation: bind to loopback or restrict with firewall | not in exposed list |
| Works from one host only | compare `net.dns`, `net.route`, `net.reach` on both hosts | asymmetric DNS/routes, per-host firewall | cause-specific | parity between hosts |
| Kubernetes service unreachable | `k8s.pods --selector`, `k8s.describe --kind service`, `k8s.events`, `net.reach` to node port | no ready endpoints, selector mismatch, NetworkPolicy | see the Kubernetes playbook | endpoints ready and reachable |

Notes:

- `net.reach` uses the host's own resolver and trust store; a `TLS_VERIFY_FAILED` on a private CA is expected from a host that lacks the CA, and the decoded certificate fields still tell you expiry and SANs.
- Reachability checks are bounded to 10 s; a slow success is itself a finding.
