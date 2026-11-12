WITH filtered_l1 AS (
  SELECT
    *
  FROM tbl_items
  WHERE
    col_l_receipt_date > col_l_commit_date
), filtered_tbl_orders AS (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_status = 'F'
), filtered_tbl_countries AS (
  SELECT
    *
  FROM tbl_countries
  WHERE
    col_n_name = 'ALGERIA'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  col_s_name,
  COUNT(*) AS numwait
FROM tbl_suppliers, filtered_l1 AS l1, filtered_tbl_orders AS tbl_orders, filtered_tbl_countries AS tbl_countries
WHERE
  (
    (
      (
        col_s_id = l1.col_l_supplier_id AND col_o_id = l1.col_l_order_id
      )
      AND EXISTS(
        SELECT
          *
        FROM tbl_items AS l2
        WHERE
          l2.col_l_order_id = l1.col_l_order_id
          AND l2.col_l_supplier_id <> l1.col_l_supplier_id
      )
    )
    AND NOT EXISTS(
      SELECT
        *
      FROM tbl_items AS l3
      WHERE
        l3.col_l_order_id = l1.col_l_order_id
        AND l3.col_l_supplier_id <> l1.col_l_supplier_id
        AND l3.col_l_receipt_date > l3.col_l_commit_date
    )
  )
  AND col_s_country_id = col_n_id
GROUP BY
  col_s_name
ORDER BY
  numwait DESC,
  col_s_name
LIMIT 100;
