# Creating the databases (PostgreSQL 18.6)

All commands were run on the database machine.

## 1. Generate the TPC-H data (tpch-kit, dbgen 2.17.3)

```sh
cd tpch-kit/dbgen
DSS_PATH=data/sf0.1 ./dbgen -s 0.1 -f
DSS_PATH=data/sf1   ./dbgen -s 1   -f
```

## 2. Databases with the original TPC-H names (`tpch_sf01`, `tpch_sf1`)

Only `tpch_sf01` is used, by the self-test (`python measure/cli.py selftest --db tpch_sf01`).

```sh
db=tpch_sf01; cd data/sf0.1      # same for tpch_sf1 with data/sf1
createdb "$db"
psql -d "$db" -f tpch-kit/dbgen/dss.ddl
for t in region nation supplier customer part partsupp orders lineitem; do
  sed 's/|$//' $t.tbl | psql -d "$db" -c "\copy $t from stdin with (delimiter '|')"
done
psql -d "$db" -f repo/setup/keys.sql
```

## 3. Anonymized databases used for the measurements (`tpch_sf01_anon`, `tpch_sf1_anon`)

The data is loaded directly into the anonymized schema (same column order as TPC-H),
parents before children because of the foreign keys:

```sh
db=tpch_sf01_anon; cd data/sf0.1  # same for tpch_sf1_anon with data/sf1
createdb "$db"
psql -d "$db" -f repo/queries/schema_anon.sql
for pair in region:tbl_zones nation:tbl_countries supplier:tbl_suppliers \
            customer:tbl_customers part:tbl_parts partsupp:tbl_part_suppliers \
            orders:tbl_orders lineitem:tbl_items; do
  src=${pair%%:*}; dst=${pair##*:}
  sed 's/|$//' $src.tbl | psql -d "$db" -c "\copy $dst from stdin with (delimiter '|')"
done
psql -d "$db" -f repo/setup/anonymize_values.sql
```

## 4. Database with foreign-key indexes (`tpch_sf01_idx`)

```sh
createdb tpch_sf01_idx -T tpch_sf01_anon
psql -d tpch_sf01_idx -f repo/setup/indexes.sql
```

## 5. Server settings

See `setup/pg_config.txt`: `shared_buffers = 2GB`, `jit = off`, all other parameters at their defaults.