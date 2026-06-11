"""
MySQL backend for ValerieMusic.

This module replaces the previous MongoDB (motor) backend. To avoid rewriting
the ~40 call sites scattered across utils/database.py, misc.py and the plugins,
it exposes a tiny *Mongo-compatible* layer on top of MySQL:

    mongodb.<collection>.find_one(query)
    mongodb.<collection>.find(query)            -> async cursor
    mongodb.<collection>.insert_one(document)
    mongodb.<collection>.update_one(query, {"$set": {...}}, upsert=True)
    mongodb.<collection>.delete_one(query)
    mongodb.<collection>.count_documents(query)
    mongodb.command("dbstats")

Each "collection" is a MySQL table with two columns:
    _id   BIGINT AUTO_INCREMENT PRIMARY KEY
    doc   JSON                        (the whole document, stored as JSON)

Filtering is done with MySQL's JSON_EXTRACT / JSON_UNQUOTE so the supported
Mongo query operators ($gt, $lt, plain equality) keep working exactly as the
old code expected. This keeps the public surface identical to the old
`from ValerieMusic.core.mongo import mongodb` import, so nothing else needs to
change in terms of query syntax.
"""

import asyncio
import json

import aiomysql

from config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DB,
)

from ..logging import LOGGER

# Holds the shared connection pool (initialised lazily on first use).
_pool: "aiomysql.Pool | None" = None
_pool_lock = asyncio.Lock()


def _coerce(value):
    """Make a value JSON-serialisable and comparison-friendly."""
    return value


async def _get_pool() -> "aiomysql.Pool":
    """Return the shared aiomysql pool, creating it on first call."""
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await aiomysql.create_pool(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                db=MYSQL_DB,
                autocommit=True,
                charset="utf8mb4",
                minsize=1,
                maxsize=10,
                pool_recycle=3600,
            )
    return _pool


def _safe_table(name: str) -> str:
    """Sanitise a collection name so it is a valid, safe MySQL table name."""
    cleaned = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
    if not cleaned:
        cleaned = "col"
    if cleaned[0].isdigit():
        cleaned = "c_" + cleaned
    return f"col_{cleaned}"


class _Cursor:
    """Async iterable returned by Collection.find(), mimicking motor's cursor."""

    def __init__(self, collection: "Collection", query: dict):
        self._collection = collection
        self._query = query or {}
        self._rows: "list[dict] | None" = None
        self._index = 0

    async def _ensure(self):
        if self._rows is None:
            self._rows = await self._collection._find_many(self._query)

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._ensure()
        if self._index >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._index]
        self._index += 1
        return row

    async def to_list(self, length: "int | None" = None):
        await self._ensure()
        if length is None:
            return list(self._rows)
        return list(self._rows[:length])


