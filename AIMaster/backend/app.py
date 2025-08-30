from flask import Flask, request, jsonify, abort
from . import create_app, db
from .models import User, Deck, Routine
from .schemas import user_schema, users_schema, deck_schema, decks_schema, routine_schema, routines_schema
from .config import DefaultConfig
from datetime import datetime

app = create_app(DefaultConfig)

# Minimal in-memory session for demonstration only
# Frontend can POST /login and receive the user object; replace with tokens later
SESSIONS = {}

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 400
    user = User(email=email, credits=data.get('credits', 5))
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user_schema.jsonify(user), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401
    # simple session token
    token = f"token-{user.id}"
    SESSIONS[token] = user.id
    payload = user.to_dict()
    payload["token"] = token
    return jsonify(payload), 200

def require_user(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization') or request.args.get('token')
        if not token or token not in SESSIONS:
            return jsonify({"error": "authentication required"}), 401
        user_id = SESSIONS[token]
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "invalid session"}), 401
        request.current_user = user
        return func(*args, **kwargs)
    return wrapper

@app.route('/api/user', methods=['GET'])
@require_user
def get_user():
    return user_schema.jsonify(request.current_user)

# Deck endpoints
@app.route('/api/decks', methods=['GET'])
@require_user
def list_decks():
    decks = Deck.query.filter_by(owner_id=request.current_user.id).all()
    return decks_schema.jsonify(decks)

@app.route('/api/decks', methods=['POST'])
@require_user
def create_deck():
    data = request.get_json() or {}
    # frontend may send { name, order } for card orders or { name, nodes } for node decks
    name = data.get('name') or data.get('stack')
    if not name:
        return jsonify({"error": "name required"}), 400
    # normalize: prefer 'order' (card order) otherwise 'nodes'
    nodes = data.get('nodes')
    order = data.get('order')
    payload_nodes = None
    if order is not None:
        # store card orders under nodes for compatibility but keep original under 'order' in response
        if not isinstance(order, list):
            return jsonify({"error": "order must be a list"}), 400
        payload_nodes = order
    else:
        if nodes is None:
            payload_nodes = []
        else:
            if not isinstance(nodes, list):
                return jsonify({"error": "nodes must be a list"}), 400
            # simple validation of node shape
            for n in nodes:
                if not isinstance(n, dict) or 'id' not in n or 'type' not in n or 'config' not in n:
                    return jsonify({"error": "each node must be an object with id, type, config"}), 400
            payload_nodes = nodes
    deck = Deck(name=name, description=data.get('description'), owner_id=request.current_user.id, nodes=payload_nodes)
    db.session.add(deck)
    db.session.commit()
    # prepare response matching frontend: include 'order' key if original request had it
    resp = deck_schema.dump(deck)
    if order is not None:
        resp['order'] = deck.nodes or []
    return jsonify(resp), 201

@app.route('/api/decks/<int:deck_id>', methods=['GET'])
@require_user
def get_deck(deck_id):
    deck = Deck.query.filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({"error": "not found"}), 404
    return deck_schema.jsonify(deck)

@app.route('/api/decks/<int:deck_id>', methods=['PUT'])
@require_user
def update_deck(deck_id):
    deck = Deck.query.filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    deck.name = data.get('name', deck.name)
    deck.description = data.get('description', deck.description)
    db.session.commit()
    return deck_schema.jsonify(deck)

@app.route('/api/decks/<int:deck_id>', methods=['DELETE'])
@require_user
def delete_deck(deck_id):
    deck = Deck.query.filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({"error": "not found"}), 404
    db.session.delete(deck)
    db.session.commit()
    return jsonify({"success": True}), 200

# Routine endpoints
@app.route('/api/routines', methods=['GET'])
@require_user
def list_routines():
    routines = Routine.query.filter_by(owner_id=request.current_user.id).all()
    return routines_schema.jsonify(routines)

