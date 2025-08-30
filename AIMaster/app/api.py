from flask import Blueprint, request, jsonify
from . import app, appbuilder, db
from flask_login import current_user
from datetime import datetime
from werkzeug.security import check_password_hash

bp = Blueprint('api', __name__, url_prefix='/api')

# Simple token sessions for API usage
SESSIONS = {}

# Helper to get FAB user model - FIXED VERSION
UserModel = appbuilder.sm.user_model

# Public app configuration for mobile/frontend clients
@bp.route('/config', methods=['GET'])
def get_app_config():
    try:
        config = {
            # Keep these in sync with frontend constants
            "node_types": [
                "Iniciar",
                "Capturar Imagen",
                "Conversación",
                "Encontrar una Carta",
                "Carta al Número",
                "Pesar Cartas",
                "Coincidencia Absoluta",
                "Códigos Secretos",
            ],
            "node_info": {
                "Iniciar": "Configura el primer mensaje...",
            },
            "default_node_config": {
                "Iniciar": {
                    "startMessage": "Estoy listo para hacer magia.",
                    "personality": "Sé muy sarcástico.",
                }
            },
            # Bump to bust client cache when server config changes
            "version": "2025-01-01",
        }

        # Basic type validation
        if not isinstance(config.get("node_types"), list) or not all(isinstance(x, str) for x in config["node_types"]):
            raise ValueError("node_types must be a list of strings")
        if not isinstance(config.get("node_info"), dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in config["node_info"].items()):
            raise ValueError("node_info must be a dict of strings")
        if not isinstance(config.get("default_node_config"), dict):
            raise ValueError("default_node_config must be a dict")
        if not isinstance(config.get("version"), str):
            raise ValueError("version must be a string")

        return jsonify(config), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Registration: create a FAB user using security manager
@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400
    # check existing
    user = db.session.query(UserModel).filter_by(email=email).first()
    if user:
        return jsonify({'error': 'email already registered'}), 400
    try:
        # create user with default role 'User'
        role = appbuilder.sm.find_role('User') or appbuilder.sm.find_role('Public')
        appbuilder.sm.add_user(
            username=email,
            first_name=email,
            last_name='',
            email=email,
            role=role,
            password=password
        )
        user = db.session.query(UserModel).filter_by(email=email).first()
        return jsonify({'id': user.id, 'email': user.email}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Login: validate credentials using security manager
@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'email and password required'}), 400
    user = db.session.query(UserModel).filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'invalid credentials'}), 401
    
    # Use FAB's auth_user_db method which handles password verification internally
    if not appbuilder.sm.auth_user_db(email, password):
        return jsonify({'error': 'invalid credentials'}), 401
    
    # create token
    token = f"token-{user.id}-{int(datetime.utcnow().timestamp())}"
    SESSIONS[token] = user.id
    payload = {'id': user.id, 'email': user.email, 'token': token}
    return jsonify(payload), 200

# Require user decorator that checks FAB login or token
from functools import wraps

