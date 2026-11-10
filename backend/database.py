import sqlite3
from contextlib import closing

def db_init():
    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()
            tables_standard_seats = [2, 2, 2, 2,
                                     4, 4, 4, 4,
                                     6, 6, 8, 8]

            cursor.execute(
                """CREATE TABLE IF NOT EXISTS tables (
                table_number INTEGER PRIMARY KEY,
                table_seats INTEGER NOT NULL)"""
            )

            cursor.execute(
                """CREATE TABLE IF NOT EXISTS bookings (
                booking_number INTEGER PRIMARY KEY,
                booking_name TEXT NOT NULL,
                party_size INTEGER NOT NULL,
                table_number INTEGER NOT NULL,
                booking_datetime DATETIME NOT NULL,
                booking_type TEXT NOT NULL,
                estimated_departure DATETIME NOT NULL,
                booking_status TEXT NOT NULL,
                CONSTRAINT fk_table
                FOREIGN KEY (table_number) REFERENCES tables(table_number))"""
            )

            conn.commit()

            for table in tables_standard_seats:
                cursor.execute(
                    """INSERT INTO tables (table_seats)
                    VALUES (?)""", (table,)
                )

            conn.commit()

