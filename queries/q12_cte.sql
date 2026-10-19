WITH filtered_tbl_items AS (
  SELECT
    *
  FROM tbl_items
  WHERE
    (
      (
        (
          col_l_mode IN ('FOB', 'SHIP') AND col_l_commit_date < col_l_receipt_date
        )
        AND col_l_ship_date < col_l_commit_date
      )
      AND col_l_receipt_date >= CAST('1994-01-01' AS DATE)
    )
    AND col_l_receipt_date < CAST('1994-01-01' AS DATE) + INTERVAL '1 YEAR'
)
/* using 1433771997 as a seed to the RNG */
SELECT
  col_l_mode,
  SUM(
    CASE WHEN col_o_priority = '1-URGENT' OR col_o_priority = '2-HIGH' THEN 1 ELSE 0 END
  ) AS high_line_count,
  SUM(
    CASE
      WHEN col_o_priority <> '1-URGENT' AND col_o_priority <> '2-HIGH'
      THEN 1
      ELSE 0
    END
  ) AS low_line_count
FROM tbl_orders, filtered_tbl_items AS tbl_items
WHERE
  col_o_id = col_l_order_id
GROUP BY
  col_l_mode
ORDER BY
  col_l_mode;
