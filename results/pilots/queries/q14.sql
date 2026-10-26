select
	100.00 * sum(case
		when col_p_category like 'PROMO%'
			then col_l_ext_price * (1 - col_l_discount)
		else 0
	end) / sum(col_l_ext_price * (1 - col_l_discount)) as promo_revenue
from
	tbl_items,
	tbl_parts
where
	col_l_part_id = col_p_id
	and col_l_ship_date >= date '1997-01-01'
	and col_l_ship_date < date '1997-01-01' + interval '1' month;
