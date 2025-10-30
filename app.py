
# # app.py
# import os
# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
# from dotenv import load_dotenv
# from sqlalchemy import event
# from sqlalchemy.engine import Engine
# from routes_ai import ai_bp
# load_dotenv()

# app = Flask(__name__)
# app.secret_key = "demo"
# app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///change_control.db")
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# app.register_blueprint(ai_bp)

# db = SQLAlchemy(app)

# # Ensure SQLite enforces foreign keys
# @event.listens_for(Engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     try:
#         cursor = dbapi_connection.cursor()
#         cursor.execute("PRAGMA foreign_keys=ON")
#         cursor.close()
#     except Exception:
#         pass


# app.py
import os
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine

from extensions import db  # <-- import here

load_dotenv()

app = Flask(__name__)
app.secret_key = "demo"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///change_control.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)  # <-- initialize here

# Ensure SQLite enforces foreign keys
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass

# Import blueprints AFTER app & db are ready
from routes_ai import ai_bp
from routes_core import core_bp
from routes_ui import ui_bp
app.register_blueprint(ui_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(core_bp)