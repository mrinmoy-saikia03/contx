from contx.summarizers.kubernetes import summarize_kubernetes


def test_summarize_deployment():
    yaml_text = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-api
  namespace: prod
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: auth-api
          image: registry/auth-api:latest
          ports:
            - containerPort: 8080
"""
    entries = summarize_kubernetes(yaml_text, "k8s/auth.yaml")
    assert len(entries) == 1
    e = entries[0]
    assert "Deployment" in e.rationale
    assert "auth-api" in e.rationale
    assert "prod" in e.rationale
    assert "3 replicas" in e.rationale
    assert "deploy" in e.tags
    assert "auto-summary" in e.tags
    assert "kubernetes" in e.tags


def test_summarize_service():
    yaml_text = """
apiVersion: v1
kind: Service
metadata:
  name: auth-api
  namespace: prod
spec:
  selector:
    app: auth-api
  ports:
    - port: 80
      targetPort: 8080
"""
    entries = summarize_kubernetes(yaml_text, "k8s/svc.yaml")
    assert any("Service" in e.rationale for e in entries)


def test_summarize_multi_document():
    yaml_text = """
apiVersion: v1
kind: Service
metadata: {name: a, namespace: p}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: a, namespace: p}
spec:
  replicas: 2
"""
    entries = summarize_kubernetes(yaml_text, "k8s/all.yaml")
    kinds = [r for e in entries for r in [e.rationale]]
    assert any("Service" in r for r in kinds)
    assert any("Deployment" in r for r in kinds)


def test_summarize_invalid_yaml_returns_empty():
    assert summarize_kubernetes(":::: not yaml ::::", "x.yaml") == []
