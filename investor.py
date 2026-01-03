"""
Investor Portal Blueprint - FIXED VERSION
Provides comprehensive business analytics and metrics for investors
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, login_user, logout_user
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from extensions import db
from models import (
    User, PumpOwner, Pump, FuelTransaction, WalletLedgerEntry,
    Wallet, PumpWallet, PumpSettlement, Vehicle, PumpSubscription,
    Admin, Employee, Attendance, VehicleVerification, PaymentVerification,
    WalletTopupVerification, PumpRegistrationRequest, Investor
)

investor_bp = Blueprint('investor', __name__, url_prefix='/investor')


@investor_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Investor login page"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('Investor/login.html')
        
        investor = Investor.query.filter_by(email=email).first()
        if investor and investor.check_password(password):
            login_user(investor)
            flash('Welcome to the Investor Portal', 'success')
            return redirect(url_for('investor.dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('Investor/login.html')


@investor_bp.route('/logout')
def logout():
    """Investor logout"""
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('investor.login'))


@investor_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests with OTP"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return render_template('Investor/forgot_password.html')
        
        # Check if investor exists
        investor = Investor.query.filter_by(email=email).first()
        if not investor:
            flash('If an account with this email exists, you will receive a password reset OTP', 'info')
            return render_template('Investor/forgot_password.html')
        
        # Generate OTP
        import random
        import string
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Store OTP (in production, use Redis or database with expiry)
        # For now, we'll store it in session
        from flask import session
        session['reset_otp'] = otp
        session['reset_email'] = email
        session['reset_otp_time'] = datetime.utcnow().timestamp()
        
        # Send OTP email (you'll need to configure email service)
        try:
            # TODO: Configure actual email service like SendGrid, AWS SES, or SMTP
            # For now, just log the OTP for development
            print(f"OTP for {email}: {otp}")
            
            # Send to specific email as requested
            if email == 'web3.ankitrai@gmail.com':
                print(f"OTP sent to web3.ankitrai@gmail.com: {otp}")
                print("NOTE: Configure email service to send actual OTP emails")
            
            flash('A 6-digit OTP has been sent to your email', 'success')
            return redirect(url_for('investor.verify_otp'))
            
        except Exception as e:
            flash('Error sending OTP. Please try again.', 'error')
            return render_template('Investor/forgot_password.html')
    
    return render_template('Investor/forgot_password.html')


@investor_bp.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    """Verify OTP and allow password reset"""
    from flask import session
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not otp or not new_password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('Investor/verify_otp.html')
        
        # Check OTP
        stored_otp = session.get('reset_otp')
        stored_email = session.get('reset_email')
        otp_time = session.get('reset_otp_time', 0)
        
        # Check OTP expiry (15 minutes)
        if datetime.utcnow().timestamp() - otp_time > 900:  # 15 minutes
            flash('OTP has expired. Please request a new one.', 'error')
            return redirect(url_for('investor.forgot_password'))
        
        if otp != stored_otp:
            flash('Invalid OTP. Please try again.', 'error')
            return render_template('Investor/verify_otp.html')
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('Investor/verify_otp.html')
        
        # Update password
        investor = Investor.query.filter_by(email=stored_email).first()
        if investor:
            investor.set_password(new_password)
            db.session.commit()
            
            # Clear session
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('reset_otp_time', None)
            
            flash('Password has been reset successfully. Please login with your new password.', 'success')
            return redirect(url_for('investor.login'))
        else:
            flash('Invalid session. Please try again.', 'error')
            return redirect(url_for('investor.forgot_password'))
    
    return render_template('Investor/verify_otp.html')


@investor_bp.route('/dashboard')
@login_required
def dashboard():
    """Main investor dashboard with comprehensive analytics - FIXED"""
    try:
        # Get date ranges
        today = datetime.utcnow().date()
        thirty_days_ago = today - timedelta(days=30)
        ninety_days_ago = today - timedelta(days=90)
        
        # Core Metrics
        total_cab_owners = User.query.count()
        total_pump_owners = PumpOwner.query.count()
        total_pumps = Pump.query.count()
        total_vehicles = Vehicle.query.count()
        
        # Financial Metrics
        total_driver_wallet_balance = db.session.query(func.sum(Wallet.balance)).scalar() or 0
        total_pump_wallet_balance = db.session.query(func.sum(PumpWallet.balance)).scalar() or 0
        total_transactions = FuelTransaction.query.count()
        
        # Transaction Metrics
        total_revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        today_transactions = FuelTransaction.query.filter(
            func.date(FuelTransaction.created_at) == today,
            FuelTransaction.status == 'settled'
        ).count()
        
        today_revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            func.date(FuelTransaction.created_at) == today,
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        # Monthly Growth (Last 30 days)
        monthly_transactions = FuelTransaction.query.filter(
            FuelTransaction.created_at >= thirty_days_ago,
            FuelTransaction.status == 'settled'
        ).count()
        
        monthly_revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            FuelTransaction.created_at >= thirty_days_ago,
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        # Quarterly Growth (Last 90 days)
        quarterly_transactions = FuelTransaction.query.filter(
            FuelTransaction.created_at >= ninety_days_ago,
            FuelTransaction.status == 'settled'
        ).count()
        
        quarterly_revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            FuelTransaction.created_at >= ninety_days_ago,
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        # Subscription Metrics (FIXED - no amount field)
        active_subscriptions = PumpSubscription.query.filter(
            PumpSubscription.subscription_status == 'active'
        ).count()
        
        # Calculate estimated subscription revenue based on subscription types
        active_subs = PumpSubscription.query.filter(
            PumpSubscription.subscription_status == 'active'
        ).all()
        
        subscription_pricing = {
            'silver': 999,
            'gold': 1999,
            'diamond': 4999
        }
        
        total_subscription_revenue = sum(
            subscription_pricing.get(sub.subscription_type, 0) 
            for sub in active_subs
        )
        
        # Settlement Metrics (FIXED - correct field names)
        pending_settlements = PumpSettlement.query.filter(
            PumpSettlement.status == 'pending'
        ).count()
        
        total_settled_amount = db.session.query(func.sum(PumpSettlement.amount)).filter(
            PumpSettlement.status == 'processed'  # FIXED: use 'processed' instead of 'approved'
        ).scalar() or 0
        
        # Daily Transaction Data for Charts (Last 30 days)
        daily_data = []
        for i in range(30):
            date = today - timedelta(days=i)
            transactions_count = FuelTransaction.query.filter(
                func.date(FuelTransaction.created_at) == date,
                FuelTransaction.status == 'settled'
            ).count()
            
            revenue_count = db.session.query(func.sum(FuelTransaction.amount)).filter(
                func.date(FuelTransaction.created_at) == date,
                FuelTransaction.status == 'settled'
            ).scalar() or 0
            
            daily_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'transactions': transactions_count,
                'revenue': float(revenue_count)
            })
        
        daily_data.reverse()  # Show oldest to newest
        
        # Fuel Type Distribution
        fuel_type_data = db.session.query(
            FuelTransaction.fuel_type,
            func.count(FuelTransaction.id).label('count'),
            func.sum(FuelTransaction.amount).label('revenue')
        ).filter(
            FuelTransaction.status == 'settled'
        ).group_by(FuelTransaction.fuel_type).all()
        
        fuel_distribution = [
            {
                'fuel_type': ft.fuel_type,
                'count': ft.count,
                'revenue': float(ft.revenue)
            }
            for ft in fuel_type_data
        ]
        
        # Top Performing Pumps
        top_pumps = db.session.query(
            Pump.name,
            func.count(FuelTransaction.id).label('transactions'),
            func.sum(FuelTransaction.amount).label('revenue')
        ).join(
            FuelTransaction, Pump.id == FuelTransaction.pump_id
        ).filter(
            FuelTransaction.status == 'settled'
        ).group_by(
            Pump.id, Pump.name
        ).order_by(
            func.sum(FuelTransaction.amount).desc()
        ).limit(10).all()
        
        top_pumps_data = [
            {
                'name': tp.name,
                'transactions': tp.transactions,
                'revenue': float(tp.revenue)
            }
            for tp in top_pumps
        ]
        
        # Growth Metrics (Month over Month)
        last_month_start = today.replace(day=1) - timedelta(days=1)
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_end = last_month_end.replace(day=28) if last_month_end.month == 2 else last_month_end.replace(day=30)
        
        last_month_transactions = FuelTransaction.query.filter(
            FuelTransaction.created_at >= last_month_start,
            FuelTransaction.created_at <= last_month_end,
            FuelTransaction.status == 'settled'
        ).count()
        
        last_month_revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            FuelTransaction.created_at >= last_month_start,
            FuelTransaction.created_at <= last_month_end,
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        # Safe division to avoid division by zero
        mom_transaction_growth = ((monthly_transactions - last_month_transactions) / max(last_month_transactions, 1)) * 100
        mom_revenue_growth = ((monthly_revenue - last_month_revenue) / max(last_month_revenue, 1)) * 100
        
        # Average transaction value
        avg_transaction_value = total_revenue / max(total_transactions, 1)
        
        return render_template('Investor/dashboard.html', **{
            # Core Metrics
            'total_cab_owners': total_cab_owners,
            'total_pump_owners': total_pump_owners,
            'total_pumps': total_pumps,
            'total_vehicles': total_vehicles,
            
            # Financial Metrics
            'total_driver_wallet_balance': total_driver_wallet_balance,
            'total_pump_wallet_balance': total_pump_wallet_balance,
            'total_transactions': total_transactions,
            'total_revenue': total_revenue,
            
            # Today's Metrics
            'today_transactions': today_transactions,
            'today_revenue': today_revenue,
            
            # Period Metrics
            'monthly_transactions': monthly_transactions,
            'monthly_revenue': monthly_revenue,
            'quarterly_transactions': quarterly_transactions,
            'quarterly_revenue': quarterly_revenue,
            
            # Subscription Metrics
            'active_subscriptions': active_subscriptions,
            'total_subscription_revenue': total_subscription_revenue,
            
            # Settlement Metrics
            'pending_settlements': pending_settlements,
            'total_settled_amount': total_settled_amount,
            
            # Chart Data
            'daily_data': daily_data,
            'fuel_distribution': fuel_distribution,
            'top_pumps_data': top_pumps_data,
            
            # Growth Metrics
            'mom_transaction_growth': round(mom_transaction_growth, 2),
            'mom_revenue_growth': round(mom_revenue_growth, 2),
            'avg_transaction_value': avg_transaction_value,
            
            # Dates
            'today': today.strftime('%Y-%m-%d'),
            'thirty_days_ago': thirty_days_ago.strftime('%Y-%m-%d'),
        })
        
    except Exception as e:
        # Log the error and show a user-friendly message
        print(f"Error in investor dashboard: {str(e)}")
        flash('There was an error loading the dashboard. Please try again.', 'error')
        return render_template('Investor/dashboard.html', **{
            # Default values to prevent template errors
            'total_cab_owners': 0,
            'total_pump_owners': 0,
            'total_pumps': 0,
            'total_vehicles': 0,
            'total_driver_wallet_balance': 0,
            'total_pump_wallet_balance': 0,
            'total_transactions': 0,
            'total_revenue': 0,
            'today_transactions': 0,
            'today_revenue': 0,
            'monthly_transactions': 0,
            'monthly_revenue': 0,
            'quarterly_transactions': 0,
            'quarterly_revenue': 0,
            'active_subscriptions': 0,
            'total_subscription_revenue': 0,
            'pending_settlements': 0,
            'total_settled_amount': 0,
            'daily_data': [],
            'fuel_distribution': [],
            'top_pumps_data': [],
            'mom_transaction_growth': 0,
            'mom_revenue_growth': 0,
            'avg_transaction_value': 0,
            'today': datetime.utcnow().strftime('%Y-%m-%d'),
            'thirty_days_ago': (datetime.utcnow().date() - timedelta(days=30)).strftime('%Y-%m-%d'),
        })


@investor_bp.route('/api/revenue-chart')
@login_required
def revenue_chart_api():
    """API endpoint for revenue chart data"""
    days = request.args.get('days', 30, type=int)
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days)
    
    data = []
    for i in range(days):
        date = today - timedelta(days=i)
        revenue = db.session.query(func.sum(FuelTransaction.amount)).filter(
            func.date(FuelTransaction.created_at) == date,
            FuelTransaction.status == 'settled'
        ).scalar() or 0
        
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(revenue)
        })
    
    data.reverse()
    return jsonify({'data': data})


@investor_bp.route('/api/transaction-chart')
@login_required
def transaction_chart_api():
    """API endpoint for transaction volume chart data"""
    days = request.args.get('days', 30, type=int)
    today = datetime.utcnow().date()
    
    data = []
    for i in range(days):
        date = today - timedelta(days=i)
        transactions = FuelTransaction.query.filter(
            func.date(FuelTransaction.created_at) == date,
            FuelTransaction.status == 'settled'
        ).count()
        
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'transactions': transactions
        })
    
    data.reverse()
    return jsonify({'data': data})


@investor_bp.route('/api/fuel-distribution')
@login_required
def fuel_distribution_api():
    """API endpoint for fuel type distribution"""
    data = db.session.query(
        FuelTransaction.fuel_type,
        func.count(FuelTransaction.id).label('count'),
        func.sum(FuelTransaction.amount).label('revenue')
    ).filter(
        FuelTransaction.status == 'settled'
    ).group_by(FuelTransaction.fuel_type).all()
    
    return jsonify({
        'data': [
            {
                'fuel_type': d.fuel_type,
                'count': d.count,
                'revenue': float(d.revenue)
            }
            for d in data
        ]
    })


@investor_bp.route('/api/top-pumps')
@login_required
def top_pumps_api():
    """API endpoint for top performing pumps"""
    data = db.session.query(
        Pump.name,
        func.count(FuelTransaction.id).label('transactions'),
        func.sum(FuelTransaction.amount).label('revenue')
    ).join(
        FuelTransaction, Pump.id == FuelTransaction.pump_id
    ).filter(
        FuelTransaction.status == 'settled'
    ).group_by(
        Pump.id, Pump.name
    ).order_by(
        func.sum(FuelTransaction.amount).desc()
    ).limit(10).all()
    
    return jsonify({
        'data': [
            {
                'name': d.name,
                'transactions': d.transactions,
                'revenue': float(d.revenue)
            }
            for d in data
        ]
    })
