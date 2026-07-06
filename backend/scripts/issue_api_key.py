"""
AuraMatch AI - API Key Issuance
There's no admin auth/UI yet (that's a separate, not-yet-built roadmap
phase), so this CLI script is the right-sized tool for "an operator hands a
partner a key" today: generates a random secret, prints it exactly once,
and stores only its hash (see migration 0004_api_keys, app/api/auth.py).

Usage:
  python scripts/issue_api_key.py --type publishable --label "Web frontend" --origin http://localhost:3000
  python scripts/issue_api_key.py --type secret --label "Acme Corp integration" --rate-limit 300
"""
import argparse
import asyncio
import hashlib
import os
import secrets
import sys

import asyncpg

PREFIX_BY_TYPE = {"publishable": "pk_live_", "secret": "sk_live_"}


def generate_key(key_type: str) -> str:
    return PREFIX_BY_TYPE[key_type] + secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def issue(conn_string: str, key_type: str, label: str, origins: list[str] | None, rate_limit: int) -> None:
    if key_type == "publishable" and not origins:
        print("Error: --origin is required for publishable keys (they're restricted by Origin, "
              "see app/api/auth.py). Use --type secret for server-to-server integrations instead.",
              file=sys.stderr)
        sys.exit(1)

    raw_key = generate_key(key_type)
    key_prefix = raw_key[:12]

    conn = await asyncpg.connect(conn_string)
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO api_keys (key_prefix, key_hash, label, key_type, allowed_origins, rate_limit_per_minute)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            key_prefix, hash_key(raw_key), label, key_type, origins, rate_limit,
        )
    finally:
        await conn.close()

    print(f"Issued {key_type} key #{row['id']} ({label!r}):")
    print(f"\n  {raw_key}\n")
    print("This is the only time the raw key is shown - only its hash is stored. "
          "Save it now; it cannot be recovered later (only revoked and reissued).")


def main() -> None:
    parser = argparse.ArgumentParser(description="AuraMatch AI - Issue an API key")
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL",
                        "postgresql://auramatch:auramatch_secret@localhost:5434/auramatch"))
    parser.add_argument("--type", choices=["publishable", "secret"], required=True)
    parser.add_argument("--label", required=True, help="Human-readable description, e.g. 'Web frontend'")
    parser.add_argument("--origin", action="append", default=None,
                        help="Allowed Origin (repeatable) - required for --type publishable")
    parser.add_argument("--rate-limit", type=int, default=60, help="Requests per minute (default: 60)")
    args = parser.parse_args()

    asyncio.run(issue(args.dsn, args.type, args.label, args.origin, args.rate_limit))


if __name__ == "__main__":
    main()
