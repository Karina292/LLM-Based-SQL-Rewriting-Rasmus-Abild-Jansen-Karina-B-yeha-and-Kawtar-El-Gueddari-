/* using 1433771997 as a seed to the RNG */
SELECT
  col_ps_part_id,
  SUM(col_ps_cost * col_ps_available_qty) AS value
FROM tbl_part_suppliers
INNER JOIN tbl_suppliers
  ON col_ps_supplier_id = col_s_id
INNER JOIN tbl_countries
  ON col_s_country_id = col_n_id
WHERE
  col_n_name = 'ARGENTINA'
GROUP BY
  col_ps_part_id
HAVING
  SUM(col_ps_cost * col_ps_available_qty) > (
    SELECT
      SUM(col_ps_cost * col_ps_available_qty) * 0.0001000000
    FROM tbl_part_suppliers
    INNER JOIN tbl_suppliers
      ON col_ps_supplier_id = col_s_id
    INNER JOIN tbl_countries
      ON col_s_country_id = col_n_id
    WHERE
      col_n_name = 'ARGENTINA'
  )
ORDER BY
  value DESC;