class Collection:
    """A Mongo-compatible collection backed by a single MySQL table."""

    def __init__(self, db: "Database", name: str):
        self._db = db
        self._name = name
        self._table = _safe_table(name)
        self._ready = False
        self._ready_lock = asyncio.Lock()

    async def _ensure_table(self):
        if self._ready:
            return
        async with self._ready_lock:
            if self._ready:
                return
            pool = await _get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Suppress the benign "table already exists" warning that can
                    # occur when two coroutines create the same table concurrently.
                    import warnings as _w
                    with _w.catch_warnings():
                        _w.simplefilter("ignore")
                        await cur.execute(
                            f"CREATE TABLE IF NOT EXISTS `{self._table}` ("
                            "  `_id` BIGINT AUTO_INCREMENT PRIMARY KEY,"
                            "  `doc` JSON NOT NULL"
                            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                        )
            self._ready = True

    # ---- query building -------------------------------------------------

    @staticmethod
    def _build_where(query: dict):
        """
        Translate a (subset of) Mongo query dict into a SQL WHERE clause plus
        parameters. Supports equality and the $gt / $lt / $gte / $lte / $ne
        operators, which is everything the ValerieMusic codebase uses.
        """
        if not query:
            return "1=1", []

        clauses = []
        params = []
        for field, condition in query.items():
            path = f"$.{field}"
            extract = f"JSON_UNQUOTE(JSON_EXTRACT(doc, %s))"
            if isinstance(condition, dict):
                for op, value in condition.items():
                    if op == "$gt":
                        clauses.append(f"CAST({extract} AS SIGNED) > %s")
                        params.extend([path, value])
                    elif op == "$lt":
                        clauses.append(f"CAST({extract} AS SIGNED) < %s")
                        params.extend([path, value])
                    elif op == "$gte":
                        clauses.append(f"CAST({extract} AS SIGNED) >= %s")
                        params.extend([path, value])
                    elif op == "$lte":
                        clauses.append(f"CAST({extract} AS SIGNED) <= %s")
                        params.extend([path, value])
                    elif op == "$ne":
                        clauses.append(f"{extract} <> %s")
                        params.extend([path, str(value)])
                    else:
                        # Unsupported operator -> fall back to equality on raw
                        clauses.append(f"{extract} = %s")
                        params.extend([path, str(value)])
            else:
                # Plain equality. Compare as text (JSON_UNQUOTE) which works for
                # both numeric and string scalar values used in this codebase.
                clauses.append(f"{extract} = %s")
                params.extend([path, str(condition)])

        return " AND ".join(clauses), params

    # ---- internal helpers ----------------------------------------------

    async def _find_many(self, query: dict):
        await self._ensure_table()
        where, params = self._build_where(query)
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT doc FROM `{self._table}` WHERE {where}", params
                )
                rows = await cur.fetchall()
        results = []
        for (doc,) in rows:
            results.append(self._load(doc))
        return results

    @staticmethod
    def _load(doc):
        if isinstance(doc, (dict, list)):
            return doc
        return json.loads(doc)

    # ---- public Mongo-compatible API ------------------------------------

    async def find_one(self, query: dict = None):
        await self._ensure_table()
        where, params = self._build_where(query or {})
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT doc FROM `{self._table}` WHERE {where} LIMIT 1",
                    params,
                )
                row = await cur.fetchone()
        if not row:
            return None
        return self._load(row[0])

    def find(self, query: dict = None):
        # Returns a cursor (NOT awaited) just like motor.
        return _Cursor(self, query or {})

    async def insert_one(self, document: dict, _mirror: bool = True):
        await self._ensure_table()
        payload = json.dumps(document, default=str)
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"INSERT INTO `{self._table}` (doc) VALUES (%s)",
                    (payload,),
                )
                insert_id = cur.lastrowid
        return _InsertOneResult(insert_id)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        await self._ensure_table()
        set_doc = update.get("$set", {}) if isinstance(update, dict) else {}

        existing = await self.find_one(query)
        pool = await _get_pool()

        if existing is not None:
            merged = dict(existing)
            merged.update(set_doc)
            where, params = self._build_where(query)
            payload = json.dumps(merged, default=str)
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"UPDATE `{self._table}` SET doc = %s "
                        f"WHERE {where} LIMIT 1",
                        [payload, *params],
                    )
            return _UpdateResult(matched=1, modified=1)

        if upsert:
            # Seed the new document with the equality fields from the query.
            new_doc = {}
            for field, condition in (query or {}).items():
                if not isinstance(condition, dict):
                    new_doc[field] = condition
            new_doc.update(set_doc)
            await self.insert_one(new_doc)
            return _UpdateResult(matched=0, modified=0, upserted=True)

        return _UpdateResult(matched=0, modified=0)

    async def delete_one(self, query: dict):
        await self._ensure_table()
        where, params = self._build_where(query)
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM `{self._table}` WHERE {where} LIMIT 1", params
                )
                deleted = cur.rowcount
        return _DeleteResult(deleted)

    async def delete_many(self, query: dict):
        await self._ensure_table()
        where, params = self._build_where(query)
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"DELETE FROM `{self._table}` WHERE {where}", params
                )
                deleted = cur.rowcount
        return _DeleteResult(deleted)

    async def count_documents(self, query: dict = None):
        await self._ensure_table()
        where, params = self._build_where(query or {})
        pool = await _get_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT COUNT(*) FROM `{self._table}` WHERE {where}", params
                )
                row = await cur.fetchone()
        return int(row[0]) if row else 0


