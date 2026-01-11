import os
import time
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import requests

from sqlalchemy import or_

from extensions import csrf, db
from models import (
    LogisticsBooking,
    LogisticsPartner,
    LogisticsVehicle,
    LogisticsVehicleType,
    Pump,
    PumpOwner,
    User,
    VehicleLocation,
)

import math

logistics_bp = Blueprint("logistics", __name__)


_PUBLIC_PUMPS_CACHE = {}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _current_scope_filter():
    if isinstance(current_user, PumpOwner):
        return {"owner_id": current_user.id}
    if isinstance(current_user, User):
        return {"user_id": current_user.id}
    return {}


def _ensure_partner_for_current_user() -> LogisticsPartner | None:
    if isinstance(current_user, PumpOwner):
        existing = LogisticsPartner.query.filter_by(partner_type="pump_owner", pump_owner_id=current_user.id).first()
        if existing:
            return existing
        partner = LogisticsPartner(
            partner_type="pump_owner",
            pump_owner_id=current_user.id,
            display_name=(current_user.full_name or current_user.email or f"PumpOwner {current_user.id}"),
            is_active=True,
        )
        db.session.add(partner)
        db.session.commit()
        return partner

    if isinstance(current_user, User):
        existing = LogisticsPartner.query.filter_by(partner_type="user", user_id=current_user.id).first()
        if existing:
            return existing
        partner = LogisticsPartner(
            partner_type="user",
            user_id=current_user.id,
            display_name=(current_user.full_name or current_user.email or f"User {current_user.id}"),
            is_active=True,
        )
        db.session.add(partner)
        db.session.commit()
        return partner

    return None


def _quote_lowest_cost(quantity_tons: float, distance_km: float, single_vehicle: bool) -> dict:
    if quantity_tons <= 0:
        raise ValueError("quantity_tons must be > 0")
    if distance_km <= 0:
        raise ValueError("distance_km must be > 0")

    vtypes = LogisticsVehicleType.query.filter_by(is_active=True).all()
    if not vtypes:
        raise ValueError("No vehicle types available")

    best = None
    for vt in vtypes:
        cap = float(vt.capacity_tons or 0.0)
        if cap <= 0:
            continue
        if single_vehicle and quantity_tons > cap:
            continue

        vehicles_needed = 1
        if not single_vehicle:
            vehicles_needed = int(math.ceil(quantity_tons / cap))

        charge_qty = float(quantity_tons)
        sbq = float(vt.sbq_tons or 0.0)
        if single_vehicle and sbq > 0:
            charge_qty = max(charge_qty, sbq)

        fixed = float(vt.fixed_cost or 0.0) * float(vehicles_needed)
        variable = float(vt.variable_cost_per_km or 0.0) * float(distance_km) * float(vehicles_needed)
        total = fixed + variable
        cand = {
            "vehicle_type_id": vt.id,
            "vehicle_type_name": vt.name,
            "vehicles_needed": int(vehicles_needed),
            "capacity_tons": cap,
            "sbq_tons": sbq,
            "distance_km": float(distance_km),
            "quantity_tons": float(quantity_tons),
            "estimated_cost": float(total),
            "single_vehicle": bool(single_vehicle),
        }
        if best is None or cand["estimated_cost"] < best["estimated_cost"]:
            best = cand

    if best is None:
        raise ValueError("No feasible vehicle type for the requested quantity")
    return best


@logistics_bp.route("/api/logistics/marketplace/quote", methods=["POST"])
@login_required
def marketplace_quote():
    data = request.get_json(silent=True) or {}
    try:
        quantity_tons = float(data.get("quantity_tons"))
        distance_km = float(data.get("distance_km"))
    except Exception:
        return jsonify({"success": False, "message": "quantity_tons and distance_km are required"}), 400

    single_vehicle = bool(data.get("single_vehicle") is True)

    try:
        quote = _quote_lowest_cost(quantity_tons=quantity_tons, distance_km=distance_km, single_vehicle=single_vehicle)
        return jsonify({"success": True, "quote": quote})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@logistics_bp.route("/api/logistics/marketplace/book", methods=["POST"])
