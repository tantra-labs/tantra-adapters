# Plans Index — `vyapaar-adapters`

Per workspace rule `.agents/rules/gap-tracking.md`:
- **Gaps** (`docs/gaps/XXXX-*.md`): individual missing features, stubs, or hardcoded behavior.
- **Plans** (`docs/plans/XXXX-*.md`): collections of gaps.
- When implemented, plan documents are cleaned up from `docs/plans/` and recorded in this index.
- Numbering is per-repo, sequential, never reused.

## Active Plans

| # | Title | Target Scope | Status |
|---|-------|--------------|--------|
| [0002](0002-complete-broker-contract-certification.md) | Complete Broker Contract Certification & Adapter Parity | `vyapaar_adapters` (all 7 brokers) | Open — tracks gaps 0001–0007 |

## Implemented Plans

| # | Title | Target Scope | Implemented In |
|---|-------|--------------|----------------|
| 0001 | Clarifying the Python/Rust Broker Adapter Boundary | `vyapaar-adapters` | Resolved & settled in commit `4f497aa` (Python adapters dev/research-only; Rust production path) |