class _InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.acknowledged = True


class _UpdateResult:
    def __init__(self, matched=0, modified=0, upserted=False):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = 1 if upserted else None
        self.acknowledged = True


class _DeleteResult:
    def __init__(self, deleted=0):
        self.deleted_count = deleted
        self.acknowledged = True


class Database:
    """
    Mongo-compatible database handle. Accessing an attribute (e.g.
    `mongodb.sudoers`) lazily returns a Collection wrapping a MySQL table,
    exactly like motor's `mongodb.sudoers` returned a collection.
    """

    def __init__(self):
        self._collections: "dict[str, Collection]" = {}

    def _get_collection(self, name: str) -> Collection:
        col = self._collections.get(name)
        if col is None:
            col = Collection(self, name)
            self._collections[name] = col
        return col

    def __getattr__(self, name: str) -> Collection:
        # Only called for attributes not found normally; avoids recursion on
        # internal attributes (which are set in __init__).
        if name.startswith("_"):
            raise AttributeError(name)
        return self._get_collection(name)

    def __getitem__(self, name: str) -> Collection:
        return self._get_collection(name)

    async def command(self, command_name, *args, **kwargs):
        """
        Minimal emulation of MongoDB's db.command(). Only "dbstats" is used in
        this codebase (plugins/tools/stats.py), which reads dataSize/storageSize.
        We return the equivalent MySQL figures (in bytes) so the existing
        `call["dataSize"] / 1024` style maths keeps producing sensible numbers.
        """
        cmd = command_name
        if isinstance(command_name, dict):
            cmd = next(iter(command_name), "")
        if str(cmd).lower() == "dbstats":
            pool = await _get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT "
                        "  COALESCE(SUM(data_length), 0), "
                        "  COALESCE(SUM(data_length + index_length), 0) "
                        "FROM information_schema.tables "
                        "WHERE table_schema = %s",
                        (MYSQL_DB,),
                    )
                    row = await cur.fetchone()
            data_size = int(row[0]) if row else 0
            storage_size = int(row[1]) if row else 0
            return {
                "db": MYSQL_DB,
                "dataSize": data_size,
                "storageSize": storage_size,
                "ok": 1.0,
            }
        return {"ok": 1.0}


# ---- module-level singleton, mirroring the old `mongodb` object -------------

# Whether MySQL is configured/usable. MySQL is now OPTIONAL: it is only used
# when credentials are present (as primary if no Mongo URI, otherwise as a
# local backup mirror). If MySQL cannot be reached we disable it rather than
# killing the bot, so a MongoDB-only deployment keeps working.
MYSQL_ENABLED = False
mysql_db = None

if MYSQL_HOST:
    LOGGER(__name__).info("Connecting to your MySQL Database...")
    try:
        mysql_db = Database()

        async def _startup_check():
            """Validate connectivity once using a standalone connection.

            We deliberately avoid touching the shared pool here so the pool is
            only ever created on the bot's real event loop (lazily, at first
            query). This prevents binding the pool to a throwaway loop.
            """
            conn = await aiomysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                db=MYSQL_DB,
                charset="utf8mb4",
            )
            await conn.ping()
            conn.close()

        try:
            _loop = asyncio.get_event_loop()
            if _loop.is_running():
                LOGGER(__name__).info(
                    "Event loop already running; MySQL pool will connect lazily."
                )
            else:
                raise RuntimeError("no running loop")
        except RuntimeError:
            _probe_loop = asyncio.new_event_loop()
            try:
                _probe_loop.run_until_complete(_startup_check())
            finally:
                _probe_loop.close()

        MYSQL_ENABLED = True
        LOGGER(__name__).info("Connected to your MySQL Database.")
    except Exception as err:  # noqa: BLE001
        LOGGER(__name__).warning(
            f"MySQL not available ({err}). Continuing without MySQL."
        )
        MYSQL_ENABLED = False
        mysql_db = None

# Backward-compatible alias. Historically `from ValerieMusic.core.mysql import
# mongodb` returned the MySQL-backed handle. It is still exported so nothing
# breaks, but the active primary is now decided in `core/mongo.py`.
mongodb = mysql_db
