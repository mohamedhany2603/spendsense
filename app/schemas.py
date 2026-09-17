from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    created_at: datetime


# ---- Categories ----
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str


# ---- Transactions ----
class TransactionCreate(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    amount: float = Field(gt=0, description="Positive amount in the transaction's currency")
    currency: str = Field(default="USD", min_length=3, max_length=8)
    category_id: int | None = None

    @field_validator("merchant")
    @classmethod
    def strip_merchant(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("merchant must not be blank")
        return v


class TransactionBulkCreate(BaseModel):
    items: list[TransactionCreate] = Field(min_length=1, max_length=1000)


class TransactionPatch(BaseModel):
    category_id: int | None = Field(default=None, ge=1)
    merchant: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant: str
    description: str
    amount: float
    currency: str
    status: str
    source: str | None
    category_id: int | None
    category_name: str | None
    created_at: datetime
    categorized_at: datetime | None


# ---- Analytics ----
class CategoryTotal(BaseModel):
    category: str
    total: float
    count: int


class MonthlyAnalytics(BaseModel):
    month: str
    total_expense: float
    total_transactions: int
    by_category: list[CategoryTotal]
    cached: bool = False


# ---- LLM ----
class CategorizeRequest(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)

    @field_validator("merchant")
    @classmethod
    def strip_merchant(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("merchant must not be blank")
        return v


class CategorizeResponse(BaseModel):
    merchant: str
    category: str
    category_id: int
    source: str
    cost_estimated_usd: float


class CostLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    model: str
    merchant: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    response_category: str | None
    success: bool
    error: str | None
    created_at: datetime


class CostSummary(BaseModel):
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_estimated_cost_usd: float
    logs: list[CostLogOut]


# ---- Reports ----
class ReportGenerateRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$", description="Month as YYYY-MM")


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: str
    file_name: str
    total_expense: float
    transaction_count: int
    generated_at: datetime