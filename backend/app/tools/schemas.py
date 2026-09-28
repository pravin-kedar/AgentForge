from datetime import date

from pydantic import BaseModel, Field, model_validator


class SearchHotelsInput(BaseModel):
    destination: str
    check_in: date | None = None
    check_out: date | None = None
    guests: int = Field(default=1, ge=1, le=20)


class GetHotelDetailsInput(BaseModel):
    hotel_id: int


class CheckHotelAvailabilityInput(BaseModel):
    hotel_id: int
    check_in: date
    check_out: date
    guests: int = Field(default=1, ge=1, le=20)
    room_type: str | None = None

    @model_validator(mode="after")
    def _dates_ordered(self) -> "CheckHotelAvailabilityInput":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class GetDestinationInfoInput(BaseModel):
    destination: str


class SearchActivitiesInput(BaseModel):
    destination: str
    category: str | None = None


class GetWeatherInput(BaseModel):
    destination: str
    for_date: date | None = None


class CreateTripInput(BaseModel):
    destination: str
    start_date: date
    end_date: date
    budget: float | None = Field(default=None, ge=0)
    notes: str | None = None
    hotel_id: int | None = None
    activity_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dates_ordered(self) -> "CreateTripInput":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class GetMyTripsInput(BaseModel):
    pass


class GetTripInput(BaseModel):
    trip_id: str


class UpdateTripInput(BaseModel):
    trip_id: str
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = Field(default=None, ge=0)
    notes: str | None = None
    status: str | None = None


class DeleteTripInput(BaseModel):
    trip_id: str
