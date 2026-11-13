select
	col_p_label,
	col_p_category,
	col_p_dimension,
	count(distinct col_ps_supplier_id) as supplier_cnt
from
	tbl_part_suppliers,
	tbl_parts
where
	col_p_id = col_ps_part_id
	and col_p_label <> 'Brand#44'
	and col_p_category not like 'STANDARD BURNISHED%'
	and col_p_dimension in (13, 8, 3, 36, 24, 29, 34, 30)
	and col_ps_supplier_id not in (
		select
			col_s_id
		from
			tbl_suppliers
		where
			col_s_notes like '%Customer%Complaints%'
	)
group by
	col_p_label,
	col_p_category,
	col_p_dimension
order by
	supplier_cnt desc,
	col_p_label,
	col_p_category,
	col_p_dimension;
