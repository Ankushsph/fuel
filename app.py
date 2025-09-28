#app.py
from flask import Flask, redirect, url_for, request, jsonify, render_template
from config import Config
from extensions import db, mail, oauth,csrf
from flask_login import LoginManager
from models import User
from flask_wtf import CSRFProtect    
from flask_cors import CORS
from flask_wtf.csrf import generate_csrf 

app = Flask(__name__)
app.config.from_object(Config)

#  Session cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
app.config['SESSION_COOKIE_SECURE'] = False  # True if running HTTPS


CORS(app, supports_credentials=True, origins=["http://127.0.0.1:5001"])


# Initialize extensions
db.init_app(app)
mail.init_app(app)
oauth.init_app(app)
csrf.init_app(app)


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # your login route endpoint
login_manager.init_app(app)

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')




# User loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    return jsonify({"success": False, "message": "Login required."}), 401

# Import and register blueprints
from auth import auth_bp
from dashboard import dashboard_bp
from vehicle import vehicle_bp
from wallet import wallet_bp
from password_reset import password_bp



app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(vehicle_bp)
app.register_blueprint(wallet_bp)
app.register_blueprint(password_bp)

#testing deduct
@app.route('/pump-owner')
def pumpowner():
    return render_template('testdeduct.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # create tables after init_app
    app.run(debug=True, host='0.0.0.0', port=5001)
