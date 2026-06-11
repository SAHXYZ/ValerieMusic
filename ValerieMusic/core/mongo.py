"""
Database brain for ValerieMusic.

MongoDB is the PRIMARY datastore. It is the natural fit for this codebase (every
call site speaks Mongo: ``find_one``, ``update_one`` with ``$set``, cursors with
``.to_list()`` …) and, when pointed at a cloud MongoDB such as Atlas, your data
lives off the VPS — so if the VPS ever expires you keep every user and group and
simply redeploy against the same ``MONGO_DB_URI``.

MySQL is now OPTIONAL and serves two roles:

* If ``MONGO_DB_URI`` is **set**  → MongoDB is primary; if MySQL is also
  configured, every write is additionally mirrored to MySQL as a **local backup**
  (best-effort, never blocks or breaks the bot).
* If ``MONGO_DB_URI`` is **not set** → the bot falls back to the MySQL-backed
  Mongo-compatible layer (``core/mysql.py``) as the primary, exactly like before.

Every existing ``from ValerieMusic.core.mongo import mongodb`` import keeps
working unchanged — ``mongodb`` is always a Mongo-compatible handle regardless of
which backend is primary.
"""

from config import MONGO_DB_URI, MONGO_DB_NAME

from ..logging import LOGGER
from . import mysql as _mysql

# Pull the optional MySQL handle (None if MySQL is unavailable / not configured).
_mysql_db = getattr(_mysql, "mysql_db", None)
_mysql_enabled = bool(getattr(_mysql, "MYSQL_ENABLED", False)) and _mysql_db is not None


# ---------------------------------------------------------------------------
# MySQL backup mirror helpers (used only when MongoDB is primary AND MySQL is
# configured). All mirroring is best-effort: failures are logged and swallowed
# so the backup can never stall or crash the bot.
# ---------------------------------------------------------------------------

import asyncio


def _mirror(coro):
    if not _mysql_enabled:
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if not loop.is_running():
        return
    asyncio.ensure_future(_mirror_guard(coro))


async def _mirror_guard(coro):
    try:
        await coro
    except Exception as err:  # noqa: BLE001
        LOGGER(__name__).warning(f"MySQL backup write failed (ignored): {err}")


# ---------------------------------------------------------------------------
# Thin proxy over motor that mirrors writes to MySQL. Reads and any other motor
# feature pass straight through untouched.
# ---------------------------------------------------------------------------

class _CollectionProxy:
    def __init__(self, motor_collection, name: str):
        self._c = motor_collection
        self._name = name

    # --- reads & anything else: passthrough to motor ---
    def __getattr__(self, item):
        return getattr(self._c, item)

    def find(self, *args, **kwargs):
        return self._c.find(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return await self._c.find_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return await self._c.count_documents(*args, **kwargs)

    # --- writes: do on Mongo first, then mirror to MySQL backup ---
    async def insert_one(self, document, **kwargs):
        result = await self._c.insert_one(document, **kwargs)
        if _mysql_enabled:
            _mirror(_mysql_db[self._name].insert_one(dict(document)))
        return result

    async def update_one(self, query, update, upsert: bool = False, **kwargs):
        result = await self._c.update_one(query, update, upsert=upsert, **kwargs)
        if _mysql_enabled:
            _mirror(
                _mysql_db[self._name].update_one(dict(query or {}), update, upsert=upsert)
            )
        return result

    async def delete_one(self, query, **kwargs):
        result = await self._c.delete_one(query, **kwargs)
        if _mysql_enabled:
            _mirror(_mysql_db[self._name].delete_one(dict(query or {})))
        return result

    async def delete_many(self, query, **kwargs):
        result = await self._c.delete_many(query, **kwargs)
        if _mysql_enabled:
            _mirror(_mysql_db[self._name].delete_many(dict(query or {})))
        return result


class _DatabaseProxy:
    def __init__(self, motor_db):
        self._db = motor_db

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return _CollectionProxy(self._db[name], name)

    def __getitem__(self, name):
        return _CollectionProxy(self._db[name], name)

    async def command(self, *args, **kwargs):
        return await self._db.command(*args, **kwargs)


# ---------------------------------------------------------------------------
# Pick the primary backend.
# ---------------------------------------------------------------------------

mongodb = None

if MONGO_DB_URI:
    LOGGER(__name__).info("Connecting to your Mongo Database...")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        _mongo_client = AsyncIOMotorClient(MONGO_DB_URI)
        _mongo_db = _mongo_client[MONGO_DB_NAME]
        mongodb = _DatabaseProxy(_mongo_db)
        LOGGER(__name__).info("Connected to your Mongo Database.")
        if _mysql_enabled:
            LOGGER(__name__).info(
                "MySQL detected — it will receive a live local backup of every write."
            )
        else:
            LOGGER(__name__).info("Running on MongoDB only (no MySQL backup configured).")
    except Exception as err:  # noqa: BLE001
        LOGGER(__name__).error(f"Failed to connect to your Mongo Database. {err}")
        if _mysql_enabled:
            LOGGER(__name__).warning("Falling back to MySQL as the primary datastore.")
            mongodb = _mysql_db
        else:
            exit()
else:
    # No Mongo URI: use the MySQL-backed Mongo-compatible layer as primary.
    if _mysql_enabled:
        LOGGER(__name__).info(
            "MONGO_DB_URI not set — using MySQL as the primary datastore."
        )
        mongodb = _mysql_db
    else:
        LOGGER(__name__).error(
            "No database configured. Set MONGO_DB_URI (recommended) or MySQL "
            "credentials in your .env. Exiting..."
        )
        exit()


# ---------------------------------------------------------------------------
# One-time startup sync: when both backends are configured, seed the MySQL
# backup with any data that already exists in MongoDB but not yet in MySQL.
# Best-effort — never raises. Call this from __main__'s init() after the loop
# is running (it is safe to call even if disabled; it just returns).
# ---------------------------------------------------------------------------

async def sync_backup():
    if not (MONGO_DB_URI and _mysql_enabled and isinstance(mongodb, _DatabaseProxy)):
        return
    try:
        names = await _mongo_db.list_collection_names()
    except Exception as err:  # noqa: BLE001
        LOGGER(__name__).warning(f"MySQL backup sync skipped (ignored): {err}")
        return

    copied_total = 0
    for name in names:
        try:
            target = _mysql_db[name]
            # Only seed collections that are empty in the MySQL backup.
            if await target.count_documents({}) > 0:
                continue
            docs = await _mongo_db[name].find({}).to_list(length=None)
            for doc in docs:
                doc.pop("_id", None)  # let MySQL assign its own auto _id
                await target.insert_one(dict(doc))
                copied_total += 1
        except Exception as err:  # noqa: BLE001
            LOGGER(__name__).warning(f"MySQL backup sync skipped '{name}': {err}")
    if copied_total:
        LOGGER(__name__).info(
            f"MySQL backup initial sync complete ({copied_total} docs)."
        )


__all__ = ["mongodb", "sync_backup"]
