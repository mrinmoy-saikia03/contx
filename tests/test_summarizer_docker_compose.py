from contx.summarizers.docker_compose import summarize_docker_compose


def test_summarize_services():
    yaml_text = """
version: '3'
services:
  api:
    image: my/api:latest
    depends_on: [db]
  db:
    image: postgres:15
"""
    entries = summarize_docker_compose(yaml_text, "docker-compose.yml")
    assert len(entries) == 1
    r = entries[0].rationale
    assert "api" in r
    assert "db" in r
    assert "depends_on" in r or "depends on" in r
    assert "docker-compose" in entries[0].tags


def test_summarize_invalid_returns_empty():
    assert summarize_docker_compose("::::", "x.yml") == []
