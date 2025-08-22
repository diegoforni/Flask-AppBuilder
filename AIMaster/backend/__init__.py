from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
ma = Marshmallow()

def create_app(config_object=None):
    from flask import Flask
    app = Flask(__name__)
    if config_object:
        app.config.from_object(config_object)
    else:
        app.config.from_mapping(
            SQLALCHEMY_DATABASE_URI='sqlite:///backend.db',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY='dev-secret',
        )
    db.init_app(app)
    ma.init_app(app)

    with app.app_context():
        from . import models  # ensure models are registered
        db.create_all()

    return app
