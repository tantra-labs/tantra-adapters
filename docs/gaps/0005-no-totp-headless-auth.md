# Gap 0005 — No TOTP / Headless Authentication Flow

## What's Missing

The `vyapaar-adapters` AGENTS.md lists "Headless authentication support (TOTP)" as a
primary responsibility, but **no TOTP implementation exists**. There is no module for
time-based one-time password generation, no login/session flow, and no token refresh.

Broker adapters require the caller to pre-provide `api_key`, `access_token`,
`client_id`, and `api_secret` via `BrokerCredentials`. There is no code that performs
the initial OAuth/login handshake or TOTP-based 2FA that Indian brokers (Zerodha Kite,
Angel One SmartAPI, Upstox, etc.) require.

## Why It Matters

Without headless auth, every adapter instance must be manually authenticated outside
Vyapaar (copy-pasting tokens). This blocks unattended execution, containerized
deployment, and the `vyapaar-exec`/strategy automation that depends on adapters
obtaining and refreshing their own tokens.

## How to Close

1. Add `vyapaar_adapters/common/auth.py` with a TOTP generator (`pyotp`-compatible or
   stdlib `hmac`/`hashlib`/`time`).
2. Add per-broker `login()` / `authenticate()` methods that perform the broker's
   OAuth/2FA flow and populate `BrokerCredentials.access_token`.
3. Add token-refresh logic (expiry tracking, refresh before 401).
4. Add contract tests with `MockTransport` simulating login challenge/response.
5. Document credential storage guidance (environment variables, never commit secrets).

See `docs/plans/0002-complete-broker-contract-certification.md` for the tracking plan.
