"""
Production-ready escrow service for fuel transactions.
Handles atomic wallet movements, immutable ledger entries, and verification flows.
"""
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (
    FuelTransaction, Wallet, PumpWallet, WalletLedgerEntry,
    User, PumpOwner, Pump
)


class EscrowError(Exception):
    """Base escrow service exception"""
    pass


class InsufficientFundsError(EscrowError):
    """Raised when driver wallet lacks sufficient balance"""
    pass


class VerificationRequiredError(EscrowError):
    """Raised when a transaction requires verification before settlement"""
    pass


class InvalidStateError(EscrowError):
    """Raised when operation is not allowed in current state"""
    pass


def _create_ledger_entry(group_uuid: str, event_type: str, direction: str,
                         wallet_type: str, wallet_id: int, amount: float,
                         balance_after: float, reference_id: Optional[int]=None,
                         reference_type: Optional[str]=None) -> WalletLedgerEntry:
    """Create an immutable ledger entry"""
    entry = WalletLedgerEntry(
        group_uuid=group_uuid,
        event_type=event_type,
        direction=direction,
        wallet_type=wallet_type,
        wallet_id=wallet_id,
        amount=amount,
        balance_after=balance_after,
        reference_id=reference_id,
        reference_type=reference_type
    )
    db.session.add(entry)
    return entry


def _find_driver_by_vehicle(vehicle_number: str) -> Optional[User]:
    """Find driver (cab owner) by vehicle number. In real world, this could be:
    - Exact match in Vehicle table (license field)
    - Fuzzy match via external fleet management API
    - ANPR-linked registry
    """
    from models import Vehicle
    vehicle = Vehicle.query.filter_by(license=vehicle_number.upper()).first()
    return vehicle.user if vehicle else None


def create_fuel_transaction(pump_id: int, vehicle_number: str, fuel_type: str,
                           quantity_litres: float, unit_price: float,
                           attendant_id: int, verification_level: str = "manual",
                           extra_data: Optional[Dict[str, Any]] = None) -> FuelTransaction:
    """
    Step 3: Create a fuel transaction record.
    No money moves yet. Just a pending transaction.
    """
    amount = round(quantity_litres * unit_price, 2)
    transaction = FuelTransaction(
        pump_id=pump_id,
        vehicle_number=vehicle_number.upper(),
        fuel_type=fuel_type,
        quantity_litres=quantity_litres,
        unit_price=unit_price,
        amount=amount,
        status="pending_verification",
        verification_level=verification_level,
        attendant_id=attendant_id,
        extra_data=extra_data or {}
    )
    db.session.add(transaction)
    db.session.flush()  # Get ID without committing
    current_app.logger.info(f"Created fuel transaction {transaction.id} for {vehicle_number} amount {amount}")
    return transaction


def verify_fuel_transaction(transaction_id: int, verifier_id: int,
                           verification_notes: Optional[str] = None) -> FuelTransaction:
    """
    Step 4: Mark a transaction as verified.
    In Phase 1 (manual), this is done by attendant/supervisor.
    """
    transaction = FuelTransaction.query.get_or_404(transaction_id)
    if transaction.status != "pending_verification":
        raise InvalidStateError(f"Transaction {transaction_id} is not pending verification")
    
    transaction.status = "verified"
    transaction.verifier_id = verifier_id
    transaction.verified_at = datetime.utcnow()
    if verification_notes:
        if not transaction.extra_data:
            transaction.extra_data = {}
        transaction.extra_data["verification_notes"] = verification_notes
    
    db.session.add(transaction)
    current_app.logger.info(f"Verified fuel transaction {transaction_id} by verifier {verifier_id}")
    return transaction


