WITH filtered_tbl_countries AS (
  SELECT
    *
  FROM tbl_countries
  WHERE
    col_n_name = 'ARGENTINA'
)
/* using 1433771997 as a seed to the RNG */
SELECT
  col_ps_part_id,
  SUM(col_ps_cost * col_ps_available_qty) AS value
FROM tbl_part_suppliers, tbl_suppliers, filtered_tbl_countries AS tbl_countries
WHERE
  col_ps_supplier_id = col_s_id AND col_s_country_id = col_n_id
GROUP BY
  col_ps_part_id
HAVING
  SUM(col_ps_cost * col_ps_available_qty) > (
    SELECT
      SUM(col_ps_cost * col_ps_available_qty) * 0.0001000000
    FROM tbl_part_suppliers, tbl_suppliers, tbl_countries
    WHERE
      col_ps_supplier_id = col_s_id
      AND col_s_country_id = col_n_id
      AND col_n_name = 'ARGENTINA'
  )
ORDER BY
  value DESC;
