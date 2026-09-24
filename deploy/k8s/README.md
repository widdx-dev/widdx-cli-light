# WIDDX Nexus — Kubernetes Deployment (Task 4.4)

Production manifests for running WIDDX Nexus on Kubernetes with
auto-scaling, health probes, TLS ingress, and isolated persistent
storage.

## Files

| File | Purpose |
|------|---------|
| `namespace.yaml` | `widdx` namespace (pod-security `restricted`) |
| `deployment.yaml` | 2-replica Deployment with probes, resources, security context |
| `service.yaml` | ClusterIP service (port 80 → container 8000) |
| `ingress.yaml` | nginx ingress + cert-manager TLS + WebSocket timeouts |
| `hpa.yaml` | HorizontalPodAutoscaler (2–10 replicas, CPU 70% / mem 80%) |
| `pvc.yaml` | PersistentVolumeClaim for `.widdx/` data |
| `configmap.yaml` | Non-secret runtime config (CORS, tenancy, telemetry) |
| `secret.example.yaml` | **Template** for API/admin keys (not committed filled) |
| `kustomization.yaml` | Bundles the above (excludes secrets) |

## Prerequisites

* A built image: `docker build -t widdx/nexus:3.3.0 .` (push to your registry)
* [metrics-server](https://github.com/kubernetes-sigs/metrics-server) (for the HPA)
* [ingress-nginx](https://kubernetes.github.io/ingress-nginx/) and
  [cert-manager](https://cert-manager.io/) with a `letsencrypt-prod` ClusterIssuer

## Deploy

```bash
# 1. Create secrets from the template (never commit the filled file)
cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml
# edit deploy/k8s/secret.yaml with real keys
kubectl apply -f deploy/k8s/secret.yaml

# 2. Apply everything else
kubectl apply -k deploy/k8s/

# 3. Verify
kubectl -n widdx get pods,svc,ingress,hpa
kubectl -n widdx rollout status deployment/widdx-nexus
```

Edit `ingress.yaml` and set your real hostname (replace
`nexus.example.com`) and the matching `WIDDX_CORS_ORIGINS` in
`configmap.yaml`.

## Health probes

The web server exposes two unauthenticated endpoints used by the
manifests (added specifically for orchestrators):

* `GET /api/livez` — liveness (process is alive)
* `GET /api/ready` — readiness (database layer reachable)

`/api/health` is also available and requires no auth.

## ⚠ Storage & replicas

WIDDX persists to SQLite under `.widdx/`. The default PVC is
`ReadWriteOnce`, meaning **only one node** can mount it. With
`replicas > 1` you must choose one:

1. **ReadWriteMany storage class** (NFS, CephFS, AWS EFS…) — set
   `accessModes: [ReadWriteMany]` in `pvc.yaml`. Simplest for
   autoscaling. Note SQLite over network FS needs care; keep WAL on a
   low-latency volume.
2. **StatefulSet** with `volumeClaimTemplates` — one volume per pod
   (data is then per-pod, not shared).
3. **Keep `replicas: 1`** in `deployment.yaml` (disable the HPA or set
   `minReplicas: 1, maxReplicas: 1`).

For a single shared database across scaled replicas, prefer option 1
with a fast, low-latency RWX backend, or front a single writer with
read replicas at the application level.

## Security hardening notes

The Deployment already sets:

* `runAsNonRoot` / `runAsUser: 1000` (image runs as `widdx`)
* `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`
* `seccompProfile: RuntimeDefault`
* namespace `pod-security.kubernetes.io/enforce: restricted`

To go further, set `readOnlyRootFilesystem: true` on the container —
the writable paths (`/workspace/.widdx` via the PVC and `/tmp` via an
`emptyDir`) are already mounted as volumes, so the app keeps working.
It is left `false` by default for maximum compatibility; enable it
after a smoke test in your environment.

## Optional: multi-tenant mode

Set in `configmap.yaml` / `secret.yaml`:

```yaml
WIDDX_TENANT_MODE: "keymap"
WIDDX_TENANT_KEYS: "acme:key-1,globex:key-2"
```

Each tenant then gets a physically isolated SQLite database under
`.widdx/data/tenants/<tenant>/widdx.db` (see `core/tenancy.py`).
