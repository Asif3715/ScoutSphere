from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Base for every request body. Surrounding whitespace is removed *before* validation, so
    a name of "   " fails `min_length` instead of being stored as a blank."""

    model_config = ConfigDict(str_strip_whitespace=True)
