# Database Online Checklist

## Required before production

1. Fill `.env` with the production MySQL connection.
2. Set `APP_ENV=production`, `APP_SECURE_COOKIES=true`, and strong non-default passwords.
3. Run `python scripts/init_db.py` on an empty production database.
4. Run `python scripts/migrate_production_indexes.py` if the database was created before the production indexes were added.
5. Run the analytics aggregate migrations on databases that already contain order data:

   ```bash
   python scripts/migrate_analytics_aggregates.py
   python scripts/migrate_dashboard_aggregates.py
   ```

6. Run `python scripts/check_db_ready.py`.
7. Confirm the application starts and `/healthz` plus `/readyz` return `200`.
8. Change the default seeded passwords after first login if they were not customized through `.env`.

The aggregate migrations are idempotent. They rebuild monthly product analytics,
global daily/monthly dashboard metrics, and monthly platform metrics from
`t_order_sku_detail`. New committed imports refresh only their affected months.
Keep the application stopped during the first backfill on a low-memory server.

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
python scripts/migrate_import_performance_indexes.py
python scripts/migrate_widen_order_text_fields.py
python scripts/migrate_import_rule_changes.py
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

ALTER TABLE tmp_order_import
  ADD INDEX idx_import_duplicate (batch_no, order_no, ship_time, sku_id, product_no);

ALTER TABLE t_order_sku_detail
  MODIFY COLUMN order_no VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'order number',
  MODIFY COLUMN original_order_no VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'original order number',
  MODIFY COLUMN receiver_address VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'receiver address';

ALTER TABLE tmp_order_import
  MODIFY COLUMN order_no VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'order number',
  MODIFY COLUMN original_order_no VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'original order number',
  MODIFY COLUMN receiver_address VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'receiver address';

ALTER TABLE t_import_log
  ADD COLUMN file_hash VARCHAR(64) NOT NULL DEFAULT '' AFTER duplicate_rows,
  ADD INDEX idx_file_hash_status (file_hash, status);

ALTER TABLE t_order_sku_detail
  DROP INDEX uk_order_sku_product_time,
  ADD INDEX idx_order_sku_product_time (order_no, sku_id, product_no, ship_time);
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