def settle_fuel_transaction(transaction_id: int) -> Tuple[FuelTransaction, str]:
    """
    Step 5: Atomic escrow release.
    Debits driver wallet, credits pump wallet, creates immutable ledger entries.
    If vehicle is not linked to a driver, marks transaction as 'failed' instead of error.
    """
    transaction = FuelTransaction.query.get_or_404(transaction_id)
    if transaction.status != "verified":
        raise VerificationRequiredError(f"Transaction {transaction_id} must be verified before settlement")
    
    # Find driver by vehicle number
    driver = _find_driver_by_vehicle(transaction.vehicle_number)
    if not driver or not driver.wallet:
        # Graceful fallback: mark as failed instead of throwing error
        transaction.status = "failed"
        transaction.extra_data = transaction.extra_data or {}
        transaction.extra_data["failure_reason"] = "Vehicle not linked to any driver wallet"
        db.session.add(transaction)
        current_app.logger.warning(f"Settlement failed for transaction {transaction_id}: vehicle {transaction.vehicle_number} not linked to driver")
        return transaction, None
    
    if driver.wallet.balance < transaction.amount:
        # Mark as failed due to insufficient funds
        transaction.status = "failed"
        transaction.extra_data = transaction.extra_data or {}
        transaction.extra_data["failure_reason"] = f"Insufficient driver balance: {driver.wallet.balance} < {transaction.amount}"
        db.session.add(transaction)
        current_app.logger.warning(f"Settlement failed for transaction {transaction_id}: insufficient driver balance")
        return transaction, None
    
    # Find pump wallet
    pump = Pump.query.get(transaction.pump_id)
    if not pump or not pump.owner or not pump.owner.wallet:
        raise EscrowError(f"Pump wallet not found for pump {transaction.pump_id}")
    
    pump_wallet = pump.owner.wallet
    
    # Generate a group UUID for this transaction
    group_uuid = str(uuid.uuid4())
    
    # Capture balances before changes
    driver_balance_before = driver.wallet.balance
    pump_balance_before = pump_wallet.balance
    
    # Perform atomic wallet updates
    driver.wallet.balance -= transaction.amount
    pump_wallet.balance += transaction.amount
    
    # Create immutable ledger entries
    _create_ledger_entry(
        group_uuid=group_uuid,
        event_type="fuel_sale",
        direction="debit",
        wallet_type="driver_wallet",
        wallet_id=driver.wallet.id,
        amount=transaction.amount,
        balance_after=driver.wallet.balance,
        reference_id=transaction.id,
        reference_type="fuel_transaction"
    )
    
    _create_ledger_entry(
        group_uuid=group_uuid,
        event_type="fuel_sale",
        direction="credit",
        wallet_type="pump_wallet",
        wallet_id=pump_wallet.id,
        amount=transaction.amount,
        balance_after=pump_wallet.balance,
        reference_id=transaction.id,
        reference_type="fuel_transaction"
    )
    
    # Mark transaction as settled
    transaction.status = "settled"
    transaction.settled_at = datetime.utcnow()
    
    # Add settlement metadata to extra_data
    if not transaction.extra_data:
        transaction.extra_data = {}
    transaction.extra_data["settlement"] = {
        "group_uuid": group_uuid,
        "driver_balance_before": driver_balance_before,
        "driver_balance_after": driver.wallet.balance,
        "pump_balance_before": pump_balance_before,
        "pump_balance_after": pump_wallet.balance,
        "settled_at": transaction.settled_at.isoformat()
    }
    
    db.session.add(transaction)
    
    current_app.logger.info(
        f"Settled fuel transaction {transaction.id}: "
        f"-{transaction.amount} from driver {driver.id}, "
        f"+{transaction.amount} to pump {pump.id} (group {group_uuid})"
    )
    
    return transaction, group_uuid


