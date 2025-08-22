from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

# Association table if many-to-many between Deck and Routine (if needed)
# Here we model: a Routine belongs to a single Deck; a User has many Routines and Decks
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    credits = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    decks = db.relationship('Deck', backref='owner', lazy=True)
    routines = db.relationship('Routine', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "credits": self.credits,
            "created_at": self.created_at.isoformat()
        }

class Deck(db.Model):
    __tablename__ = 'decks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # corresponds to "stack" or deck name in frontend
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # store nodes/order as JSON so LinkedListModule can reconstruct ordering client-side
    nodes = db.Column(db.JSON, nullable=True, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # routines that use this deck
    routines = db.relationship('Routine', backref='deck', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "nodes": self.nodes or [],
            "created_at": self.created_at.isoformat()
        }

class Routine(db.Model):
    __tablename__ = 'routines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)  # frontend uses "name"
    # store nodes array exactly like INITIAL_ROUTINES: [{id, type, config}, ...]
    nodes = db.Column(db.JSON, nullable=True, default=list)
    # the stack field in frontend is a deck name; we'll keep deck_id as FK to Deck
    stack = db.Column(db.String(255), nullable=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_run_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "stack": self.stack,
            "deck_id": self.deck_id,
            "nodes": self.nodes or [],
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None
        }
