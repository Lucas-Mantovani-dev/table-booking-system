from fastapi import HTTPException
from backend import database
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3

# CHECKS TABLE'S AVAILABILITY AGAINST THEIR NEXT BOOKING
# RETURNS AN INTEGER VALUE WHICH IF IT'S NEGATIVE MEANS THAT TABLE IS CURRENTLY RESERVED, ELSE IT'S AVAILABLE
def check_availability(
        current_datetime: str,
        booking_datetime: str,
        customer_party: int | None = None
) -> int:
    if customer_party in (1, 2):
        estimated_dining = 70
    elif customer_party in (3, 4):
        estimated_dining = 80
    elif customer_party in (5, 6):
        estimated_dining = 110
    elif customer_party in (7, 8):
        estimated_dining = 130
    else:
        estimated_dining = 70
    str_format = "%Y-%m-%d %H:%M:%S"

    current_object = datetime.strptime(current_datetime, str_format)
    booking_object = datetime.strptime(booking_datetime, str_format)

    waiting_starts = booking_object - timedelta(minutes=estimated_dining)
    minutes_diff = int((waiting_starts - current_object).total_seconds() // 60)

    return minutes_diff

# GATHER TABLES DATA FROM THE "TABLES" TABLE
# RETURNS A LIST OF TABLES WHICH EACH TABLE IS A DICT WITH table_number AND table_seats
def get_tables() -> list:
    database.db_init()

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            cursor.execute(
                """SELECT * FROM tables"""
            )
            query_outcome = cursor.fetchall()

    if not query_outcome:
        raise HTTPException(
            status_code=500,
            detail="No tables found!"
        )
    
    else:
        request_list = []

        for table in query_outcome:
            request_list.append(
                {
                    "table_number": table[0],
                    "table_seats": table[1]
                }
            )

        return request_list

# GATHER DEEPER DATA FROM EACH TABLE
# 
def tables_info(tables_list: list) -> list:
    now = datetime.now()
    formatted_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

    if not tables_list:
        raise HTTPException(
            status_code=500,
            detail="No tables found!"
        )
    
    else:
        with closing(sqlite3.connect("restaurant.db")) as conn:
            with conn:
                cursor = conn.cursor()

                for tables in tables_list:
                    cursor.execute(
                        """SELECT booking_number, estimated_departure, booking_datetime
                        FROM bookings
                        WHERE table_number = ? AND (booking_status = ? OR booking_status = ?)""",
                        (tables[0], "waiting", "ongoing")
                    )