# `vyapaar-adapters` — Migration Verification Milestone

Verification commands for the `honba-adapters → vyapaar-adapters` migration:

```bash
cd /home/pmallapp/Devel/Finance/vyapaar-labs/vyapaar-adapters
pytest -q
ruff check .
```

## Migration Milestone Status

| Milestone | Status |
|-----------|--------|
| `pyproject.toml` fixed | Complete |
| Source code ported | Complete |
| Tests, configs, examples ported | Complete |
| `pytest -q` | Passing |
| `ruff check .` | Clean |
