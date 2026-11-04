# `vyapaar-adapters` — Subagent Migration & DDD Refactoring Guide

> **Tier**: Tier 6B
> **Source**: `/home/pmallapp/Devel/Finance/honba-workspace/honba-adapters`
> **Target**: `/home/pmallapp/Devel/Finance/vyapaar-labs/vyapaar-adapters`

---

## 1. Migration & DDD Refactoring Steps
1. **Fix `pyproject.toml`**:
   - Remove invalid `"rust_decimal>=1.0.0"` from `vyapaar-adapters/pyproject.toml`.
   - Configure `[project.entry-points."vyapaar.adapters"]` for `dhan`, `zerodha`, `angelone`, `upstox`, `fyers`, `kotak`, `iifl`.
2. **Port Source Code**:
   - Copy `honba-workspace/honba-adapters/src/honba_adapters/*` and `src/honba_adapters_shared/*` into `vyapaar-labs/vyapaar-adapters/vyapaar_adapters/`.
   - Do **NOT** copy `.egg-info` or `__pycache__` directories.
   - Replace `honba_adapters` → `vyapaar_adapters` and `honba` → `vyapaar`.
3. **Port Tests, Configs & Examples**:
   - Copy `tests/`, `configs/`, `examples/`, `scripts/`, and `Makefile` from `honba-adapters`, updating imports to `vyapaar_adapters`.

## 2. Verification Commands
```bash
cd /home/pmallapp/Devel/Finance/vyapaar-labs/vyapaar-adapters
pytest -q
ruff check .
```
