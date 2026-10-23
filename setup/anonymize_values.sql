-- Rename categorical values so they match the anonymized queries (mapping from Karina's script).
-- AFRICA and AMERICA are not renamed (not used by any query).
BEGIN;
UPDATE tbl_zones SET col_r_name = 'ZONE_CENTRAL' WHERE col_r_name = 'MIDDLE EAST';
UPDATE tbl_zones SET col_r_name = 'ZONE_EAST'    WHERE col_r_name = 'ASIA';
UPDATE tbl_zones SET col_r_name = 'ZONE_NORTH'   WHERE col_r_name = 'EUROPE';

UPDATE tbl_customers SET col_c_segment = 'SEGMENT_A' WHERE col_c_segment = 'FURNITURE';
UPDATE tbl_customers SET col_c_segment = 'SEGMENT_B' WHERE col_c_segment = 'BUILDING';
UPDATE tbl_customers SET col_c_segment = 'SEGMENT_C' WHERE col_c_segment = 'MACHINERY';
UPDATE tbl_customers SET col_c_segment = 'SEGMENT_D' WHERE col_c_segment = 'HOUSEHOLD';
UPDATE tbl_customers SET col_c_segment = 'SEGMENT_E' WHERE col_c_segment = 'AUTOMOBILE';
COMMIT;
VACUUM ANALYZE;
