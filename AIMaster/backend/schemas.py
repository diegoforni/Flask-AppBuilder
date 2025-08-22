from . import ma
from .models import User, Deck, Routine

class UserSchema(ma.Schema):
    class Meta:
        fields = ("id", "email", "credits", "created_at")

user_schema = UserSchema()
users_schema = UserSchema(many=True)

class DeckSchema(ma.Schema):
    class Meta:
        # expose fields frontend expects; 'order' may be provided by frontend and will be echoed when present
        fields = ("id", "name", "description", "nodes", "created_at")

    # coerce id to string so it matches frontend sample data which uses string ids
    id = ma.Function(lambda obj: str(obj.id))

deck_schema = DeckSchema()
decks_schema = DeckSchema(many=True)

class RoutineSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "stack", "deck_id", "nodes", "created_at", "last_run_at")

    id = ma.Function(lambda obj: str(obj.id))
    deck_id = ma.Function(lambda obj: str(obj.deck_id) if obj.deck_id is not None else None)

routine_schema = RoutineSchema()
routines_schema = RoutineSchema(many=True)
