# contx

Git for context. Append-only logs of *why* each file and function exists, written by AI coding agents as they edit and read by AI agents when explaining code to humans.

See `docs/specs/2026-05-21-contx-design.md` for the full design.

## Quickstart

```bash
pip install -e .[dev]
contx init
contx show src/foo.py::bar
```
