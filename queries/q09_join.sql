/* using 1792286819 as a seed to the RNG */
SELECT
  country,
  o_year,
  SUM(amount) AS sum_profit
FROM (
  SELECT
    col_n_name AS country,
    EXTRACT(YEAR FROM col_o_date) AS o_year,
    col_l_ext_price * (
      1 - col_l_discount
    ) - col_ps_cost * col_l_qty AS amount
  FROM tbl_parts
  INNER JOIN tbl_items
    ON col_p_id = col_l_part_id
  INNER JOIN tbl_suppliers
    ON col_s_id = col_l_supplier_id
  INNER JOIN tbl_part_suppliers
    ON col_ps_supplier_id = col_l_supplier_id AND col_ps_part_id = col_l_part_id
  INNER JOIN tbl_orders
    ON col_o_id = col_l_order_id
  INNER JOIN tbl_countries
    ON col_s_country_id = col_n_id
  WHERE
    col_p_name LIKE '%cream%'
) AS profit
GROUP BY
  country,
  o_year
ORDER BY
  country,
  o_year DESC;
