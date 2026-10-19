-- Anonymized TPC-H Schema Definition (PostgreSQL)
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
