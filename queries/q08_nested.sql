/* using 1433771997 as a seed to the RNG */
SELECT
  o_year,
  SUM(CASE WHEN country = 'INDIA' THEN volume ELSE 0 END) / SUM(volume) AS mkt_share
FROM (
  SELECT
    EXTRACT(YEAR FROM col_o_date) AS o_year,
    col_l_ext_price * (
      1 - col_l_discount
    ) AS volume,
    n2.col_n_name AS country
  FROM (
    SELECT
      *
    FROM tbl_parts
    WHERE
      col_p_category = 'PROMO BRUSHED COPPER'
  ) AS tbl_parts, tbl_suppliers, tbl_items, (
    SELECT
      *
    FROM tbl_orders
    WHERE
      col_o_date BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
  ) AS tbl_orders, tbl_customers, tbl_countries AS n1, tbl_countries AS n2, (
    SELECT
      *
    FROM tbl_zones
    WHERE
      col_r_name = 'ZONE_EAST'
  ) AS tbl_zones
  WHERE
    (
      (
        (
          (
            (
              col_p_id = col_l_part_id AND col_s_id = col_l_supplier_id
            )
            AND col_l_order_id = col_o_id
          )
          AND col_o_customer_id = col_c_id
        )
        AND col_c_country_id = n1.col_n_id
      )
      AND n1.col_n_zone_id = col_r_id
    )
    AND col_s_country_id = n2.col_n_id
) AS all_nations
GROUP BY
  o_year
ORDER BY
  o_year;
