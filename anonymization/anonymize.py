"""TPC-H Query and Schema Anonymization Module.
Author: Karina B'yeha
"""
import re
from pathlib import Path
import sqlglot
from sqlglot import exp

# ============================================================
# ANONYMIZATION MAPPINGS (TABLES & COLUMNS)
# ============================================================

TABLE_MAP = {
    "customer": "tbl_customers",
    "orders": "tbl_orders",
    "lineitem": "tbl_items",
    "part": "tbl_parts",
    "partsupp": "tbl_part_suppliers",
    "supplier": "tbl_suppliers",
    "nation": "tbl_countries",
    "region": "tbl_zones",
}

COLUMN_MAP = {
    # customer
    "c_custkey": "col_c_id",
    "c_name": "col_c_name",
    "c_address": "col_c_address",
    "c_nationkey": "col_c_country_id",
    "c_phone": "col_c_phone",
    "c_acctbal": "col_c_balance",
    "c_mktsegment": "col_c_segment",
    "c_comment": "col_c_notes",
    # orders
    "o_orderkey": "col_o_id",
    "o_custkey": "col_o_customer_id",
    "o_orderstatus": "col_o_status",
    "o_totalprice": "col_o_total_amount",
    "o_orderdate": "col_o_date",
    "o_orderpriority": "col_o_priority",
    "o_clerk": "col_o_agent",
    "o_shippriority": "col_o_ship_level",
    "o_comment": "col_o_notes",
    # lineitem
    "l_orderkey": "col_l_order_id",
    "l_partkey": "col_l_part_id",
    "l_suppkey": "col_l_supplier_id",
    "l_linenumber": "col_l_item_num",
    "l_quantity": "col_l_qty",
    "l_extendedprice": "col_l_ext_price",
    "l_discount": "col_l_discount",
    "l_tax": "col_l_tax",
    "l_returnflag": "col_l_ret_flag",
    "l_linestatus": "col_l_status",
    "l_shipdate": "col_l_ship_date",
    "l_commitdate": "col_l_commit_date",
    "l_receiptdate": "col_l_receipt_date",
    "l_shipinstruct": "col_l_instruct",
    "l_shipmode": "col_l_mode",
    "l_comment": "col_l_notes",
    # part
    "p_partkey": "col_p_id",
    "p_name": "col_p_name",
    "p_mfgr": "col_p_manufacturer",
    "p_brand": "col_p_label",
    "p_type": "col_p_category",
    "p_size": "col_p_dimension",
    "p_container": "col_p_packaging",
    "p_retailprice": "col_p_price",
    "p_comment": "col_p_notes",
    # partsupp
    "ps_partkey": "col_ps_part_id",
    "ps_suppkey": "col_ps_supplier_id",
    "ps_availqty": "col_ps_available_qty",
    "ps_supplycost": "col_ps_cost",
    "ps_comment": "col_ps_notes",
    # supplier
    "s_suppkey": "col_s_id",
    "s_name": "col_s_name",
    "s_address": "col_s_address",
    "s_nationkey": "col_s_country_id",
    "s_phone": "col_s_phone",
    "s_acctbal": "col_s_balance",
    "s_comment": "col_s_notes",
    # nation
    "n_nationkey": "col_n_id",
    "n_name": "col_n_name",
    "n_regionkey": "col_n_zone_id",
    "n_comment": "col_n_notes",
    # region
    "r_regionkey": "col_r_id",
    "r_name": "col_r_name",
    "r_comment": "col_r_notes",
}

# Controlled literal shifts (C12: avoids zero row counts while altering text)
LITERAL_REPLACEMENTS = {
    # Regions
    "'MIDDLE EAST'": "'ZONE_CENTRAL'",
    "'ASIA'": "'ZONE_EAST'",
    "'EUROPE'": "'ZONE_NORTH'",
    # Market segments & Types
    "'FURNITURE'": "'SEGMENT_A'",
    "'BUILDING'": "'SEGMENT_B'",
    "'MACHINERY'": "'SEGMENT_C'",
    "'HOUSEHOLD'": "'SEGMENT_D'",
    "'AUTOMOBILE'": "'SEGMENT_E'",
}


# ============================================================
# ANONYMIZATION LOGIC
# ============================================================

