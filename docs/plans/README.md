# Plans Index — `vyapaar-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- **Gaps** (`docs/gaps/XXXX-*.md`): individual missing features, stubs, or hardcoded behavior.
- **Plans** (`docs/plans/XXXX-*.md`): collections of gaps.
- When implemented, plan documents are cleaned up from `docs/plans/` and recorded in this index.
- Numbering is per-repo, sequential, never reused.

The former `docs/roadmap/` directory has been dismantled into this index: the
completed Tier 6B work lives in `docs/design/` (architecture + module
references), the remaining adapter-parity items are gaps 0001–0007 tracked by
plan 0002, and the former "Cross-Repo Integration" and "Production Hardening"
milestones are now plans 0003 and 0004.

## Active Plans

| # | Title | Target Scope | Status |
|---|-------|--------------|--------|
| [0002](0002-complete-broker-contract-certification.md) | Complete Broker Contract Certification & Adapter Parity | `vyapaar_adapters` (all 7 brokers) | Ready — tracks gaps 0001–0007 (Phases A–D, incl. improvements) |
| [0003](0003-cross-repo-integration.md) | Cross-Repo Integration (Python Adapters ↔ Rust Core) | `vyapaar-adapters` + `vyapaar-market` / `vyapaar-exec` / `vyapaar-ledger` | Proposed |
| [0004](0004-production-hardening.md) | Production Hardening (Transport & Auth Reliability) | `vyapaar_adapters` | Proposed |

## Implemented Plans

| # | Title | Target Scope | Implemented In |
|---|-------|--------------|----------------|
| 0001 | Clarifying the Python/Rust Broker Adapter Boundary | `vyapaar-adapters` | Resolved & settled in commit `4f497aa` (Python adapters dev/research-only; Rust production path) |
