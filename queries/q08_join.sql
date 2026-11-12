/* using 1792286819 as a seed to the RNG */
SELECT
  o_year,
  SUM(CASE WHEN country = 'INDONESIA' THEN volume ELSE 0 END) / SUM(volume) AS mkt_share
FROM (
  SELECT
    EXTRACT(YEAR FROM col_o_date) AS o_year,
    col_l_ext_price * (
      1 - col_l_discount
    ) AS volume,
    n2.col_n_name AS country
  FROM tbl_parts
  INNER JOIN tbl_items
    ON col_p_id = col_l_part_id
  INNER JOIN tbl_suppliers
    ON col_s_id = col_l_supplier_id
  INNER JOIN tbl_orders
    ON col_l_order_id = col_o_id
  INNER JOIN tbl_customers
    ON col_o_customer_id = col_c_id
  INNER JOIN tbl_countries AS n1
    ON col_c_country_id = n1.col_n_id
  INNER JOIN tbl_countries AS n2
    ON col_s_country_id = n2.col_n_id
  INNER JOIN tbl_zones
    ON n1.col_n_zone_id = col_r_id
  WHERE
    (
      col_r_name = 'ZONE_EAST'
      AND col_o_date BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
    )
    AND col_p_category = 'SMALL BURNISHED NICKEL'
) AS all_nations
GROUP BY
  o_year
ORDER BY
  o_year;
