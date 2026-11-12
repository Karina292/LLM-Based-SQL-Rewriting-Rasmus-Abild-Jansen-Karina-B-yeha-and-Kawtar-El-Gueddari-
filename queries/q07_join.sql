/* using 1792286819 as a seed to the RNG */
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
  FROM tbl_suppliers
  INNER JOIN tbl_items
    ON col_s_id = col_l_supplier_id
  INNER JOIN tbl_orders
    ON col_o_id = col_l_order_id
  INNER JOIN tbl_customers
    ON col_c_id = col_o_customer_id
  INNER JOIN tbl_countries AS n1
    ON col_s_country_id = n1.col_n_id
  INNER JOIN tbl_countries AS n2
    ON col_c_country_id = n2.col_n_id
  WHERE
    (
      (
        n1.col_n_name = 'UNITED KINGDOM' AND n2.col_n_name = 'INDONESIA'
      )
      OR (
        n1.col_n_name = 'INDONESIA' AND n2.col_n_name = 'UNITED KINGDOM'
      )
    )
    AND col_l_ship_date BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
) AS shipping
GROUP BY
  supp_nation,
  cust_nation,
  l_year
ORDER BY
  supp_nation,
  cust_nation,
  l_year;
