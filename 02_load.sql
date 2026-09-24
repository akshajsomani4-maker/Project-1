-- Bulk-load the generated CSVs (mounted at /docker-entrypoint-initdb.d).
\copy regions FROM '/docker-entrypoint-initdb.d/regions.csv' WITH (FORMAT csv, HEADER true);
\copy customers FROM '/docker-entrypoint-initdb.d/customers.csv' WITH (FORMAT csv, HEADER true);
\copy orders FROM '/docker-entrypoint-initdb.d/orders.csv' WITH (FORMAT csv, HEADER true);
\copy customer_quarters FROM '/docker-entrypoint-initdb.d/customer_quarters.csv' WITH (FORMAT csv, HEADER true);

ANALYZE regions;
ANALYZE customers;
ANALYZE orders;
ANALYZE customer_quarters;
