from fastapi import HTTPException
from backend import database
from contextlib import closing
from datetime import datetime, timedelta
import sqlite3

# RECEIVES A strftime DATETIME AND ROUND UP IF ITS >= 5 ELSE ROUND DOWN
# RETURNS THE ROUNDED DATETIME
def round_minutes(booking_datetime: str, walk_in: bool = False) -> str:
    str_format = "%Y-%m-%d %H:%M:%S"
    booking_datetime_object = datetime.strptime(booking_datetime, str_format)
    booking_datetime_object = booking_datetime_object.replace(second=0, microsecond=0)

    remainder = booking_datetime_object.minute % 10

    if not walk_in:
        if remainder >= 5:
            booking_datetime_object = booking_datetime_object + timedelta(minutes=(10 - remainder))
        else:
            booking_datetime_object = booking_datetime_object - timedelta(minutes=remainder)

    else:
        booking_datetime_object = booking_datetime_object - timedelta(minutes=remainder)

    return booking_datetime_object.strftime("%Y-%m-%d %H:%M:%S")

# CHECKS TABLE'S AVAILABILITY AGAINST THEIR NEXT BOOKING
# RETURNS AN INTEGER VALUE WHICH IF IT'S 0 OR NEGATIVE MEANS THAT TABLE IS CURRENTLY RESERVED, ELSE IT'S AVAILABLE
def check_availability(
        start_datetime: str,
        booking_datetime: str,
        party_size: int
) -> int:
    if 1 <= party_size <= 8:
        if party_size in (1, 2):
            estimated_dining = 70
        elif party_size in (3, 4):
            estimated_dining = 80
        elif party_size in (5, 6):
            estimated_dining = 110
        else:
            estimated_dining = 130
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid party size!"
        )
    
    str_format = "%Y-%m-%d %H:%M:%S"

    current_object = datetime.strptime(start_datetime, str_format)
    booking_object = datetime.strptime(booking_datetime, str_format)

    waiting_starts = booking_object - timedelta(minutes=estimated_dining)
    minutes_diff = int((waiting_starts - current_object).total_seconds() // 60)

    return minutes_diff

# GATHER TABLES DATA FROM THE "TABLES" TABLE
# RETURNS A LIST OF TABLES WHICH EACH TABLE IS A DICT WITH table_number AND table_seats
def get_tables(party_size: int = 1) -> list:
    database.db_init()

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            cursor.execute(
                """SELECT * FROM tables
                WHERE table_seats >= ?""",
                (party_size,)
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
def tables_info(tables_list: list, start_datetime: str | None = None, party_size: int = 1) -> list:
    database.db_init()
    tables_list = tables_list.copy()
    if not start_datetime:
        now = datetime.now()
        formatted_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
    else:
        formatted_datetime = start_datetime

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
                        """SELECT booking_number, estimated_departure, booking_datetime, booking_status
                        FROM bookings
                        WHERE booking_datetime < ? AND table_number = ? AND (booking_status = ? OR booking_status = ?)
                        ORDER BY booking_datetime ASC
                        LIMIT 1""",
                        (formatted_datetime, tables["table_number"], "waiting", "ongoing")
                    )
                    last_booking = cursor.fetchone()

                    cursor.execute(
                        """SELECT booking_number, estimated_departure, booking_datetime, booking_status
                        FROM bookings
                        WHERE booking_datetime >= ? AND table_number = ? AND (booking_status = ? OR booking_status = ?)
                        ORDER BY booking_datetime ASC
                        LIMIT 1""",
                        (formatted_datetime, tables["table_number"], "waiting", "ongoing")
                    )
                    query_outcome = cursor.fetchone()

                    if not query_outcome:
                        min_to_next = 200
                    else:
                        min_to_next = check_availability(formatted_datetime, query_outcome[2], party_size)

                    if not last_booking:
                        min_to_last = 200
                    else:
                        min_to_last = check_availability(last_booking[1], formatted_datetime, party_size)

                    if not query_outcome and min_to_last > 0:
                        tables.update(
                            {
                                "table_status": "available",
                                "estimated_departure": None,
                                "booking_number": None
                            }
                        )

                    else:
                        if query_outcome[3] == "ongoing":
                            tables.update(
                                {
                                    "table_status": "ongoing",
                                    "estimated_departure": query_outcome[1],
                                    "booking_number": query_outcome[0]
                                }
                            )

                        else:
                            if min_to_next <= 0:
                                tables.update(
                                    {
                                        "table_status": "waiting",
                                        "estimated_departure": query_outcome[1],
                                        "booking_number": query_outcome[0]
                                    }
                                )

                            elif min_to_next > 0 and min_to_last > 0:
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
def next_upcoming(start_datetime: str | None = None) -> list:
    database.db_init()
    tables_list = get_tables()

    with closing(sqlite3.connect("restaurant.db")) as conn:
        with conn:
            cursor = conn.cursor()

            for table in tables_list:
                del table["table_seats"]

                if not start_datetime:
                    cursor.execute(
                        """SELECT booking_number, booking_name, party_size, booking_datetime
                        FROM bookings
                        WHERE table_number = ? AND booking_status = ?
                        ORDER BY booking_datetime ASC
                        LIMIT 1""",
                        (table["table_number"], "waiting")
                    )
                else:
                    cursor.execute(
                        """SELECT booking_number, booking_name, party_size, booking_datetime
                        FROM bookings
                        WHERE table_number = ? AND booking_status = ? AND booking_datetime >= ?
                        ORDER BY booking_datetime ASC
                        LIMIT 1""",
                        (table[0], "waiting", start_datetime)
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
                WHERE booking_status IN (?, ?)
                ORDER BY booking_datetime ASC""",
                ("waiting", "ongoing")
            )
            active_list = cursor.fetchall()

            cursor.execute(
                """SELECT * FROM bookings
                WHERE booking_status IN (?, ?)
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

# RETURNS THE TIME SCORING SYSTEM POINTS ACCORDING TO THE TIME DIFFERENCE
def min_scoring(minutes_difference: int) -> int:
    if minutes_difference == 0:
        return 100
    elif minutes_difference in (10, -10):
        return 85
    elif minutes_difference in (20, -20):
        return 70
    elif minutes_difference in (30, -30):
        return 55
    elif minutes_difference == -40:
        return 40
    elif minutes_difference == -50:
        return 25
    elif minutes_difference == -60:
        return 10
    else:
        raise HTTPException(
            status_code=500,
            detail="Scoring system error!"
        )

# SCORING SYSTEM FOR BEST BOOKING OPTIONS
def scoring_system(candidates_list: list) -> list:
    options_list = []
    str_format = "%Y-%m-%d %H:%M:%S"
    for candidate in candidates_list:

        if candidate["table_seats"] < candidate["party_size"]:
            ti = candidates_list.index(candidate)
            del candidates_list[ti]
            continue
        elif (candidate["table_seats"] - candidate["party_size"]) in (0, 1):
            candidate["score"] += 100
        elif (candidate["table_seats"] - candidate["party_size"]) in (2, 3):
            candidate["score"] += 50
        elif (candidate["table_seats"] - candidate["party_size"]) in (4, 5):
            candidate["score"] += 25
        elif (candidate["table_seats"] - candidate["party_size"]) > 5:
            ti = candidates_list.index(candidate)
            del candidates_list[ti]
            continue

        booking_datetime_object = datetime.strptime(candidate["booking_datetime"], str_format)
        candidate_datetime_object = datetime.strptime(candidate["candidate_datetime"], str_format)
        min_diff = booking_datetime_object - candidate_datetime_object
        min_diff = int(min_diff.total_seconds() // 60)
        candidate["score"] += min_scoring(min_diff)

    while len(options_list) != 5 and len(candidates_list) != 0:
        candidate_index = 0
        possible_cand = None
        for candidate in candidates_list:
            if not possible_cand:
                possible_cand = candidate.copy()
                candidate_index = candidates_list.index(candidate)
            else:
                if candidate["score"] > possible_cand["score"]:
                    possible_cand = candidate.copy()
                    candidate_index = candidates_list.index(candidate)

        if possible_cand:
            options_list.append(possible_cand)
            del candidates_list[candidate_index]

    return options_list

# GATHERS THE BEST ADVANCE BOOKING OPTIONS AND SEND THEM BACK TO FRONTEND IN A LIST
def advance_booking_options(request):
    database.db_init()
    str_format = "%Y-%m-%d %H:%M:%S"
    candidates_list = []
    suitable_tables = get_tables(request.party_size)

    request.booking_datetime = round_minutes(request.booking_datetime)

    booking_datetime_object = datetime.strptime(request.booking_datetime, str_format)

    for interval in range(-30, 61, 10):
        candidate_datetime = booking_datetime_object + timedelta(minutes=interval)
        candidate_datetime = candidate_datetime.strftime("%Y-%m-%d %H:%M:%S")

        temp_candidates_list = tables_info(suitable_tables, candidate_datetime, request.party_size)

        for candidate in temp_candidates_list:
            if candidate["table_status"] != "available":
                ti = temp_candidates_list.index(candidate)
                del temp_candidates_list[ti]
                continue

            else:
                del candidate["estimated_departure"]
                del candidate["booking_number"]
                candidate.update(
                    {
                        "candidate_datetime": candidate_datetime,
                        "booking_datetime": request.booking_datetime,
                        "party_size": request.party_size,
                        "score": 0
                    }
                )
                candidates_list.append(candidate.copy())
    return scoring_system(candidates_list)

# GATHERS THE BEST WALK IN BOOKING OPTIONS AND SEND THEM BACK TO FRONTEND IN A LIST
def walk_in_booking_options(request):
    database.db_init()
    str_format = "%Y-%m-%d %H:%M:%S"
    candidates_list = []
    suitable_tables = get_tables(request.party_size)

    request.booking_datetime = round_minutes(request.booking_datetime, True)

    booking_datetime_object = datetime.strptime(request.booking_datetime, str_format)

    for interval in range(0, 5):
        candidate_datetime = booking_datetime_object + timedelta(minutes=interval)
        candidate_datetime = candidate_datetime.strftime("%Y-%m-%d %H:%M:%S")

        temp_candidates_list = tables_info(suitable_tables, candidate_datetime, request.party_size)

        for candidate in temp_candidates_list:
            if candidate["table_status"] != "available":
                ti = temp_candidates_list.index(candidate)
                del temp_candidates_list[ti]
                continue

            else:
                del candidate["estimated_departure"]
                del candidate["booking_number"]
                candidate.update(
                    {
                        "candidate_datetime": candidate_datetime,
                        "booking_datetime": request.booking_datetime,
                        "party_size": request.party_size,
                        "score": 0
                    }
                )
                candidates_list.append(candidate)

    return scoring_system(candidates_list)
