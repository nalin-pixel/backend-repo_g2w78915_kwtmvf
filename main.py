import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, date

from database import db, create_document, get_documents
from schemas import Donor, Hospital, Inventory, Request as RequestSchema, Notification

app = FastAPI(title="Blood Donation Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Utility -----------------

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid object id")

# Eligibility logic

def compute_eligibility(donor: Donor) -> bool:
    return donor.age >= 18 and donor.age <= 65 and donor.health_ok

# ---------------- Donor Endpoints -----------------

@app.post("/donors", response_model=dict)
def register_donor(payload: Donor):
    data = payload.model_dump()
    data["eligible"] = compute_eligibility(payload)
    donor_id = create_document("donor", data)
    # send notification stub
    create_document("notification", {
        "to_email": data.get("email"),
        "subject": "Registration Successful",
        "message": f"Hello {data.get('name')}, your donor profile has been registered.",
    })
    return {"id": donor_id, "eligible": data["eligible"]}

@app.get("/donors", response_model=List[dict])
def list_donors(blood_group: Optional[str] = None, eligible_only: bool = True):
    query = {}
    if blood_group:
        query["blood_group"] = blood_group
    if eligible_only:
        query["eligible"] = True
    donors = get_documents("donor", query, limit=None)
    # convert ObjectId
    for d in donors:
        d["id"] = str(d.pop("_id"))
    return donors

# ---------------- Hospital Endpoints -----------------

@app.post("/hospitals", response_model=dict)
def create_hospital(payload: Hospital):
    hid = create_document("hospital", payload)
    return {"id": hid}

@app.get("/hospitals", response_model=List[dict])
def list_hospitals():
    items = get_documents("hospital", {}, None)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

# ---------------- Inventory Endpoints -----------------

@app.post("/inventory", response_model=dict)
def add_inventory(payload: Inventory):
    # ensure hospital exists
    h = db["hospital"].find_one({"_id": oid(payload.hospital_id)})
    if not h:
        raise HTTPException(404, "Hospital not found")
    # add record
    inv_id = create_document("inventory", payload)
    return {"id": inv_id}

@app.get("/inventory", response_model=List[dict])
def get_inventory(hospital_id: Optional[str] = None, include_expired: bool = False):
    q = {}
    if hospital_id:
        q["hospital_id"] = hospital_id
    if not include_expired:
        today = date.today().isoformat()
        q["expiry_date"] = {"$gte": today}
    items = get_documents("inventory", q, None)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.delete("/inventory/{inv_id}")
def remove_inventory(inv_id: str):
    res = db["inventory"].delete_one({"_id": oid(inv_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Inventory record not found")
    return {"status": "deleted"}

# ---------------- Request & Approval -----------------

@app.post("/requests", response_model=dict)
def create_request(payload: RequestSchema):
    # ensure entities exist
    donor = db["donor"].find_one({"_id": oid(payload.donor_id)})
    if not donor:
        raise HTTPException(404, "Donor not found")
    hospital = db["hospital"].find_one({"_id": oid(payload.hospital_id)})
    if not hospital:
        raise HTTPException(404, "Hospital not found")

    req_id = create_document("request", payload)

    # notification stub for donor
    create_document("notification", {
        "to_email": donor.get("email"),
        "subject": "Blood Request",
        "message": f"{hospital.get('name')} requested {payload.units} unit(s) of {payload.blood_group}.",
        "meta": {"request_id": req_id}
    })
    return {"id": req_id}

@app.get("/requests", response_model=List[dict])
def list_requests(status: Optional[str] = None, donor_id: Optional[str] = None, hospital_id: Optional[str] = None):
    q = {}
    if status:
        q["status"] = status
    if donor_id:
        q["donor_id"] = donor_id
    if hospital_id:
        q["hospital_id"] = hospital_id
    items = get_documents("request", q, None)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

class UpdateStatus(BaseModel):
    status: str

@app.post("/requests/{request_id}/status")
def update_request_status(request_id: str, payload: UpdateStatus):
    if payload.status not in ["approved", "declined"]:
        raise HTTPException(400, "Status must be 'approved' or 'declined'")
    res = db["request"].update_one({"_id": oid(request_id)}, {"$set": {"status": payload.status, "updated_at": datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Request not found")
    # notify hospital
    req = db["request"].find_one({"_id": oid(request_id)})
    hospital = db["hospital"].find_one({"_id": oid(req["hospital_id"])})
    create_document("notification", {
        "to_email": hospital.get("email") if hospital else None,
        "subject": f"Request {payload.status}",
        "message": f"Request {request_id} has been {payload.status} by the donor.",
    })
    return {"status": payload.status}

# ---------------- Notifications (Email/SMS stubs) -----------------

@app.post("/notify", response_model=dict)
def create_notification(payload: Notification):
    nid = create_document("notification", payload)
    return {"id": nid}

@app.get("/notifications", response_model=List[dict])
def list_notifications(limit: Optional[int] = 50):
    items = get_documents("notification", {}, limit)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

# ---------------- Health -----------------

@app.get("/")
def read_root():
    return {"message": "Blood Donation Management API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, 'name', '✅ Connected')
            response["connection_status"] = "Connected"
            collections = db.list_collection_names()
            response["collections"] = collections[:10]
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
