from pydantic import BaseModel

class BookingCheck(BaseModel):
    party_size: int
    booking_type: str
    booking_datetime: str

