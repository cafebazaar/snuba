import os

env = os.environ.get

DEBUG = env("DEBUG", "0").lower() in ("1", "true")

DEFAULT_BROKERS = env("DEFAULT_BROKERS", "localhost:9092").split(",")

REDIS_HOST = env("REDIS_HOST", "localhost")
REDIS_PORT = int(env("REDIS_PORT", 6379))
REDIS_PASSWORD = env("REDIS_PASSWORD")
REDIS_DB = int(env("REDIS_DB", 1))
USE_REDIS_CLUSTER = False

EVENTS_TOPIC = env("EVENTS_TOPIC", "events")
REPLACEMENTS_TOPIC = env("REPLACEMENT_TOPIC", "event-replacements")
COMMIT_LOG_TOPIC = env("COMMIT_LOG_TOPIC", "snuba-commit-logs")
CDC_TOPIC = env("CDC_TOPIC", "cdc")
OUTCOMES_TOPIC = env("OUTCOMES_TOPIC", "outcomes")
INGEST_SESSIONS_TOPIC = env("INGEST_SESSION_TOPIC", "ingest-sessions")

# Dogstatsd Options
DOGSTATSD_HOST = os.getenv("DOGSTATSD_HOST")
DOGSTATSD_PORT = os.getenv("DOGSTATSD_PORT")

SENTRY_DSN = os.getenv("SENTRY_DSN")
