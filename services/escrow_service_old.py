import uuid
from datetime import datetime

from extensions import db
from models import (
    User,
    Vehicle,
    Pump,
    PumpOwner,
    PumpWallet,
    Wallet,
    EscrowAccount,
    FuelTransaction,
    WalletLedgerEntry,
)


def _get_or_create_driver_wallet(driver):
    if not getattr(driver, "wallet", None):
        wallet = Wallet(user_id=driver.id, balance=0.0)
        db.session.add(wallet)
        db.session.flush()
        driver.wallet = wallet
    return driver.wallet


def _get_or_create_pump_wallet(owner):
    if not getattr(owner, "wallet", None):
        wallet = PumpWallet(owner_id=owner.id, balance=0.0)
        db.session.add(wallet)
        db.session.flush()
        owner.wallet = wallet
    return owner.wallet


def _get_main_escrow():
    account = EscrowAccount.query.filter_by(name="main").first()
    if not account:
        account = EscrowAccount(name="main", balance=0.0)
        db.session.add(account)
        db.session.flush()
    return account


def process_fuel_transaction_for_pump(
    pump_owner,
    pump_id,
    vehicle_number,
    fuel_type,
    quantity_litres,
    unit_price,
    txn_uuid=None,
    attendant_id=None,
):
    """Perform a closed-loop fuel transaction: driver wallet -> pump wallet.

    Idempotent on txn_uuid.
    """
    if quantity_litres <= 0 or unit_price <= 0:
        raise ValueError("Quantity and unit price must be positive")

    amount = quantity_litres * unit_price
    fuel_type = (fuel_type or "").strip()

    pump = Pump.query.filter_by(id=pump_id, owner_id=pump_owner.id).first()
    if not pump:
        raise ValueError("Pump not found or not owned by current user")

    vehicle = Vehicle.query.filter_by(license=vehicle_number.upper()).first()
    if not vehicle:
        raise ValueError("Vehicle not registered in FuelFlux")

    driver = User.query.get(vehicle.user_id)
    if not driver:
        raise ValueError("Driver user not found for this vehicle")

    if not txn_uuid:
        txn_uuid = str(uuid.uuid4())

    _get_main_escrow()  # ensure escrow exists; balance not changed for fuel flow
    driver_wallet = _get_or_create_driver_wallet(driver)
    pump_wallet = _get_or_create_pump_wallet(pump_owner)

    with db.session.begin():
        existing = (
            FuelTransaction.query.filter_by(txn_uuid=txn_uuid)
            .with_for_update()
            .first()
        )
        if existing and existing.status == "completed":
            return _fuel_tx_to_receipt(existing, driver_wallet, pump_wallet)

        if driver_wallet.balance < amount:
            raise ValueError(
                "Insufficient balance. Required ₹%.2f, available ₹%.2f"
                % (amount, driver_wallet.balance)
            )

        fuel_tx = existing
        if not fuel_tx:
            fuel_tx = FuelTransaction(
                txn_uuid=txn_uuid,
                driver_id=driver.id,
                driver_wallet_id=driver_wallet.id,
                pump_id=pump.id,
                pump_owner_id=pump_owner.id,
                pump_wallet_id=pump_wallet.id,
                vehicle_number=vehicle_number.upper(),
                fuel_type=fuel_type,
                quantity_litres=quantity_litres,
                unit_price=unit_price,
                amount=amount,
                status="initiated",
                attendant_id=attendant_id,
            )
            db.session.add(fuel_tx)
            db.session.flush()

        driver_wallet.balance -= amount
        pump_wallet.balance += amount

        fuel_tx.status = "completed"
        fuel_tx.verified_at = datetime.utcnow()
        if not fuel_tx.receipt_number:
            fuel_tx.receipt_number = "FTX-%08d" % fuel_tx.id

        group_uuid = str(uuid.uuid4())

        driver_entry = WalletLedgerEntry(
            group_uuid=group_uuid,
            event_type="FUEL",
            direction="debit",
            account_type="driver",
            driver_wallet_id=driver_wallet.id,
            amount=amount,
            balance_after=driver_wallet.balance,
            fuel_transaction_id=fuel_tx.id,
        )
        db.session.add(driver_entry)

        pump_entry = WalletLedgerEntry(
            group_uuid=group_uuid,
            event_type="FUEL",
            direction="credit",
            account_type="pump",
            pump_wallet_id=pump_wallet.id,
            amount=amount,
            balance_after=pump_wallet.balance,
            fuel_transaction_id=fuel_tx.id,
        )
        db.session.add(pump_entry)

    return _fuel_tx_to_receipt(fuel_tx, driver_wallet, pump_wallet)


def _fuel_tx_to_receipt(fuel_tx, driver_wallet, pump_wallet):
    return {
        "fuel_transaction": {
            "id": fuel_tx.id,
            "txn_uuid": fuel_tx.txn_uuid,
            "receipt_number": fuel_tx.receipt_number,
            "vehicle_number": fuel_tx.vehicle_number,
            "fuel_type": fuel_tx.fuel_type,
            "quantity_litres": fuel_tx.quantity_litres,
            "unit_price": fuel_tx.unit_price,
            "amount": fuel_tx.amount,
            "status": fuel_tx.status,
            "created_at": fuel_tx.created_at.isoformat() if fuel_tx.created_at else None,
            "verified_at": fuel_tx.verified_at.isoformat() if fuel_tx.verified_at else None,
        },
        "driver_balance": round(driver_wallet.balance, 2),
        "pump_wallet_balance": round(pump_wallet.balance, 2),
        "digital_receipt": {
            "receipt_number": fuel_tx.receipt_number,
            "driver_email": fuel_tx.driver.email if fuel_tx.driver else None,
            "pump_name": fuel_tx.pump.name if fuel_tx.pump else None,
            "pump_location": fuel_tx.pump.location if fuel_tx.pump else None,
            "vehicle_number": fuel_tx.vehicle_number,
            "fuel_type": fuel_tx.fuel_type,
            "quantity_litres": fuel_tx.quantity_litres,
            "unit_price": fuel_tx.unit_price,
            "amount": fuel_tx.amount,
            "timestamp": fuel_tx.verified_at.isoformat() if fuel_tx.verified_at else None,
        },
    }


def get_driver_fuel_history(driver):
    txs = (
        FuelTransaction.query
        .filter_by(driver_id=driver.id)
        .order_by(FuelTransaction.created_at.desc())
        .limit(100)
        .all()
    )
    result = []
    for t in txs:
        result.append(
            {
                "receipt_number": t.receipt_number,
                "vehicle_number": t.vehicle_number,
                "pump_name": t.pump.name if t.pump else None,
                "pump_location": t.pump.location if t.pump else None,
                "fuel_type": t.fuel_type,
                "quantity_litres": t.quantity_litres,
                "amount": t.amount,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return {"transactions": result}


def get_pump_fuel_history(owner, pump_id=None):
    query = FuelTransaction.query.filter_by(pump_owner_id=owner.id)
    if pump_id:
        query = query.filter_by(pump_id=pump_id)
    txs = query.order_by(FuelTransaction.created_at.desc()).limit(200).all()

    result = []
    for t in txs:
        result.append(
            {
                "receipt_number": t.receipt_number,
                "vehicle_number": t.vehicle_number,
                "fuel_type": t.fuel_type,
                "quantity_litres": t.quantity_litres,
                "amount": t.amount,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return {"transactions": result}
