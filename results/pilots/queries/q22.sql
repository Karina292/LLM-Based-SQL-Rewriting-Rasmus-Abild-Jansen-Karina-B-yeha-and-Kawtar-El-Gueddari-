select
	cntrycode,
	count(*) as numcust,
	sum(col_c_balance) as totacctbal
from
	(
		select
			substring(col_c_phone from 1 for 2) as cntrycode,
			col_c_balance
		from
			tbl_customers
		where
			substring(col_c_phone from 1 for 2) in
				('27', '21', '24', '26', '12', '31', '34')
			and col_c_balance > (
				select
					avg(col_c_balance)
				from
					tbl_customers
				where
					col_c_balance > 0.00
					and substring(col_c_phone from 1 for 2) in
						('27', '21', '24', '26', '12', '31', '34')
			)
			and not exists (
				select
					*
				from
					tbl_orders
				where
					col_o_customer_id = col_c_id
			)
	) as custsale
group by
	cntrycode
order by
	cntrycode;
