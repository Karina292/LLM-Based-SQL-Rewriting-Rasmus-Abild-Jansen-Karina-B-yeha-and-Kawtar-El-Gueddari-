/* using 1433771997 as a seed to the RNG */
SELECT
  col_s_name,
  COUNT(*) AS numwait
FROM tbl_suppliers
INNER JOIN tbl_items AS l1
  ON col_s_id = l1.col_l_supplier_id
INNER JOIN tbl_orders
  ON col_o_id = l1.col_l_order_id
INNER JOIN tbl_countries
  ON col_s_country_id = col_n_id
WHERE
  (
    (
      (
        col_o_status = 'F' AND l1.col_l_receipt_date > l1.col_l_commit_date
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
  AND col_n_name = 'GERMANY'
GROUP BY
  col_s_name
ORDER BY
  numwait DESC,
  col_s_name
LIMIT 100;