def anonymize_sql(sql: str) -> str:
    """Anonymize tables, columns, subquery aliases, and literals in an SQL query using SQLGlot."""
    ast = sqlglot.parse_one(sql.strip().rstrip(";"), read="postgres")

    # 1. Rename table references (FROM and JOIN)
    for table_node in list(ast.find_all(exp.Table)):
        t_name = table_node.name.lower()
        if t_name in TABLE_MAP:
            table_node.set("this", exp.to_identifier(TABLE_MAP[t_name]))

        alias = table_node.alias
        if alias and alias.lower() in TABLE_MAP:
            table_node.set(
                "alias",
                exp.TableAlias(
                    this=exp.to_identifier(TABLE_MAP[alias.lower()])
                ),
            )

    # 2. Rename Subquery (Derived Table) aliases (e.g. AS part -> AS tbl_parts)
    for subquery in list(ast.find_all(exp.Subquery)):
        sub_alias = subquery.alias
        if sub_alias and sub_alias.lower() in TABLE_MAP:
            subquery.set(
                "alias",
                exp.TableAlias(
                    this=exp.to_identifier(TABLE_MAP[sub_alias.lower()])
                ),
            )

    # 3. Rename columns and table qualifiers
    for col_node in list(ast.find_all(exp.Column)):
        c_name = col_node.name.lower()
        if c_name in COLUMN_MAP:
            col_node.set("this", exp.to_identifier(COLUMN_MAP[c_name]))

        if col_node.table:
            tbl_qual = col_node.table.lower()
            if tbl_qual in TABLE_MAP:
                col_node.set("table", exp.to_identifier(TABLE_MAP[tbl_qual]))

    # 4. Rename column aliases that clash with old table names (e.g. 'AS nation' in Q08/Q09)
    for alias_node in list(ast.find_all(exp.Alias)):
        if alias_node.alias.lower() in TABLE_MAP:
            new_col_alias = (
                "country"
                if alias_node.alias.lower() == "nation"
                else TABLE_MAP[alias_node.alias.lower()]
            )
            alias_node.set("alias", exp.to_identifier(new_col_alias))

    # 5. Rename custom CTE names containing original table names (e.g., filtered_orders -> filtered_tbl_orders)
    for cte in list(ast.find_all(exp.CTE)):
        cte_alias = cte.alias
        for orig_t, anon_t in TABLE_MAP.items():
            if orig_t in cte_alias.lower():
                new_alias = cte_alias.lower().replace(orig_t, anon_t)
                cte.set(
                    "alias",
                    exp.TableAlias(this=exp.to_identifier(new_alias)),
                )
                for tbl in list(ast.find_all(exp.Table)):
                    if tbl.name.lower() == cte_alias.lower():
                        tbl.set("this", exp.to_identifier(new_alias))

    # Convert back to PostgreSQL SQL string
    anonymized_sql = ast.sql(dialect="postgres", pretty=True)

    # 6. Apply controlled literal substitutions (C12)
    for orig_lit, shifted_lit in LITERAL_REPLACEMENTS.items():
        anonymized_sql = anonymized_sql.replace(orig_lit, shifted_lit)

    # Clean any stray reference in outer clauses (e.g. GROUP BY nation -> GROUP BY country)
    anonymized_sql = re.sub(
        r"\bnation\b", "country", anonymized_sql, flags=re.IGNORECASE
    )

    return anonymized_sql.rstrip(";") + ";"


# ============================================================
# SCHEMA DDL GENERATOR (schema_anon.sql)
# ============================================================

