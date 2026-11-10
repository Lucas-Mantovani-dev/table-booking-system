from fastapi import FastAPI, HTTPException
from backend import services, models

app = FastAPI()

@app.get("/tables")
def get_tables():
    tables_list = services.get_tables()
    tables_list = services.tables_info(tables_list)
    return tables_list

@app.get("/bookings/upcoming")
def get_upcoming():
    return services.next_upcoming()

@app.get("/bookings")
def get_bookings():
    return services.all_bookings()

@app.post("/booking_availability")
def booking_availability(request: models.BookingCheck):
    services.booking_options(request)