from fastapi import HTTPException
from backend import database
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3

# CHECKS TABLE'S AVAILABILITY AGAINST THEIR NEXT BOOKING
# RETURNS AN INTEGER VALUE WHICH IF IT'S 0 OR NEGATIVE MEANS THAT TABLE IS CURRENTLY RESERVED, ELSE IT'S AVAILABLE
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
# RETURNS SAME LIST PROVIDED BUT WITH MORE DATA IN IT
def tables_info(tables_list: list) -> list:
    database.db_init()
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
                        WHERE table_number = ? AND (booking_status = ? OR booking_status = ?)
                        ORDER BY booking_datetime ASC
                        LIMIT 1""",
                        (tables[0], "waiting", "ongoing")
                    )
                    query_outcome = cursor.fetchone()

                    if not query_outcome:
                        tables.update(
                            {
                                "table_status": "available",
                                "estimated_departure": None,
                                "booking_number": None
                            }
                        )

                    else:
                        min_to_next = check_availability(formatted_datetime, query_outcome[2])

                        if min_to_next <= 0:
                            tables.update(
                                {
                                    "table_status": "waiting",
                                    "estimated_departure": query_outcome[1],
                                    "booking_number": query_outcome[0]
                                }
                            )

                        else:
                            tables.update(
                                {
                                    "table_status": "available",
                                    "estimated_departure": None,
                                    "booking_number": None
                                }
                            )

                return tables_list

# GATHER TABLES LIST USING get_tables()
# RETURNS EDITED TABLES LIST
def next_upcoming() -> list:
    database.db_init()
    tables_list = get_tables()

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            for table in tables_list:
                del table["table_seats"]

                cursor.execute(
                    """SELECT booking_number, booking_name, party_size, booking_datetime
                    FROM bookings
                    WHERE table_number = ? AND booking_status = ?
                    ORDER BY booking_datetime ASC
                    LIMIT 1""",
                    (table[0], "waiting")
                )

                query_outcome = cursor.fetchone()

                if not query_outcome:
                    table.update(
                        {
                            "booking_number": None,
                            "booking_name": None,
                            "party_size": None,
                            "booking_datetime": None
                        }
                    )

                else:
                    table.update(
                        {
                            "booking_number": query_outcome[0],
                            "booking_name": query_outcome[1],
                            "party_size": query_outcome[2],
                            "booking_datetime": query_outcome[3]
                        }
                    )

        return tables_list

# RETURNS ALL BOOKINGS IN A LIST FROM ACTIVE TO UNACTIVE BOOKINGS
def all_bookings() -> list:
    database.db_init()

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            cursor.execute(
                """SELECT * FROM bookings
                WHERE bookings_status = ? AND booking_status = ?
                ORDER BY booking_datetime ASC""",
                ("waiting", "ongoing")
            )
            active_list = cursor.fetchall()

            cursor.execute(
                """SELECT * FROM bookings
                WHERE bookings_status = ? AND booking_status = ?
                ORDER BY booking_datetime DESC""",
                ("finished", "cancelled")
            )
            unactive_list = cursor.fetchall()

            full_list = active_list + unactive_list
            bookings_list = []

            for booking in full_list:
                bookings_list.append(
                    {
                        "booking_number": booking[0],
                        "booking_name": booking[1],
                        "party_size": booking[2],
                        "table_number": booking[3],
                        "booking_datetime": booking[4],
                        "booking_status": booking[7]
                    }
                )

    return bookings_list

def booking_options(request):
    database.db_init()
    option_list = []

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            if request.booking_type == "advance":
                