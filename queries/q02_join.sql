/* using 1433771997 as a seed to the RNG */
SELECT
  col_s_balance,
  col_s_name,
  col_n_name,
  col_p_id,
  col_p_manufacturer,
  col_s_address,
  col_s_phone,
  col_s_notes
FROM tbl_parts
INNER JOIN tbl_part_suppliers
  ON col_p_id = col_ps_part_id
INNER JOIN tbl_suppliers
  ON col_s_id = col_ps_supplier_id
INNER JOIN tbl_countries
  ON col_s_country_id = col_n_id
INNER JOIN tbl_zones
  ON col_n_zone_id = col_r_id
WHERE
  (
    (
      col_p_dimension = 38 AND col_p_category LIKE '%TIN'
    )
    AND col_r_name = 'ZONE_CENTRAL'
  )
  AND col_ps_cost = (
    SELECT
      MIN(col_ps_cost)
    FROM tbl_part_suppliers
    INNER JOIN tbl_suppliers
      ON col_s_id = col_ps_supplier_id
    INNER JOIN tbl_countries
      ON col_s_country_id = col_n_id
    INNER JOIN tbl_zones
      ON col_n_zone_id = col_r_id
    WHERE
      col_p_id = col_ps_part_id AND col_r_name = 'ZONE_CENTRAL'
  )
ORDER BY
  col_s_balance DESC,
  col_n_name,
  col_s_name,
  col_p_id
LIMIT 100;
