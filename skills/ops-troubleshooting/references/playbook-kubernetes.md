# Playbook — Kubernetes

Start with `k8s.context` (are you on the right cluster, can you read?) and `triage.k8s`. Pod finding codes are `POD_<REASON>`; node codes are `NODE_<CONDITION>`.

| Finding / symptom | Confirm with | Likely causes | Mitigation (allowlisted where marked) | Verify |
|---|---|---|---|---|
| `POD_CRASHLOOPBACKOFF` | `k8s.logs --name <pod> --previous`, `k8s.describe --kind pod`, `k8s.events --namespace` | app exits on start (config, missing secret/env, dependency down), failing probe, wrong command | Fix the cause. **Allowlisted mitigation**: `k8s.pod.delete` (managed pod) after a transient dependency recovered, or `k8s.rollout.restart` after the config was fixed | restarts stop increasing; `ready:true` |
| `POD_OOMKILLED`, `OOMKilled(previous)` | `k8s.logs --previous`, `k8s.describe` (limits), `k8s.nodes` (pressure) | memory limit too low, leak, batch spike | Recommendation: raise limit / fix leak. `k8s.rollout.restart` only buys time | no new OOMKilled in `lastState` |
| `POD_IMAGEPULLBACKOFF`, `POD_ERRIMAGEPULL` | `k8s.events` (exact pull error), `k8s.describe` | wrong tag, private registry auth, registry down, rate limit | Recommendation: fix image ref or pull secret; then `k8s.rollout.restart` | pods Running |
| `POD_PENDING`, `POD_UNSCHEDULABLE_*` | `k8s.events` (`FailedScheduling` message), `k8s.nodes` (taints, allocatable, pressure) | insufficient CPU/memory, taints/affinity, PVC not bound, node cordoned | Recommendation: capacity, tolerations, storage. No allowlisted action | pod scheduled |
| `NODE_NOT_READY` | `k8s.nodes`, on that node: `host.services --unit kubelet` (or `k3s`), `host.disk`, `net.reach` to the API | kubelet down, disk pressure, network partition, VM stopped | Recommendation: fix node; `service.restart` of kubelet only when its journal shows a stuck daemon | node `Ready` |
| `NODE_MEMORYPRESSURE`, `NODE_DISKPRESSURE`, `NODE_PIDPRESSURE` | `k8s.nodes --usage`, on node `host.overview`, `host.disk` | overcommit, image/log bloat, fork bomb | Recommendation: evict/limit, prune images, size nodes | condition clears |
| `ROLLOUT_INCOMPLETE`, `ROLLOUT_STALLED` | `k8s.rollout` (conditions, history), `k8s.pods --selector`, `k8s.events` | new revision crashing, probes failing, quota, PDB blocking | Recommendation: `kubectl rollout undo` (not allowlisted; human or approved capability). `k8s.rollout.restart` only when pods are stuck for transient reasons | `rolloutComplete:true` |
| `WARNING_EVENTS` with `BackOff`, `Unhealthy`, `FailedMount` | `k8s.events --namespace`, then the pod-level checks | probe misconfig, volume/secret missing | cause-specific | warning count stops growing |
| Service unreachable | `k8s.describe --kind service`, `k8s.pods --selector <svc selector>`, `k8s.describe --kind endpoints` | no ready pods, selector mismatch, wrong targetPort, NetworkPolicy | cause-specific | endpoints populated, `net.reach` ok |
| "It was fine before the deploy" | `k8s.rollout` history/images, `change.recent` on nodes | new image/config | Recommendation: rollback via `rollout undo` | previous behaviour restored |

Rules:

- `k8s.describe` refuses Secrets and ConfigMaps by design; reason about missing keys from events and logs, never by reading secret contents.
- `k8s.logs` is capped at 1000 lines; use `--pattern`, `--since`, `--container`, and `--previous` instead of raising the tail.
- `k8s.pod.delete` refuses pods without a controller; deleting a bare pod is data loss, not remediation.
- Restarting a rollout re-pulls images and re-reads mounted config; it does not fix a bad image or a wrong limit.
- Cluster-wide symptoms (many namespaces, several nodes) point at nodes, DNS (`kube-dns`/CoreDNS pods), or the API — check those before individual workloads.
