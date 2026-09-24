"""Tests — Kubernetes Manifests validity (Task 4.4).

Ensures the deploy/k8s manifests parse as YAML and carry the fields the
cluster needs (probes, selectors, scaling bounds). Skips cleanly if PyYAML
is not installed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

yaml = pytest.importorskip("yaml")

K8S_DIR = Path(__file__).resolve().parent.parent / "deploy" / "k8s"


def load(name: str) -> dict:
    return yaml.safe_load((K8S_DIR / name).read_text(encoding="utf-8"))


def test_all_manifests_parse():
    files = sorted(K8S_DIR.glob("*.yaml"))
    assert files, "deploy/k8s should contain manifests"
    for f in files:
        docs = list(yaml.safe_load_all(f.read_text(encoding="utf-8")))
        assert docs, f"{f.name} parsed to nothing"


def test_deployment_has_probes_and_selector():
    d = load("deployment.yaml")
    assert d["kind"] == "Deployment"
    spec = d["spec"]["template"]["spec"]
    container = spec["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/api/livez"
    assert container["readinessProbe"]["httpGet"]["path"] == "/api/ready"
    assert container["startupProbe"]["httpGet"]["path"] == "/api/livez"
    # selector matches pod labels
    pod_labels = d["spec"]["template"]["metadata"]["labels"]
    for k, v in d["spec"]["selector"]["matchLabels"].items():
        assert pod_labels[k] == v
    # non-root security
    sc = container["securityContext"]
    assert sc["allowPrivilegeEscalation"] is False
    assert spec["securityContext"]["runAsNonRoot"] is True


def test_service_targets_deployment_pods():
    svc = load("service.yaml")
    dep = load("deployment.yaml")
    assert svc["kind"] == "Service"
    pod_labels = dep["spec"]["template"]["metadata"]["labels"]
    for k, v in svc["spec"]["selector"].items():
        assert pod_labels[k] == v


def test_hpa_bounds_and_target():
    h = load("hpa.yaml")
    assert h["kind"] == "HorizontalPodAutoscaler"
    assert h["spec"]["minReplicas"] >= 1
    assert h["spec"]["maxReplicas"] >= h["spec"]["minReplicas"]
    assert h["spec"]["scaleTargetRef"]["name"] == "widdx-nexus"
    kinds = {m["resource"]["name"] for m in h["spec"]["metrics"]}
    assert "cpu" in kinds


def test_ingress_has_tls_and_host():
    ing = load("ingress.yaml")
    assert ing["kind"] == "Ingress"
    assert ing["spec"]["tls"], "ingress should terminate TLS"
    assert ing["spec"]["rules"], "ingress should define rules"
    assert ing["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]["name"] == "widdx-nexus"


def test_kustomization_references_existing_files():
    k = load("kustomization.yaml")
    for res in k["resources"]:
        assert (K8S_DIR / res).exists(), f"kustomization references missing {res}"


def nginx_blocks():
    text = (K8S_DIR.parent / "nginx.conf").read_text(encoding="utf-8")
    text = re.sub(r"#.*", "", text)
    stack = []
    for token in re.findall(r"[^{};]+[{};]|[{}]", text):
        directive = token[:-1].strip()
        if token.endswith("{"):
            stack.append(directive)
        elif token.endswith("}"):
            assert stack
            stack.pop()
        else:
            yield tuple(stack), directive
    assert not stack


def test_nginx_rate_limit_zones_are_in_http_include_context():
    zones = [(context, directive) for context, directive in nginx_blocks()
             if directive.startswith("limit_req_zone ")]
    assert len(zones) == 2
    assert all(not context for context, _ in zones)
    assert any("zone=widdx_api:" in directive for _, directive in zones)
    assert any("zone=widdx_web:" in directive for _, directive in zones)


def test_nginx_routes_dashboard_and_standalone_api_separately():
    routes = {context[-1]: directive for context, directive in nginx_blocks()
              if directive.startswith("proxy_pass ")}
    assert routes["location /"] == "proxy_pass http://widdx_web"
    assert routes["location /api/"] == "proxy_pass http://widdx_web"
    assert routes["location /standalone-api/"] == "proxy_pass http://widdx_api/api/"
    assert routes["location /static/"] == "proxy_pass http://widdx_web"


def test_docker_installs_after_copying_source():
    text = (K8S_DIR.parent.parent / "Dockerfile").read_text(encoding="utf-8")
    installs = re.findall(r'^RUN pip install --no-cache-dir .*"\.\[api\]"$', text, re.MULTILINE)
    assert installs == ['RUN pip install --no-cache-dir ".[api]"']
    assert text.index("WORKDIR /opt/widdx") < text.index("COPY --chown=widdx:widdx . .")
    assert text.index("COPY --chown=widdx:widdx . .") < text.index(installs[0])
    assert 'ENTRYPOINT ["widdx-web"]' in text


def test_ci_installs_dev_and_api_extras_for_checks():
    workflow = yaml.safe_load((K8S_DIR.parent.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    for job in ("test", "lint", "typecheck", "benchmark"):
        step = next(step for step in workflow["jobs"][job]["steps"]
                    if step.get("name") == "Install dependencies")
        assert 'pip install -e ".[dev,api]"' in step["run"]
