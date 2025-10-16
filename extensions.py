#extensions.py
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

db = SQLAlchemy()
mail = Mail()
oauth = OAuth()
csrf = CSRFProtect() 
migrate = Migrate()