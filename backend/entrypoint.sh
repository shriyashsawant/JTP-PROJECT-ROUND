#!/bin/sh
# Applies any pending Alembic migrations before the app starts - required for
# "docker compose up" to be genuinely plug-and-play. Without this, a fresh
# volume gets 01_schema.sql + the pre-baked seed dump (both frozen at the
# 0001 baseline) but none of the migrations added afterward (source_priority,
# normalized_key, api_keys), and every route depending on those breaks with
# "relation does not exist" the moment a real request comes in.
#
# Safe to run on every boot, not just first install: `alembic upgrade head`
# is a no-op once the DB is already at head (the common case for the
# existing dev volume this session has been using), and correctly walks a
# genuinely fresh DB from nothing through every migration in one pass (it
# creates its own alembic_version table if none exists yet).
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
