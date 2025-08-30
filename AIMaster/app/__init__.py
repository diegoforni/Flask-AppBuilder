import logging

from flask import Flask
from flask_cors import CORS
from flask_appbuilder import AppBuilder, SQLA

"""
 Logging configuration
"""
logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger().setLevel(logging.DEBUG)

app = Flask(__name__)
app.config.from_object("config")
# initialize Flask-AppBuilder SQLA db
db = SQLA(app)
appbuilder = AppBuilder(app, db.session)

# Enable CORS for mobile app calls
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
)

# After AppBuilder is created, augment its user model to include credits
try:
    # Import local mixin
    from .models import CreditsMixin
    # Get the FAB user model class
    User = appbuilder.get_user_model()
    # If credits attribute not present, add it dynamically
    if not hasattr(User, 'credits'):
        # create a new subclass to include credits column while keeping same table
        NewUser = type('NewUser', (CreditsMixin, User), {})
        # Replace the user model in the security manager where possible
        try:
            appbuilder.sm.user_model = NewUser
        except Exception:
            pass

    # ensure tables exist; this will create missing tables for new deployments
    with app.app_context():
        db.create_all()
        # For existing sqlite DBs, attempt to add column if missing
        try:
            engine = db.engine
            inspector = engine.dialect.get_inspector(engine)
        except Exception:
            inspector = None
        try:
            # Use raw SQL to add column if it doesn't exist (SQLite compatible ADD COLUMN)
            from sqlalchemy import text
            conn = engine.connect()
            cols = []
            try:
                res = conn.execute(text("PRAGMA table_info(ab_user)"))
                cols = [r[1] for r in res.fetchall()]
            except Exception:
                try:
                    res = conn.execute(text("PRAGMA table_info(auth_user)"))
                    cols = [r[1] for r in res.fetchall()]
                except Exception:
                    cols = []
            if 'credits' not in cols:
                try:
                    conn.execute(text("ALTER TABLE ab_user ADD COLUMN credits INTEGER DEFAULT 0"))
                except Exception:
                    try:
                        conn.execute(text("ALTER TABLE auth_user ADD COLUMN credits INTEGER DEFAULT 0"))
                    except Exception:
                        pass
            # Ensure routines.deck_order column exists (nullable JSON)
            try:
                res = conn.execute(text("PRAGMA table_info(routines)"))
                routine_cols = [r[1] for r in res.fetchall()]
            except Exception:
                routine_cols = []
            if 'deck_order' not in routine_cols:
                try:
                    # SQLite doesn't enforce JSON type; store as TEXT compatible with JSON
                    conn.execute(text("ALTER TABLE routines ADD COLUMN deck_order JSON"))
                except Exception:
                    try:
                        conn.execute(text("ALTER TABLE routines ADD COLUMN deck_order TEXT"))
                    except Exception:
                        pass
            conn.close()
        except Exception:
            pass
except Exception:
    # if any of this fails, do not prevent app from running
    pass

from . import views
# Register API blueprint
try:
    from .api import bp as api_bp
    app.register_blueprint(api_bp)
except Exception:
    pass