ANONYMIZED_DDL = """-- Anonymized TPC-H Schema Definition (PostgreSQL)
-- Generated for INF2204 - Experiment Project Design

DROP TABLE IF EXISTS tbl_items CASCADE;
DROP TABLE IF EXISTS tbl_part_suppliers CASCADE;
DROP TABLE IF EXISTS tbl_parts CASCADE;
DROP TABLE IF EXISTS tbl_orders CASCADE;
DROP TABLE IF EXISTS tbl_customers CASCADE;
DROP TABLE IF EXISTS tbl_suppliers CASCADE;
DROP TABLE IF EXISTS tbl_countries CASCADE;
DROP TABLE IF EXISTS tbl_zones CASCADE;

CREATE TABLE tbl_zones (
    col_r_id       INTEGER PRIMARY KEY,
    col_r_name     CHAR(25) NOT NULL,
    col_r_notes    VARCHAR(152)
);

CREATE TABLE tbl_countries (
    col_n_id        INTEGER PRIMARY KEY,
    col_n_name      CHAR(25) NOT NULL,
    col_n_zone_id   INTEGER NOT NULL REFERENCES tbl_zones(col_r_id),
    col_n_notes     VARCHAR(152)
);

CREATE TABLE tbl_suppliers (
    col_s_id          INTEGER PRIMARY KEY,
    col_s_name        CHAR(25) NOT NULL,
    col_s_address     VARCHAR(40) NOT NULL,
    col_s_country_id  INTEGER NOT NULL REFERENCES tbl_countries(col_n_id),
    col_s_phone       CHAR(15) NOT NULL,
    col_s_balance     DECIMAL(15, 2) NOT NULL,
    col_s_notes       VARCHAR(101)
);

CREATE TABLE tbl_customers (
    col_c_id          INTEGER PRIMARY KEY,
    col_c_name        VARCHAR(25) NOT NULL,
    col_c_address     VARCHAR(40) NOT NULL,
    col_c_country_id  INTEGER NOT NULL REFERENCES tbl_countries(col_n_id),
    col_c_phone       CHAR(15) NOT NULL,
    col_c_balance     DECIMAL(15, 2) NOT NULL,
    col_c_segment     CHAR(10) NOT NULL,
    col_c_notes       VARCHAR(117)
);

CREATE TABLE tbl_parts (
    col_p_id            INTEGER PRIMARY KEY,
    col_p_name          VARCHAR(55) NOT NULL,
    col_p_manufacturer  CHAR(25) NOT NULL,
    col_p_label         CHAR(10) NOT NULL,
    col_p_category      VARCHAR(25) NOT NULL,
    col_p_dimension     INTEGER NOT NULL,
    col_p_packaging     CHAR(10) NOT NULL,
    col_p_price         DECIMAL(15, 2) NOT NULL,
    col_p_notes         VARCHAR(23)
);

CREATE TABLE tbl_part_suppliers (
    col_ps_part_id        INTEGER NOT NULL REFERENCES tbl_parts(col_p_id),
    col_ps_supplier_id    INTEGER NOT NULL REFERENCES tbl_suppliers(col_s_id),
    col_ps_available_qty  INTEGER NOT NULL,
    col_ps_cost           DECIMAL(15, 2) NOT NULL,
    col_ps_notes          VARCHAR(199),
    PRIMARY KEY (col_ps_part_id, col_ps_supplier_id)
);

CREATE TABLE tbl_orders (
    col_o_id            BIGINT PRIMARY KEY,
    col_o_customer_id   INTEGER NOT NULL REFERENCES tbl_customers(col_c_id),
    col_o_status        CHAR(1) NOT NULL,
    col_o_total_amount  DECIMAL(15, 2) NOT NULL,
    col_o_date          DATE NOT NULL,
    col_o_priority      CHAR(15) NOT NULL,
    col_o_agent         CHAR(15) NOT NULL,
    col_o_ship_level    INTEGER NOT NULL,
    col_o_notes         VARCHAR(79)
);

CREATE TABLE tbl_items (
    col_l_order_id      BIGINT NOT NULL REFERENCES tbl_orders(col_o_id),
    col_l_part_id       INTEGER NOT NULL,
    col_l_supplier_id   INTEGER NOT NULL,
    col_l_item_num      INTEGER NOT NULL,
    col_l_qty           DECIMAL(15, 2) NOT NULL,
    col_l_ext_price     DECIMAL(15, 2) NOT NULL,
    col_l_discount      DECIMAL(15, 2) NOT NULL,
    col_l_tax           DECIMAL(15, 2) NOT NULL,
    col_l_ret_flag      CHAR(1) NOT NULL,
    col_l_status        CHAR(1) NOT NULL,
    col_l_ship_date     DATE NOT NULL,
    col_l_commit_date   DATE NOT NULL,
    col_l_receipt_date  DATE NOT NULL,
    col_l_instruct      CHAR(25) NOT NULL,
    col_l_mode          CHAR(10) NOT NULL,
    col_l_notes         VARCHAR(44),
    PRIMARY KEY (col_l_order_id, col_l_item_num),
    FOREIGN KEY (col_l_part_id, col_l_supplier_id) REFERENCES tbl_part_suppliers(col_ps_part_id, col_ps_supplier_id)
);
"""


# ============================================================
# BATCH GENERATION PIPELINE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent  # Punta esattamente a LLMq
VARIANTS_DIR = BASE_DIR / "tpch_variants"
OUTPUT_DIR = BASE_DIR / "queries"

def generate_all_anonymized_files(
    input_dir=VARIANTS_DIR, output_dir=OUTPUT_DIR
):
    """Read the 3 structural forms generated by transformations.py,

    anonymize them, and save them in the format agreed in the schedule:
    queries/qXX_nested.sql, queries/qXX_join.sql, queries/qXX_cte.sql
    along with schema_anon.sql.
    """
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save schema_anon.sql
    schema_path = out_dir / "schema_anon.sql"
    schema_path.write_text(ANONYMIZED_DDL, encoding="utf-8")
    print(f"[SCHEMA] Generated {schema_path}")

    # 2. Map form names: schedule uses 'nested' for subquery
    form_mapping = {
        "cte": "cte",
        "join": "join",
        "subquery": "nested",  # Rasmus & Kawtar expect qXX_nested.sql
    }

    count = 0
    for q_folder in sorted(in_dir.glob("q*")):
        if not q_folder.is_dir():
            continue
        q_id = q_folder.name

        for src_form, dst_form in form_mapping.items():
            src_file = q_folder / f"{q_id}_{src_form}.sql"
            if not src_file.exists():
                print(f"[WARNING] Missing: {src_file}")
                continue

            raw_sql = src_file.read_text(encoding="utf-8")
            try:
                anon_sql = anonymize_sql(raw_sql)
                target_file = out_dir / f"{q_id}_{dst_form}.sql"
                target_file.write_text(
                    anon_sql.rstrip() + "\n", encoding="utf-8"
                )
                count += 1
            except Exception as exc:
                print(f"[ERROR] Failed to anonymize {src_file.name}: {exc}")

    print(
        f"\n[DONE] Anonymized {count} query variants into '{out_dir.resolve()}'"
    )


if __name__ == "__main__":
    generate_all_anonymized_files()