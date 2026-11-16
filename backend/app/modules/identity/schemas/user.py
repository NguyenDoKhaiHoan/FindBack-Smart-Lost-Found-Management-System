from datetime import datetime

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

from app.modules.identity.models.user import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str | None = None
    avatar_url: AnyHttpUrl | None = None
    role: UserRole
    created_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    avatar_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("full_name cannot be null")
        if self.full_name is not None:
            self.full_name = self.full_name.strip()
            if not self.full_name:
                raise ValueError("full_name must not be blank")
        return self
