WITH all_tbl_countriess AS (
  SELECT
    EXTRACT(YEAR FROM col_o_date) AS o_year,
    col_l_ext_price * (
      1 - col_l_discount
    ) AS volume,
    n2.col_n_name AS country
  FROM tbl_parts, tbl_suppliers, tbl_items, tbl_orders, tbl_customers, tbl_countries AS n1, tbl_countries AS n2, tbl_zones
  WHERE
    col_p_id = col_l_part_id
    AND col_s_id = col_l_supplier_id
    AND col_l_order_id = col_o_id
    AND col_o_customer_id = col_c_id
    AND col_c_country_id = n1.col_n_id
    AND n1.col_n_zone_id = col_r_id
    AND col_r_name = 'ZONE_EAST'
    AND col_s_country_id = n2.col_n_id
    AND col_o_date BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
    AND col_p_category = 'SMALL BURNISHED NICKEL'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  o_year,
  SUM(CASE WHEN country = 'INDONESIA' THEN volume ELSE 0 END) / SUM(volume) AS mkt_share
FROM all_tbl_countriess
GROUP BY
  o_year
ORDER BY
  o_year;
