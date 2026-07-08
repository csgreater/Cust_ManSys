# Database Online Checklist

## Required before production

1. Fill `.env` with the production MySQL connection.
2. Set `APP_ENV=production`, `APP_SECURE_COOKIES=true`, and strong non-default passwords.
3. Run `python scripts/init_db.py` on an empty production database.
4. Run `python scripts/migrate_production_indexes.py` if the database was created before the production indexes were added.
5. Run `python scripts/check_db_ready.py`.
6. Confirm the application starts and `/healthz` plus `/readyz` return `200`.
7. Change the default seeded passwords after first login if they were not customized through `.env`.

## Existing database migrations

If the production database was already created before the county/district field was added, run:

```bash
python scripts/migrate_add_district.py
python scripts/check_db_ready.py
```

Equivalent SQL:

```sql
ALTER TABLE t_order_sku_detail
  ADD COLUMN district VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'district/county'
  AFTER city;

ALTER TABLE tmp_order_import
  ADD COLUMN district VARCHAR(64) NOT NULL DEFAULT ''
  AFTER city;
```

Run the SQL only if the columns do not already exist. The script is idempotent and safer for repeated execution.

If the production database was already created before the receiver address field was added, run:

```bash
python scripts/migrate_add_receiver_address.py
python scripts/check_db_ready.py
```

Equivalent SQL:

```sql
ALTER TABLE t_order_sku_detail
  ADD COLUMN receiver_address VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'receiver address'
  AFTER receiver_name;

ALTER TABLE tmp_order_import
  ADD COLUMN receiver_address VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'receiver address'
  AFTER receiver_name;
```

## Recommended MySQL settings

For a low-concurrency monthly import workload, start with:

```ini
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
innodb_file_per_table = 1
innodb_buffer_pool_size = 50%-70% of available RAM
innodb_flush_log_at_trx_commit = 2
innodb_log_buffer_size = 64M
bulk_insert_buffer_size = 256M
max_allowed_packet = 256M
```

Keep binary logging enabled if the production server needs point-in-time recovery or replication. Disable it only when backup and recovery requirements explicitly allow that tradeoff.

## Monthly maintenance

Run this before the next import window:

```bash
python scripts/ensure_future_partitions.py
python scripts/check_db_ready.py
```

The table keeps all historical partitions. Do not drop partitions for cleanup.

## Backup

- After every monthly import: export the imported month to CSV or object storage.
- Daily or weekly: full MySQL backup.
- Periodically: test restore on another machine.

## Query rule

All operational queries must include a `ship_time` range so MySQL can prune monthly partitions.
