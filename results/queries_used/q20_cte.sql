WITH filtered_tbl_countries AS (
  SELECT
    *
  FROM tbl_countries
  WHERE
    col_n_name = 'IRAN'
)
/* using 1433771997 as a seed to the RNG */
SELECT
  col_s_name,
  col_s_address
FROM tbl_suppliers, filtered_tbl_countries AS tbl_countries
WHERE
  col_s_id IN (
    SELECT
      col_ps_supplier_id
    FROM tbl_part_suppliers
    WHERE
      col_ps_part_id IN (
        SELECT
          col_p_id
        FROM tbl_parts
        WHERE
          col_p_name LIKE 'frosted%'
      )
      AND col_ps_available_qty > (
        SELECT
          CAST(0.5 AS DECIMAL) * SUM(col_l_qty)
        FROM tbl_items
        WHERE
          col_l_part_id = col_ps_part_id
          AND col_l_supplier_id = col_ps_supplier_id
          AND col_l_ship_date >= CAST('1994-01-01' AS DATE)
          AND col_l_ship_date < CAST('1994-01-01' AS DATE) + INTERVAL '1 YEAR'
      )
  )
  AND col_s_country_id = col_n_id
ORDER BY
  col_s_name;
