/* using 1792286819 as a seed to the RNG */
SELECT
  col_o_priority,
  COUNT(*) AS order_count
FROM (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_date >= CAST('1994-01-01' AS DATE)
    AND col_o_date < CAST('1994-01-01' AS DATE) + INTERVAL '3 MONTH'
) AS tbl_orders
WHERE
  EXISTS(
    SELECT
      *
    FROM (
      SELECT
        *
      FROM tbl_items
      WHERE
        col_l_order_id = col_o_id AND col_l_commit_date < col_l_receipt_date
    ) AS tbl_items
  )
GROUP BY
  col_o_priority
ORDER BY
  col_o_priority;
