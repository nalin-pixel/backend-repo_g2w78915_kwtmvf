"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import date

# ---------------- Blood Donation Management Schemas -----------------

BloodGroup = Literal[
    "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
]

class Donor(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: str = Field(..., description="Contact phone number")
    age: int = Field(..., ge=18, le=65, description="Age in years (18-65 eligible)")
    blood_group: BloodGroup
    health_ok: bool = Field(..., description="Self-declared good health status")
    city: Optional[str] = Field(None, description="City/Location")
    eligible: bool = Field(True, description="Eligibility computed at registration")

class Hospital(BaseModel):
    name: str
    email: EmailStr
    phone: str
    city: Optional[str] = None

class Inventory(BaseModel):
    hospital_id: str = Field(..., description="Hospital ObjectId as string")
    blood_group: BloodGroup
    units: int = Field(..., ge=1, description="Units donated (1 unit ~ 450ml)")
    expiry_date: date = Field(..., description="Expiry date of this donation unit batch")

class Request(BaseModel):
    hospital_id: str
    donor_id: str
    blood_group: BloodGroup
    units: int = Field(..., ge=1)
    status: Literal["pending", "approved", "declined"] = "pending"

class Notification(BaseModel):
    to_email: Optional[EmailStr] = None
    to_phone: Optional[str] = None
    subject: str
    message: str
    meta: Optional[dict] = None

# ---------------- Example legacy schemas (kept for reference) -----------------
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
