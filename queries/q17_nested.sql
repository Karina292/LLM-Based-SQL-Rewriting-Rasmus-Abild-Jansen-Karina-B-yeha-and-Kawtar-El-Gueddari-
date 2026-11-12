/* using 1792286819 as a seed to the RNG */
SELECT
  SUM(col_l_ext_price) / 7.0 AS avg_yearly
FROM tbl_items, (
  SELECT
    *
  FROM tbl_parts
  WHERE
    col_p_label = 'Brand#41' AND col_p_packaging = 'LG BAG'
) AS tbl_parts
WHERE
  col_p_id = col_l_part_id
  AND col_l_qty < (
    SELECT
      0.2 * AVG(col_l_qty)
    FROM tbl_items
    WHERE
      col_l_part_id = col_p_id
  );
