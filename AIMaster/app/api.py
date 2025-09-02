from flask import Blueprint, request, jsonify
from . import app, appbuilder, db
from flask_login import current_user
from datetime import datetime
from werkzeug.security import check_password_hash
from sqlalchemy import inspect as sqla_inspect
from .models import Deck, Routine
from .defaults import INITIAL_ROUTINES

bp = Blueprint('api', __name__, url_prefix='/api')

# Simple token sessions for API usage
SESSIONS = {}

# Helper to get FAB user model - FIXED VERSION
UserModel = appbuilder.sm.user_model


def _table_has_column(table_name: str, column_name: str) -> bool:
    try:
        inspector = sqla_inspect(db.engine)
        cols = inspector.get_columns(table_name)
        names = {c.get('name') for c in cols}
        return column_name in names
    except Exception:
        return False

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
        # Seed initial routines for the new user
        try:
            for r in INITIAL_ROUTINES:
                # Normalize payload for Routine model; ignore provided 'id'
                name = r.get('name')
                stack = r.get('stack')
                nodes = r.get('nodes') or []
                routine = Routine(
                    name=name,
                    stack=stack,
                    deck_id=None,
                    nodes=nodes,
                    owner_id=user.id,
                )
                db.session.add(routine)
            db.session.commit()
        except Exception:
            db.session.rollback()
            # Do not fail registration if seeding fails; continue
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
from .models import Deck, Routine, Actuar

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
    kwargs = dict(
        name=name,
        stack=stack,
        deck_id=deck.id if deck else None,
        nodes=nodes,
        owner_id=request.current_user.id,
    )
    if 'deck_order' in data and _table_has_column('routines', 'deck_order'):
        kwargs['deck_order'] = deck_order
    routine = Routine(**kwargs)
    db.session.add(routine)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'failed to create routine'}), 500
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
    if 'deck_order' in data and _table_has_column('routines', 'deck_order'):
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

# --- Actuar endpoints ---
import os
import html as _html

def _derive_sanitized_username(user) -> str:
    """Derive username from user's email local-part; fallback to user.id or 'public'.
    Sanitize to lowercase [a-z0-9_-] only. If empty after sanitization, use 'public'."""
    base = None
    try:
        email = getattr(user, 'email', None)
        if isinstance(email, str) and '@' in email:
            base = email.split('@', 1)[0]
    except Exception:
        base = None
    if not base:
        uid = getattr(user, 'id', None)
        base = str(uid) if uid is not None else 'public'
    sanitized = ''.join(c for c in (base or '').lower() if (c.isalnum() or c in '-_'))
    return sanitized or 'public'

def _write_actuar_static(username: str, text: str) -> dict:
    try:
        # Ensure static/actuar dir exists
        base_dir = os.path.join(app.root_path, 'static', 'actuar')
        os.makedirs(base_dir, exist_ok=True)
        # Ensure provided username is sanitized to [a-z0-9_-]
        username = ''.join(c for c in (username or '').lower() if (c.isalnum() or c in '-_')) or 'public'
        # Escape text to avoid XSS in the static file
        esc_text = _html.escape(text or "")
        html_doc = (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>actuar — { _html.escape(username or '') }</title>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:2rem;max-width:60ch;line-height:1.5}pre{white-space:pre-wrap;word-wrap:break-word;background:#f6f8fa;padding:1rem;border-radius:8px}</style>"
            "</head><body>"
            f"<h1>actuar: { _html.escape(username or '') }</h1>"
            f"<pre>{esc_text}</pre>"
            "</body></html>"
        )
        # Write sanitized filename only
        out_path = os.path.join(base_dir, f"{username}.html")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html_doc)
        # Return public URL
        base_url = '/static/actuar'
        return {
            'url': f"{base_url}/{username}.html",
        }
    except Exception as e:
        return {'error': str(e)}

@bp.route('/actuar', methods=['POST'])
@require_user
def post_actuar():
    data = request.get_json(silent=True) or {}
    text = data.get('text')
    if text is None:
        # allow form-encoded fallback
        text = request.form.get('text')
    if text is None:
        return jsonify({'error': 'text required'}), 400
    u = request.current_user
    # Upsert the user's actuar row
    row = db.session.query(Actuar).filter_by(user_id=u.id).first()
    if not row:
        row = Actuar(user_id=u.id, text=str(text))
        db.session.add(row)
    else:
        row.text = str(text)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'failed to save'}), 500
    # Derive username from email local-part; fallback to id/public, sanitized [a-z0-9_-]
    san_user = _derive_sanitized_username(u)
    urls = _write_actuar_static(san_user, row.text)
    resp = {
        'success': True,
        'text': row.text,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        'static': urls,
    }
    return jsonify(resp), 200

