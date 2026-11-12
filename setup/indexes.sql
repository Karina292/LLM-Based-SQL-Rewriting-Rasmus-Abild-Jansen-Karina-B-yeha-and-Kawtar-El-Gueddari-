CREATE INDEX tbl_customers_col_c_country_id_idx ON public.tbl_customers USING btree (col_c_country_id);
CREATE INDEX tbl_items_col_l_order_id_idx ON public.tbl_items USING btree (col_l_order_id);
CREATE INDEX tbl_items_col_l_part_id_col_l_supplier_id_idx ON public.tbl_items USING btree (col_l_part_id, col_l_supplier_id);
CREATE INDEX tbl_orders_col_o_customer_id_idx ON public.tbl_orders USING btree (col_o_customer_id);
CREATE INDEX tbl_part_suppliers_col_ps_supplier_id_idx ON public.tbl_part_suppliers USING btree (col_ps_supplier_id);
CREATE INDEX tbl_suppliers_col_s_country_id_idx ON public.tbl_suppliers USING btree (col_s_country_id);
