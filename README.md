# Fuel Flux - Petrol Pump Management System

A comprehensive Flask-based web application for managing petrol pumps with advanced features including OCR receipt processing, subscription management, and vehicle verification.

## Features

- 🔐 **Dual Authentication**: Separate portals for Users and Pump Owners
- 🏪 **Pump Management**: Register and manage multiple pump stations
- 📊 **Dashboard Analytics**: Real-time data visualization
- 🚗 **Vehicle Verification**: RTSP stream integration for vehicle counting
- 💳 **Subscription System**: Tiered plans (Silver/Gold/Diamond) with Razorpay payment
- 🧾 **OCR Receipt Processing**: Advanced receipt data extraction using EasyOCR
- 📈 **Daily Comparison**: Compare sales data between receipts
- 🧪 **Density Calculator**: Fuel density calculations at standard temperature

## Tech Stack

- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Database**: PostgreSQL (production) / SQLite (development)
- **OCR**: EasyOCR, OpenCV
- **Payment**: Razorpay
- **Auth**: Google OAuth 2.0
- **Deployment**: Render.com

## Environment Variables

Required environment variables for deployment:

```
DATABASE_URL=postgresql://...
SECRET_KEY=your_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
RAZORPAY_KEY_ID=your_razorpay_key
RAZORPAY_KEY_SECRET=your_razorpay_secret
MAIL_USERNAME=your_email
MAIL_PASSWORD=your_email_password
FLASK_ENV=production
```

## Local Development

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env` file

4. Run the application:
```bash
python app.py
```

5. Access at `http://localhost:5001`

## Deployment to Render

See deployment guide in project documentation.

## Project Structure

```
Flue_flex_pvt_ltd_/
├── app.py                 # Main application file
├── config.py             # Configuration settings
├── models.py             # Database models
├── requirements.txt      # Python dependencies
├── Procfile             # Render deployment config
├── templates/           # HTML templates
├── static/              # CSS, JS, images
├── lib/                 # Custom libraries (OCR)
└── uploads/             # Receipt uploads directory
```

## License

Proprietary - All Rights Reserved

## Support

For issues or questions, contact the development team.

