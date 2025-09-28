from flask import Blueprint, redirect, url_for, request, flash
from models import db, Vehicle
from flask_login import current_user, login_required

vehicle_bp = Blueprint("vehicle", __name__)

@vehicle_bp.route("/add_vehicle", methods=["POST"])
@login_required
def add_vehicle():
    # Get all form inputs
    name = request.form.get("name", "").strip()
    type_ = request.form.get("type", "").strip()
    year = request.form.get("year", "").strip()
    license_plate = request.form.get("license", "").strip()
    fuel_type = request.form.get("fuel_type", "").strip()

    # Validate
    if not all([name, type_, year, license_plate, fuel_type]):
        flash("All fields are required.", "error")
        return redirect(url_for("dashboard.dashboard"))

    # Create and add vehicle
    vehicle = Vehicle(
        name=name,
        type=type_,
        year=year,
        license=license_plate,
        fuel_type=fuel_type,
        user_id=current_user.id
    )
    db.session.add(vehicle)
    db.session.commit()
    flash("Vehicle added successfully!", "success")
    return redirect(url_for("dashboard.dashboard"))


@vehicle_bp.route("/remove_vehicle/<int:vehicle_id>", methods=["POST"])
@login_required
def remove_vehicle(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if vehicle and vehicle.user_id == current_user.id:
        db.session.delete(vehicle)
        db.session.commit()
        flash("Vehicle removed successfully!", "success")
    else:
        flash("Vehicle not found or unauthorized.", "error")
    return redirect(url_for("dashboard.dashboard"))