@bp.route('/actuar/<path:username>', methods=['GET'])
def get_actuar_public(username):
    # Public endpoint: return latest actuar text for given username
    # Accepts: full email, stored username, or email local-part (pre-@)
    if not username:
        return jsonify({'error': 'username required'}), 400

    q = (username or '').strip()
    if not q:
        return jsonify({'error': 'username required'}), 400

    from sqlalchemy import func

    user = None
    try:
        # 1) Exact match on email (case-insensitive)
        user = (
            db.session.query(UserModel)
            .filter(func.lower(UserModel.email) == q.lower())
            .first()
        )
    except Exception:
        user = None

    if not user:
        try:
            # 2) Exact match on stored username (case-insensitive)
            user = (
                db.session.query(UserModel)
                .filter(func.lower(UserModel.username) == q.lower())
                .first()
            )
        except Exception:
            user = None

    if not user and '@' not in q:
        try:
            # 3) Match by email local-part: emails that start with '<q>@'
            user = (
                db.session.query(UserModel)
                .filter(func.lower(UserModel.email).like(f"{q.lower()}@%"))
                .first()
            )
        except Exception:
            user = None

    if not user:
        return jsonify({'error': 'user not found'}), 404

    row = db.session.query(Actuar).filter_by(user_id=user.id).first()
    if not row:
        return jsonify({'username': username, 'text': None, 'updated_at': None}), 200
    # Echo the identifier the client requested for clarity
    return jsonify(row.to_dict(username=username)), 200

# --- Actuar2 endpoints ---
# Two-phase flow:
# 1) POST /api/actuar2/init { values: ["a", "b", ...] }
#    Stores the list for the current user in-memory for this server process.
# 2) POST /api/actuar2 { value: "a", text: "..." }
#    Validates that value is one of the initialized entries and writes a static HTML
#    using the filename pattern: "<sanitized_user>_<sanitized_value>.html" in
#    the same static/actuar directory used by /actuar.

# In-memory store of initialized values per user_id
ACTUAR2_VALUES = {}

def _sanitize_token(s: str) -> str:
    return ''.join(c for c in (s or '').lower() if (c.isalnum() or c in '-_'))

@bp.route('/actuar2/init', methods=['POST'])
@require_user
def actuar2_init():
    data = request.get_json(silent=True) or {}
    values = data.get('values') or data.get('list') or data.get('strings')
    if not isinstance(values, list) or not values:
        return jsonify({'error': 'values must be a non-empty list of strings'}), 400
    cleaned = []
    for v in values:
        if not isinstance(v, str):
            return jsonify({'error': 'all values must be strings'}), 400
        sv = _sanitize_token(v)
        if not sv:
            return jsonify({'error': f'invalid value: {v}'}), 400
        cleaned.append(sv)
    ACTUAR2_VALUES[request.current_user.id] = set(cleaned)
    return jsonify({'success': True, 'values': sorted(ACTUAR2_VALUES[request.current_user.id])}), 200

@bp.route('/actuar2', methods=['POST'])
@require_user
def actuar2_post():
    data = request.get_json(silent=True) or {}
    # Accept several keys for flexibility
    value = data.get('value') or data.get('string') or data.get('item') or data.get('key')
    text = data.get('text')
    if text is None:
        text = request.form.get('text')
    if not isinstance(value, str) or text is None:
        return jsonify({'error': 'value and text are required'}), 400
    sv = _sanitize_token(value)
    if not sv:
        return jsonify({'error': 'value must include letters, digits, dash or underscore'}), 400
    allowed = ACTUAR2_VALUES.get(request.current_user.id)
    if not allowed or sv not in allowed:
        return jsonify({'error': 'value not initialized for user. Call /api/actuar2/init first.'}), 400

    # Build combined filename user_string
    san_user = _derive_sanitized_username(request.current_user)
    combined = f"{san_user}_{sv}"
    urls = _write_actuar_static(combined, str(text))
    if 'error' in urls:
        return jsonify({'error': urls['error']}), 500
    return jsonify({'success': True, 'value': sv, 'static': urls}), 200
