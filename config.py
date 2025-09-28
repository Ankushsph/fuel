#config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

    # ---------------- DATABASE ----------------
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://fueluser:fuelpass123@localhost:3306/fuelflux'
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

