#config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

    # ---------------- DATABASE ----------------
    # Use DATABASE_URL from environment (for production) or SQLite for local dev
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")
    
    # Fix for Render's postgres:// URL (SQLAlchemy needs postgresql://)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---------------- MAIL ----------------
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = (os.getenv("MAIL_DEFAULT_SENDER_NAME", "Fuel Flux"), MAIL_USERNAME)

    # ---------------- GOOGLE OAUTH ----------------
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

    # ---------------- PAYMENT DETAILS ----------------
    UPI_ID = "ankushscs645852@okaxis"
    BUSINESS_NAME = "Fuel Flux"
    PAYMENT_QR_CODE = "static/images/payment_qr.png"  # Path to QR code image

