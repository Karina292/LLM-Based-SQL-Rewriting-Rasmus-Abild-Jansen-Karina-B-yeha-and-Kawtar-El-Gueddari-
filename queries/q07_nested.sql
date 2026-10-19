/* using 1433771997 as a seed to the RNG */
SELECT
  supp_nation,
  cust_nation,
  l_year,
  SUM(volume) AS revenue
FROM (
  SELECT
    n1.col_n_name AS supp_nation,
    n2.col_n_name AS cust_nation,
    EXTRACT(YEAR FROM col_l_ship_date) AS l_year,
    col_l_ext_price * (
      1 - col_l_discount
    ) AS volume
  FROM tbl_suppliers, (
    SELECT
      *
    FROM tbl_items
    WHERE
      col_l_ship_date BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
  ) AS tbl_items, tbl_orders, tbl_customers, tbl_countries AS n1, tbl_countries AS n2
  WHERE
    (
      (
        (
          (
            col_s_id = col_l_supplier_id AND col_o_id = col_l_order_id
          )
          AND col_c_id = col_o_customer_id
        )
        AND col_s_country_id = n1.col_n_id
      )
      AND col_c_country_id = n2.col_n_id
    )
    AND (
      (
        n1.col_n_name = 'ROMANIA' AND n2.col_n_name = 'INDIA'
      )
      OR (
        n1.col_n_name = 'INDIA' AND n2.col_n_name = 'ROMANIA'
      )
    )
) AS shipping
GROUP BY
  supp_nation,
  cust_nation,
  l_year
ORDER BY
  supp_nation,
  cust_nation,
  l_year;
