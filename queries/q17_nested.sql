/* using 1433771997 as a seed to the RNG */
SELECT
  SUM(col_l_ext_price) / 7.0 AS avg_yearly
FROM tbl_items, (
  SELECT
    *
  FROM tbl_parts
  WHERE
    col_p_label = 'Brand#52' AND col_p_packaging = 'LG CAN'
) AS tbl_parts
WHERE
  col_p_id = col_l_part_id
  AND col_l_qty < (
    SELECT
      CAST('0.2' AS DECIMAL) * AVG(col_l_qty)
    FROM tbl_items
    WHERE
      col_l_part_id = col_p_id
  );