@app.route('/api/routines', methods=['POST'])
@require_user
def create_routine():
    data = request.get_json() or {}
    name = data.get('name')
    stack = data.get('stack') or data.get('deck_name')
    deck_id = data.get('deck_id')
    nodes = data.get('nodes')
    if not name:
        return jsonify({"error": "name required"}), 400
    if nodes is None:
        nodes = []
    if not isinstance(nodes, list):
        return jsonify({"error": "nodes must be a list"}), 400
    # validate node shape
    for n in nodes:
        if not isinstance(n, dict) or 'id' not in n or 'type' not in n or 'config' not in n:
            return jsonify({"error": "each node must be an object with id, type, config"}), 400
    # if deck_id provided, ensure it belongs to user
    deck = None
    if deck_id:
        deck = Deck.query.filter_by(id=deck_id, owner_id=request.current_user.id).first()
        if not deck:
            return jsonify({"error": "deck not found or unauthorized"}), 404
    else:
        # try to find deck by stack/name owned by user
        if stack:
            deck = Deck.query.filter_by(name=stack, owner_id=request.current_user.id).first()
    routine = Routine(name=name, stack=stack, deck_id=deck.id if deck else None, nodes=nodes, owner_id=request.current_user.id)
    db.session.add(routine)
    db.session.commit()
    # return shape matching frontend (string id)
    resp = routine_schema.dump(routine)
    resp['id'] = str(resp.get('id'))
    return jsonify(resp), 201

@app.route('/api/routines/<int:routine_id>', methods=['GET'])
@require_user
def get_routine(routine_id):
    r = Routine.query.filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({"error": "not found"}), 404
    return routine_schema.jsonify(r)

@app.route('/api/routines/<int:routine_id>', methods=['PUT'])
@require_user
def update_routine(routine_id):
    r = Routine.query.filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    r.name = data.get('name', r.name)
    r.stack = data.get('stack', r.stack)
    # allow updating nodes entirely from frontend
    if 'nodes' in data:
        nodes = data.get('nodes')
        if not isinstance(nodes, list):
            return jsonify({"error": "nodes must be a list"}), 400
        for n in nodes:
            if not isinstance(n, dict) or 'id' not in n or 'type' not in n or 'config' not in n:
                return jsonify({"error": "each node must be an object with id, type, config"}), 400
        r.nodes = nodes
    # allow reassigning deck by id
    if 'deck_id' in data:
        deck_id = data.get('deck_id')
        if deck_id:
            deck = Deck.query.filter_by(id=deck_id, owner_id=request.current_user.id).first()
            if not deck:
                return jsonify({"error": "deck not found or unauthorized"}), 404
        r.deck_id = deck_id
    db.session.commit()
    resp = routine_schema.dump(r)
    resp['id'] = str(resp.get('id'))
    return jsonify(resp)

@app.route('/api/routines/<int:routine_id>', methods=['DELETE'])
@require_user
def delete_routine(routine_id):
    r = Routine.query.filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({"error": "not found"}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({"success": True}), 200

# Actuar endpoint: consumes 1 credit per press and returns simulated result

# Simple endpoint to add credits (for testing)
@app.route('/api/user/credits', methods=['GET'])
@require_user
def get_credits():
    user = request.current_user
    return jsonify({"credits": user.credits}), 200

@app.route('/api/user/credits', methods=['POST'])
@require_user
def add_credits():
    data = request.get_json() or {}
    amount = int(data.get('amount', 0))
    if amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400
    user = request.current_user
    user.credits += amount
    db.session.commit()
    return jsonify({"credits": user.credits}), 200

# Logout endpoint
@app.route('/api/logout', methods=['POST'])
@require_user
def logout():
    token = request.headers.get('Authorization') or request.args.get('token')
    SESSIONS.pop(token, None)
    return jsonify({"success": True}), 200

# Run locally helper
if __name__ == '__main__':
    app.run(debug=True, port=5000)