def get_transaction_receipt(transaction_id: int) -> Dict[str, Any]:
    """
    Step 6: Generate a non-editable digital receipt.
    """
    transaction = FuelTransaction.query.get_or_404(transaction_id)
    pump = transaction.pump
    driver = _find_driver_by_vehicle(transaction.vehicle_number)
    
    receipt = {
        "transaction_id": transaction.id,
        "group_uuid": None,
        "vehicle_number": transaction.vehicle_number,
        "fuel_type": transaction.fuel_type,
        "quantity_litres": transaction.quantity_litres,
        "unit_price": transaction.unit_price,
        "amount": transaction.amount,
        "currency": "INR",
        "pump": {
            "id": pump.id,
            "name": pump.name,
            "location": pump.location
        },
        "status": transaction.status,
        "created_at": transaction.created_at.isoformat(),
        "verified_at": transaction.verified_at.isoformat() if transaction.verified_at else None,
        "settled_at": transaction.settled_at.isoformat() if transaction.settled_at else None,
        "verification_level": transaction.verification_level,
        "attendant": transaction.attendant.full_name if transaction.attendant else None,
        "verifier": transaction.verifier.full_name if transaction.verifier else None,
        "driver": {
            "id": driver.id,
            "name": driver.full_name,
            "email": driver.email
        } if driver else None,
        "ledger_entries": []
    }
    
    # Include settlement UUID if available
    if transaction.extra_data and "settlement" in transaction.extra_data:
        receipt["group_uuid"] = transaction.extra_data["settlement"]["group_uuid"]
    
    # Fetch ledger entries for this transaction
    entries = WalletLedgerEntry.query.filter_by(
        reference_id=transaction.id,
        reference_type="fuel_transaction"
    ).order_by(WalletLedgerEntry.created_at).all()
    
    for entry in entries:
        receipt["ledger_entries"].append({
            "direction": entry.direction,
            "wallet_type": entry.wallet_type,
            "amount": entry.amount,
            "balance_after": entry.balance_after,
            "created_at": entry.created_at.isoformat()
        })
    
    return receipt


def list_pump_transactions(pump_id: int, status: Optional[str] = None,
                         limit: int = 100, offset: int = 0) -> Tuple[list, int]:
    """List fuel transactions for a pump, optionally filtered by status"""
    query = FuelTransaction.query.filter_by(pump_id=pump_id)
    if status:
        query = query.filter_by(status=status)
    
    total = query.count()
    transactions = query.order_by(FuelTransaction.created_at.desc()).offset(offset).limit(limit).all()
    
    return transactions, total


def list_driver_transactions(driver_id: int, limit: int = 100, offset: int = 0) -> Tuple[list, int]:
    """List fuel transactions for a driver (by vehicle numbers they own)"""
    from models import Vehicle
    
    # Get all vehicle numbers for this driver
    vehicles = Vehicle.query.filter_by(user_id=driver_id).all()
    vehicle_numbers = [v.license.upper() for v in vehicles]
    
    if not vehicle_numbers:
        return [], 0
    
    query = FuelTransaction.query.filter(FuelTransaction.vehicle_number.in_(vehicle_numbers))
    total = query.count()
    transactions = query.order_by(FuelTransaction.created_at.desc()).offset(offset).limit(limit).all()
    
    return transactions, total


def get_pending_verifications_for_pump(pump_id: int) -> list:
    """Get transactions pending verification for a specific pump"""
    return FuelTransaction.query.filter_by(
        pump_id=pump_id,
        status="pending_verification"
    ).order_by(FuelTransaction.created_at.asc()).all()


def get_daily_sales_for_pump(pump_id: int, date: datetime) -> Dict[str, Any]:
    """Get daily sales summary for a pump"""
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    transactions = FuelTransaction.query.filter(
        FuelTransaction.pump_id == pump_id,
        FuelTransaction.created_at >= start,
        FuelTransaction.created_at <= end,
        FuelTransaction.status == "settled"
    ).all()
    
    total_amount = sum(t.amount for t in transactions)
    total_quantity = sum(t.quantity_litres for t in transactions)
    
    return {
        "date": date.date().isoformat(),
        "pump_id": pump_id,
        "total_transactions": len(transactions),
        "total_amount": round(total_amount, 2),
        "total_quantity": round(total_quantity, 2),
        "transactions": [
            {
                "id": t.id,
                "vehicle_number": t.vehicle_number,
                "fuel_type": t.fuel_type,
                "quantity": t.quantity_litres,
                "amount": t.amount,
                "settled_at": t.settled_at.isoformat() if t.settled_at else None
            }
            for t in transactions
        ]
    }
