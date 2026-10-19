/* using 1433771997 as a seed to the RNG */
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
  FROM (
    SELECT
      *
    FROM tbl_parts
    WHERE
      col_p_name LIKE '%yellow%'
  ) AS tbl_parts, tbl_suppliers, tbl_items, tbl_part_suppliers, tbl_orders, tbl_countries
  WHERE
    (
      (
        (
          (
            col_s_id = col_l_supplier_id AND col_ps_supplier_id = col_l_supplier_id
          )
          AND col_ps_part_id = col_l_part_id
        )
        AND col_p_id = col_l_part_id
      )
      AND col_o_id = col_l_order_id
    )
    AND col_s_country_id = col_n_id
) AS profit
GROUP BY
  country,
  o_year
ORDER BY
  country,
  o_year DESC;
