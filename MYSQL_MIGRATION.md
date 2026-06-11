# Database Setup (ValerieMusic)

**MongoDB is the primary datastore. MySQL is an optional local backup.**

## Why MongoDB is primary

This codebase is Mongo-native end to end (`find_one`, `update_one` with `$set`,
cursors with `.to_list()`). MongoDB stores these documents directly, with real
indexes on the fields you query. If you use a cloud MongoDB (e.g. **Atlas**),
your data lives **off the VPS** — so if the VPS ever expires, you keep every
user and group and just redeploy against the same `MONGO_DB_URI`.

## Configuration (`.env`)

```env
# PRIMARY (required)
MONGO_DB_URI=mongodb+srv://user:pass@cluster.mongodb.net   # or mongodb://localhost:27017
MONGO_DB_NAME=ValerieMusic

# OPTIONAL local backup — leave MYSQL_HOST blank to run on MongoDB only
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=@VALERIEMSC121@
MYSQL_DB=ValerieMusic
```

## How it behaves

| `.env` | Result |
|--------|--------|
| Only `MONGO_DB_URI` set | Runs on **MongoDB only**. |
| `MONGO_DB_URI` + `MYSQL_HOST` set | **MongoDB primary**; every write is also mirrored to MySQL as a live local backup. On startup, existing Mongo data is copied into any empty MySQL tables (one-time seed). |
| Only `MYSQL_HOST` set (no Mongo URI) | Falls back to the **MySQL-backed** Mongo-compatible layer as primary (backward compatible). |
| Neither set | The bot logs an error and exits. |

The MySQL mirror is **best-effort**: writes are fire-and-forget background
tasks, and any MySQL failure is logged and ignored. A slow or down MySQL can
never stall or crash the bot.

## Code map

- `ValerieMusic/core/mongo.py` — the brain: picks the primary backend and, when
  MongoDB is primary, wraps collections in a thin proxy that mirrors writes to
  MySQL. Exposes `mongodb` (used everywhere) and `sync_backup()`.
- `ValerieMusic/core/mysql.py` — the optional MySQL document store (a
  Mongo-compatible layer over MySQL). Exposes `mysql_db` / `MYSQL_ENABLED`.

Every `from ValerieMusic.core.mongo import mongodb` import keeps working
unchanged regardless of which backend is active.

## Dependencies

`requirements.txt` includes `motor` + `dnspython` (MongoDB) and `aiomysql`
(optional MySQL backup).