@login_required
def marketplace_book():
    data = request.get_json(silent=True) or {}

    try:
        quantity_tons = float(data.get("quantity_tons"))
        distance_km = float(data.get("distance_km"))
    except Exception:
        return jsonify({"success": False, "message": "quantity_tons and distance_km are required"}), 400

    single_vehicle = bool(data.get("single_vehicle") is True)
    from_location = (data.get("from_location") or "").strip() or None
    to_location = (data.get("to_location") or "").strip() or None
    scenario_id = data.get("scenario_id")
    period = data.get("period")

    try:
        quote = _quote_lowest_cost(quantity_tons=quantity_tons, distance_km=distance_km, single_vehicle=single_vehicle)
        vt_id = int(quote["vehicle_type_id"])
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

    vehicle = (
        LogisticsVehicle.query.filter_by(vehicle_type_id=vt_id, is_available=True)
        .order_by(LogisticsVehicle.id.asc())
        .first()
    )

    booking = LogisticsBooking(
        from_location=from_location,
        to_location=to_location,
        distance_km=float(distance_km),
        period=int(period) if period is not None and str(period).strip() != "" else None,
        scenario_id=int(scenario_id) if scenario_id is not None and str(scenario_id).strip() != "" else None,
        quantity_tons=float(quantity_tons),
        single_vehicle=bool(single_vehicle),
        status="booked" if vehicle else "created",
        selected_vehicle_id=(vehicle.id if vehicle else None),
        estimated_cost=float(quote["estimated_cost"]),
    )

    if isinstance(current_user, PumpOwner):
        booking.requester_owner_id = current_user.id
    elif isinstance(current_user, User):
        booking.requester_user_id = current_user.id

    db.session.add(booking)
    if vehicle:
        vehicle.is_available = False
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "booking": {
                "id": booking.id,
                "status": booking.status,
                "estimated_cost": float(booking.estimated_cost or 0.0),
                "selected_vehicle_id": booking.selected_vehicle_id,
            },
            "quote": quote,
        }
    )


def _ingest_token_valid() -> bool:
    configured = (os.environ.get("LOGISTICS_INGEST_TOKEN") or "").strip()
    if not configured:
        return False
    provided = (
        request.headers.get("X-Ingest-Token")
        or request.headers.get("Authorization")
        or request.args.get("token")
        or ""
    ).strip()
    if provided.lower().startswith("bearer "):
        provided = provided[7:].strip()
    return provided == configured


@logistics_bp.route("/logistics/map")
@login_required
def map_view():
    scenario_id = request.args.get("scenario_id")
    return render_template("logistics/map.html", scenario_id=scenario_id)


@logistics_bp.route("/api/logistics/fuelflux_pumps")
@login_required
def fuelflux_pumps():
    try:
        lat = float(request.args.get("lat") or 0)
        lon = float(request.args.get("lon") or 0)
        radius_km = float(request.args.get("radius_km") or 25)
    except Exception:
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    if lat == 0 and lon == 0:
        return jsonify({"success": True, "pumps": []})

    q = Pump.query.filter(Pump.latitude.isnot(None), Pump.longitude.isnot(None))

    if isinstance(current_user, PumpOwner):
        q = q.filter(or_(Pump.is_verified.is_(True), Pump.owner_id == current_user.id))
    else:
        q = q.filter(Pump.is_verified.is_(True))

    pumps = q.all()

    enriched = []
    for p in pumps:
        d = _haversine_km(lat, lon, float(p.latitude), float(p.longitude))
        if d <= radius_km:
            enriched.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "location": p.location,
                    "latitude": float(p.latitude),
                    "longitude": float(p.longitude),
                    "fuel_types": p.fuel_types,
                    "is_verified": bool(p.is_verified),
                    "distance_km": float(d),
                }
            )

    enriched.sort(key=lambda x: x["distance_km"])
    return jsonify({"success": True, "pumps": enriched[:100]})


