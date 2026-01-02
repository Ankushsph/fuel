import uuid
from datetime import datetime

from extensions import db
from config import Config
from models import Wallet, EscrowAccount, WalletTopup, WalletLedgerEntry

try:
    import razorpay  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    razorpay = None


def _get_or_create_wallet(user):
    """Ensure the given user has a Wallet row and return it."""
    if not getattr(user, "wallet", None):
        wallet = Wallet(user_id=user.id, balance=0.0)
        db.session.add(wallet)
        db.session.flush()
        user.wallet = wallet
    return user.wallet


def _get_main_escrow():
    """Return the main escrow account, creating it if needed."""
    account = EscrowAccount.query.filter_by(name="main").first()
    if not account:
        account = EscrowAccount(name="main", balance=0.0)
        db.session.add(account)
        db.session.flush()
    return account


def create_wallet_topup_order(user, amount):
    """Create a Razorpay order and a pending WalletTopup record."""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    if razorpay is None:
        raise RuntimeError("Razorpay library not installed on server")

    wallet = _get_or_create_wallet(user)
    txn_uuid = str(uuid.uuid4())

    client = razorpay.Client(
        auth=(
            Config.RAZORPAY_KEY_ID or "",
            Config.RAZORPAY_KEY_SECRET or "",
        )
    )

    order_data = {
        "amount": int(amount * 100),
        "currency": "INR",
        "receipt": "wallet_%s_%s" % (user.id, datetime.utcnow().timestamp()),
        "notes": {
            "user_id": str(user.id),
            "wallet_id": str(wallet.id),
            "txn_uuid": txn_uuid,
        },
    }
    order = client.order.create(data=order_data)

    topup = WalletTopup(
        driver_id=user.id,
        wallet_id=wallet.id,
        amount=amount,
        currency="INR",
        txn_uuid=txn_uuid,
        status="created",
        razorpay_order_id=order["id"],
    )
    db.session.add(topup)
    db.session.commit()

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order.get("currency", "INR"),
        "txn_uuid": txn_uuid,
        "key_id": Config.RAZORPAY_KEY_ID,
    }


def confirm_wallet_topup_payment(user, txn_uuid, amount, razorpay_payment_id, razorpay_order_id, razorpay_signature=None):
    """Mark a top-up as paid and move funds into driver wallet + escrow.

    This function is idempotent with respect to txn_uuid.
    """
    wallet = _get_or_create_wallet(user)
    escrow = _get_main_escrow()

    with db.session.begin():
        topup = (
            WalletTopup.query.filter_by(txn_uuid=txn_uuid)
            .with_for_update()
            .first()
        )
        if not topup:
            raise ValueError("Unknown top-up transaction")

        if topup.driver_id != user.id:
            raise ValueError("Top-up does not belong to this user")

        # Idempotent: if already paid, just return current balance
        if topup.status == "paid":
            return wallet.balance

        # Basic tampering protection
        if abs(topup.amount - float(amount)) > 0.01:
            raise ValueError("Amount mismatch for this transaction")

        topup.status = "paid"
        topup.razorpay_payment_id = razorpay_payment_id
        topup.razorpay_order_id = razorpay_order_id
        topup.razorpay_signature = razorpay_signature
        topup.paid_at = datetime.utcnow()

        wallet.balance += topup.amount
        escrow.balance += topup.amount

        group_uuid = str(uuid.uuid4())

        # Escrow credit entry
        escrow_entry = WalletLedgerEntry(
            group_uuid=group_uuid,
            event_type="TOPUP",
            direction="credit",
            account_type="escrow",
            escrow_account_id=escrow.id,
            amount=topup.amount,
            balance_after=escrow.balance,
            topup_id=topup.id,
        )
        db.session.add(escrow_entry)

        # Driver credit entry
        driver_entry = WalletLedgerEntry(
            group_uuid=group_uuid,
            event_type="TOPUP",
            direction="credit",
            account_type="driver",
            driver_wallet_id=wallet.id,
            amount=topup.amount,
            balance_after=wallet.balance,
            topup_id=topup.id,
        )
        db.session.add(driver_entry)

    return wallet.balance


def get_driver_wallet_transactions(user, page=1, per_page=20):
    """Return paginated ledger entries for the driver's wallet."""
    wallet = _get_or_create_wallet(user)

    query = (
        WalletLedgerEntry.query
        .filter_by(account_type="driver", driver_wallet_id=wallet.id)
        .order_by(WalletLedgerEntry.created_at.desc())
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for entry in pagination.items:
        items.append(
            {
                "event_type": entry.event_type,
                "direction": entry.direction,
                "amount": entry.amount,
                "balance_after": entry.balance_after,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "group_uuid": entry.group_uuid,
            }
        )

    return {
        "transactions": items,
        "page": pagination.page,
        "pages": pagination.pages,
        "total": pagination.total,
    }
