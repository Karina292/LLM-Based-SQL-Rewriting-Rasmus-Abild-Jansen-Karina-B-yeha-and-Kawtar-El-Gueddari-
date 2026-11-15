"""
PostgreSQL Database Configuration

Stores the connection parameters used by the SQL transformation
and query equivalence verification scripts.

The configuration is loaded by transformations.py to connect
to the PostgreSQL database.
Author: Karina B'yeha
"""

DB_CONFIG = {
    "dbname": "tpch_db",
    "user": "postgres",
    "password": "your_password",
    "host": "localhost",
    "port": 5432,
}