@logistics_bp.route("/api/logistics/vehicles/latest")
@login_required
def vehicles_latest():
    scope = (request.args.get("scope") or "me").strip().lower()
    vehicle_number = (request.args.get("vehicle_number") or "").strip()

    q = VehicleLocation.query

    if scope == "me":
        filt = _current_scope_filter()
        if not filt:
            return jsonify({"success": True, "vehicles": []})
        q = q.filter_by(**filt)

    if vehicle_number:
        q = q.filter(VehicleLocation.vehicle_number == vehicle_number)

    rows = q.order_by(VehicleLocation.recorded_at.desc()).limit(500).all()

    latest_by_vehicle = {}
    for r in rows:
        if r.vehicle_number not in latest_by_vehicle:
            latest_by_vehicle[r.vehicle_number] = r

    vehicles = [
        {
            "vehicle_number": r.vehicle_number,
            "latitude": float(r.latitude),
            "longitude": float(r.longitude),
            "speed_kmph": float(r.speed_kmph) if r.speed_kmph is not None else None,
            "heading_deg": float(r.heading_deg) if r.heading_deg is not None else None,
            "accuracy_m": float(r.accuracy_m) if r.accuracy_m is not None else None,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in latest_by_vehicle.values()
    ]

    return jsonify({"success": True, "vehicles": vehicles})


@logistics_bp.route("/api/logistics/vehicles/location", methods=["POST"])
@login_required
def post_vehicle_location():
    data = request.get_json(silent=True) or {}

    vehicle_number = (data.get("vehicle_number") or "").strip()
    if not vehicle_number:
        return jsonify({"success": False, "message": "vehicle_number is required"}), 400

    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except Exception:
        return jsonify({"success": False, "message": "Invalid latitude/longitude"}), 400

    speed_kmph = data.get("speed_kmph")
    heading_deg = data.get("heading_deg")
    accuracy_m = data.get("accuracy_m")

    row = VehicleLocation(
        vehicle_number=vehicle_number,
        latitude=latitude,
        longitude=longitude,
        speed_kmph=float(speed_kmph) if speed_kmph is not None and str(speed_kmph).strip() != "" else None,
        heading_deg=float(heading_deg) if heading_deg is not None and str(heading_deg).strip() != "" else None,
        accuracy_m=float(accuracy_m) if accuracy_m is not None and str(accuracy_m).strip() != "" else None,
        source="gps",
    )

    if isinstance(current_user, PumpOwner):
        row.owner_id = current_user.id
    elif isinstance(current_user, User):
        row.user_id = current_user.id

    db.session.add(row)
    db.session.commit()

    return jsonify({"success": True, "message": "Location saved"})


@logistics_bp.route("/api/logistics/vehicles/ingest", methods=["POST"])
@csrf.exempt
def ingest_vehicle_location():
    if not _ingest_token_valid() and not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}

    vehicle_number = (data.get("vehicle_number") or "").strip()
    if not vehicle_number:
        return jsonify({"success": False, "message": "vehicle_number is required"}), 400

    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except Exception:
        return jsonify({"success": False, "message": "Invalid latitude/longitude"}), 400

    speed_kmph = data.get("speed_kmph")
    heading_deg = data.get("heading_deg")
    accuracy_m = data.get("accuracy_m")

    row = VehicleLocation(
        vehicle_number=vehicle_number,
        latitude=latitude,
        longitude=longitude,
        speed_kmph=float(speed_kmph) if speed_kmph is not None and str(speed_kmph).strip() != "" else None,
        heading_deg=float(heading_deg) if heading_deg is not None and str(heading_deg).strip() != "" else None,
        accuracy_m=float(accuracy_m) if accuracy_m is not None and str(accuracy_m).strip() != "" else None,
        source=(data.get("source") or "gps").strip() or "gps",
    )

    if current_user.is_authenticated:
        if isinstance(current_user, PumpOwner):
            row.owner_id = current_user.id
        elif isinstance(current_user, User):
            row.user_id = current_user.id

    db.session.add(row)
    db.session.commit()

    return jsonify({"success": True, "message": "Location ingested"})


@logistics_bp.route("/api/logistics/my_pump/set_location", methods=["POST"])
@login_required
def set_my_pump_location():
    if not isinstance(current_user, PumpOwner):
        return jsonify({"success": False, "message": "Access denied"}), 403

    pump = Pump.query.filter_by(owner_id=current_user.id).first()
    if not pump:
        return jsonify({"success": False, "message": "Pump not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
    except Exception:
        return jsonify({"success": False, "message": "Invalid latitude/longitude"}), 400

    pump.latitude = latitude
    pump.longitude = longitude
    db.session.commit()

    return jsonify({"success": True, "message": "Pump location updated"})


@logistics_bp.route("/api/logistics/public_pumps")
@login_required
def public_pumps():
    enabled = (os.environ.get("ENABLE_PUBLIC_PETROL_PUMPS") or "").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return jsonify({"success": True, "enabled": False, "pumps": []})

    try:
        lat = float(request.args.get("lat") or 0)
        lon = float(request.args.get("lon") or 0)
        radius_km = float(request.args.get("radius_km") or 10)
    except Exception:
        return jsonify({"success": False, "message": "Invalid coordinates."}), 400

    if lat == 0 and lon == 0:
        return jsonify({"success": True, "enabled": True, "pumps": []})

    cache_key = (round(lat, 3), round(lon, 3), round(radius_km, 1))
    cached = _PUBLIC_PUMPS_CACHE.get(cache_key)
    now = time.time()
    if cached and (now - cached["ts"]) < 1800:
        return jsonify({"success": True, "enabled": True, "pumps": cached["data"]})

    radius_m = int(max(100, radius_km * 1000))
    query = f"""
[out:json][timeout:25];
(
  node[\"amenity\"=\"fuel\"](around:{radius_m},{lat},{lon});
);
out center;
""".strip()

    try:
        res = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=20,
        )
        res.raise_for_status()
        data = res.json()
    except Exception:
        return jsonify({"success": True, "enabled": True, "pumps": []})

    pumps = []
    for el in (data.get("elements") or []):
        try:
            plat = float(el.get("lat"))
            plon = float(el.get("lon"))
        except Exception:
            continue
        tags = el.get("tags") or {}
        name = tags.get("name") or "Fuel Station"
        brand = tags.get("brand") or tags.get("operator")
        d = _haversine_km(lat, lon, plat, plon)
        pumps.append(
            {
                "name": name,
                "brand": brand,
                "latitude": plat,
                "longitude": plon,
                "distance_km": float(d),
            }
        )

    pumps.sort(key=lambda x: x["distance_km"])
    pumps = pumps[:100]
    _PUBLIC_PUMPS_CACHE[cache_key] = {"ts": now, "data": pumps}

    return jsonify({"success": True, "enabled": True, "pumps": pumps})
