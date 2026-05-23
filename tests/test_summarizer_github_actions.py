from contx.summarizers.github_actions import summarize_github_actions


def test_summarize_workflow():
    yaml_text = """
name: CI
on:
  push:
    branches: [main]
  pull_request: {}
jobs:
  test:
    runs-on: ubuntu-latest
    steps: []
  build:
    runs-on: ubuntu-latest
    steps:
      - name: secret
        run: echo ${{ secrets.NPM_TOKEN }}
"""
    entries = summarize_github_actions(yaml_text, ".github/workflows/ci.yml")
    assert len(entries) == 1
    e = entries[0]
    assert "CI" in e.rationale
    assert "2 jobs" in e.rationale
    assert "push" in e.rationale
    assert "NPM_TOKEN" in e.rationale
    assert "github-actions" in e.tags


def test_summarize_invalid_returns_empty():
    assert summarize_github_actions("::::", "x.yml") == []
