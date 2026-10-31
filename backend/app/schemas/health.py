from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    service: Literal["qpqdata-api"] = "qpqdata-api"
