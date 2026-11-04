# `vyapaar-adapters` Agent Guidelines & Architecture Invariants

**Subsystem**: Adapters (Broker REST & WebSocket Python Adapters)
**Language**: Python
**Primary Responsibility**: Production Python client wrappers for Indian brokers: Zerodha Kite, Upstox, Angel One, and Dhan.

---

## 1. Role & Architectural Hints
* `vyapaar-adapters` implements broker-specific communication protocols:
  1. Standardizes broker API responses into canonical types (`Bar`, `Order`, `Position`, `Margin`).
  2. Headless authentication support (TOTP).
  3. Paper-trading mock harnesses with fixture recording for deterministic CI testing.
* **Idea Inheritance**:
  - **OpenAlgo / DhanHQ-py / KiteConnect**: Modern idiomatic Python broker clients.

---

## 2. Coding Guidelines (DDD & TDD)
* **PEP 621 Standard**: Modern `pyproject.toml` configuration; managed with `uv` or `pip`.
* **Type Safety**: Strictly enforced type annotations (`pyright` / `mypy` strict mode).
* **Zero Floats Policy**: Decimals (`decimal.Decimal`) for all financial values.
* **TDD & Parallel Test Directory Rule (MANDATORY)**:
  - Tests live in `tests/` parallel to `src/` (e.g. `tests/test_dhan.py`, `tests/test_zerodha.py`).
* **Check .agents/HANDOFF.md**: Review pending adapter migrations and contract status.

---

## 3. Development & CI Workflow
* **Linting & Formatting**:
  ```bash
  ruff check .
  ruff format --check .
  ```
* **Testing**:
  ```bash
  pytest -q -rs
  ```
