from flask_appbuilder import Model
from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

# This module augments the Flask-AppBuilder user model by adding a credits column.
# We'll create a mixin-style model that maps to the same users table used by FAB's
# security user model by importing the user model dynamically at runtime when needed.

# Define a simple mixin class for credits
class CreditsMixin(object):
    credits = Column(Integer, default=0, nullable=False)

# Deck and Routine models inspired by the backend example but adapted to FAB SQLA
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from datetime import datetime

class Deck(Model):
    __tablename__ = 'decks'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey('ab_user.id'), nullable=False)
    # Use generic JSON column where supported; SQLite dialect provides JSON type
    nodes = Column(SQLiteJSON, nullable=True, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'owner_id': self.owner_id,
            'nodes': self.nodes or [],
            'created_at': self.created_at.isoformat()
        }

class Routine(Model):
    __tablename__ = 'routines'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    nodes = Column(SQLiteJSON, nullable=True, default=list)
    # Optional ordering of deck cards (editor's deckOrder)
    deck_order = Column(SQLiteJSON, nullable=True)
    stack = Column(String(255), nullable=True)
    deck_id = Column(Integer, ForeignKey('decks.id'), nullable=True)
    owner_id = Column(Integer, ForeignKey('ab_user.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'stack': self.stack,
            'deck_id': str(self.deck_id) if self.deck_id is not None else None,
            'nodes': self.nodes or [],
            'deck_order': self.deck_order or [],
            'owner_id': self.owner_id,
            'created_at': self.created_at.isoformat(),
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None
        }

# Store the latest "actuar" text per user
class Actuar(Model):
    __tablename__ = 'actuar'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('ab_user.id'), nullable=False, unique=True)
    text = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, username: str = None):
        return {
            'user_id': self.user_id,
            'username': username,
            'text': self.text,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
