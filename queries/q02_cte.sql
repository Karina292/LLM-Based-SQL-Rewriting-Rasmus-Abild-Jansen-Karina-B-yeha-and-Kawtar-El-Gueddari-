WITH filtered_tbl_parts AS (
  SELECT
    *
  FROM tbl_parts
  WHERE
    col_p_dimension = 17 AND col_p_category LIKE '%NICKEL'
), filtered_tbl_zones AS (
  SELECT
    *
  FROM tbl_zones
  WHERE
    col_r_name = 'AMERICA'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  col_s_balance,
  col_s_name,
  col_n_name,
  col_p_id,
  col_p_manufacturer,
  col_s_address,
  col_s_phone,
  col_s_notes
FROM filtered_tbl_parts AS tbl_parts, tbl_suppliers, tbl_part_suppliers, tbl_countries, filtered_tbl_zones AS tbl_zones
WHERE
  (
    (
      (
        col_p_id = col_ps_part_id AND col_s_id = col_ps_supplier_id
      )
      AND col_s_country_id = col_n_id
    )
    AND col_n_zone_id = col_r_id
  )
  AND col_ps_cost = (
    SELECT
      MIN(col_ps_cost)
    FROM tbl_part_suppliers, tbl_suppliers, tbl_countries, tbl_zones
    WHERE
      col_p_id = col_ps_part_id
      AND col_s_id = col_ps_supplier_id
      AND col_s_country_id = col_n_id
      AND col_n_zone_id = col_r_id
      AND col_r_name = 'AMERICA'
  )
ORDER BY
  col_s_balance DESC,
  col_n_name,
  col_s_name,
  col_p_id
LIMIT 100;