def require_user(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # If logged via Flask-Login
        if current_user and getattr(current_user, 'is_authenticated', False):
            request.current_user = current_user
            return func(*args, **kwargs)
        # Token auth
        token = request.headers.get('Authorization') or request.args.get('token')
        if token and token in SESSIONS:
            user_id = SESSIONS[token]
            user = db.session.query(UserModel).get(user_id)
            if user:
                request.current_user = user
                return func(*args, **kwargs)
        return jsonify({'error': 'authentication required'}), 401
    return wrapper

@bp.route('/user', methods=['GET'])
@require_user
def get_user():
    u = request.current_user
    return jsonify({'id': u.id, 'email': u.email, 'credits': getattr(u, 'credits', 0)})

# Deck endpoints
from .models import Deck, Routine

@bp.route('/decks', methods=['GET'])
@require_user
def list_decks():
    decks = db.session.query(Deck).filter_by(owner_id=request.current_user.id).all()
    return jsonify([d.to_dict() for d in decks])

@bp.route('/decks', methods=['POST'])
@require_user
def create_deck():
    data = request.get_json() or {}
    name = data.get('name') or data.get('stack')
    if not name:
        return jsonify({'error': 'name required'}), 400
    nodes = data.get('nodes') or data.get('order') or []
    if not isinstance(nodes, list):
        return jsonify({'error': 'nodes must be a list'}), 400
    deck = Deck(name=name, description=data.get('description'), owner_id=request.current_user.id, nodes=nodes)
    db.session.add(deck)
    db.session.commit()
    resp = deck.to_dict()
    if 'order' in data:
        resp['order'] = resp.get('nodes', [])
    return jsonify(resp), 201

@bp.route('/decks/<int:deck_id>', methods=['GET'])
@require_user
def get_deck(deck_id):
    deck = db.session.query(Deck).filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({'error': 'not found'}), 404
    return jsonify(deck.to_dict())

@bp.route('/decks/<int:deck_id>', methods=['PUT'])
@require_user
def update_deck(deck_id):
    deck = db.session.query(Deck).filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json() or {}
    deck.name = data.get('name', deck.name)
    deck.description = data.get('description', deck.description)
    if 'nodes' in data:
        nodes = data.get('nodes')
        if not isinstance(nodes, list):
            return jsonify({'error': 'nodes must be a list'}), 400
        deck.nodes = nodes
    db.session.commit()
    return jsonify(deck.to_dict())

@bp.route('/decks/<int:deck_id>', methods=['DELETE'])
@require_user
def delete_deck(deck_id):
    deck = db.session.query(Deck).filter_by(id=deck_id, owner_id=request.current_user.id).first()
    if not deck:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(deck)
    db.session.commit()
    return jsonify({'success': True})

# Routine endpoints
@bp.route('/routines', methods=['GET'])
@require_user
def list_routines():
    routines = db.session.query(Routine).filter_by(owner_id=request.current_user.id).all()
    return jsonify([r.to_dict() for r in routines])

@bp.route('/routines', methods=['POST'])
@require_user
def create_routine():
    data = request.get_json() or {}
    name = data.get('name')
    stack = data.get('stack') or data.get('deck_name')
    deck_id = data.get('deck_id')
    nodes = data.get('nodes') or []
    deck_order = data.get('deck_order') if 'deck_order' in data else None
    if not name:
        return jsonify({'error': 'name required'}), 400
    if not isinstance(nodes, list):
        return jsonify({'error': 'nodes must be a list'}), 400
    if 'deck_order' in data and not isinstance(deck_order, list):
        return jsonify({'error': 'deck_order must be a list'}), 400
    # if deck provided, ensure ownership
    if deck_id:
        deck = db.session.query(Deck).filter_by(id=deck_id, owner_id=request.current_user.id).first()
        if not deck:
            return jsonify({'error': 'deck not found or unauthorized'}), 404
    else:
        deck = None
        if stack:
            deck = db.session.query(Deck).filter_by(name=stack, owner_id=request.current_user.id).first()
    routine = Routine(
        name=name,
        stack=stack,
        deck_id=deck.id if deck else None,
        nodes=nodes,
        deck_order=deck_order if 'deck_order' in data else None,
        owner_id=request.current_user.id,
    )
    db.session.add(routine)
    db.session.commit()
    resp = routine.to_dict()
    return jsonify(resp), 201

@bp.route('/routines/<int:routine_id>', methods=['GET'])
@require_user
def get_routine(routine_id):
    r = db.session.query(Routine).filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({'error': 'not found'}), 404
    return jsonify(r.to_dict())

@bp.route('/routines/<int:routine_id>', methods=['PUT'])
@require_user
def update_routine(routine_id):
    r = db.session.query(Routine).filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json() or {}
    r.name = data.get('name', r.name)
    r.stack = data.get('stack', r.stack)
    if 'nodes' in data:
        nodes = data.get('nodes')
        if not isinstance(nodes, list):
            return jsonify({'error': 'nodes must be a list'}), 400
        r.nodes = nodes
    if 'deck_order' in data:
        deck_order = data.get('deck_order')
        if deck_order is not None and not isinstance(deck_order, list):
            return jsonify({'error': 'deck_order must be a list'}), 400
        r.deck_order = deck_order
    if 'deck_id' in data:
        deck_id = data.get('deck_id')
        if deck_id:
            deck = db.session.query(Deck).filter_by(id=deck_id, owner_id=request.current_user.id).first()
            if not deck:
                return jsonify({'error': 'deck not found or unauthorized'}), 404
        r.deck_id = deck_id
    db.session.commit()
    return jsonify(r.to_dict())

@bp.route('/routines/<int:routine_id>', methods=['DELETE'])
@require_user
def delete_routine(routine_id):
    r = db.session.query(Routine).filter_by(id=routine_id, owner_id=request.current_user.id).first()
    if not r:
        return jsonify({'error': 'not found'}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({'success': True})

# Credits endpoints
@bp.route('/user/credits', methods=['GET'])
@require_user
def get_credits():
    u = request.current_user
    return jsonify({'credits': getattr(u, 'credits', 0)})

@bp.route('/user/credits', methods=['POST'])
@require_user
def add_credits():
    data = request.get_json() or {}
    amount = int(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'amount must be positive'}), 400
    u = request.current_user
    current = getattr(u, 'credits', 0)
    try:
        setattr(u, 'credits', current + amount)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    return jsonify({'credits': getattr(u, 'credits', 0)})

# Logout
@bp.route('/logout', methods=['POST'])
@require_user
def logout():
    token = request.headers.get('Authorization') or request.args.get('token')
    SESSIONS.pop(token, None)
    return jsonify({'success': True})
