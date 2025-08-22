from flask import render_template
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView, ModelRestApi

from . import appbuilder, db

"""
    Create your Model based REST API::

    class MyModelApi(ModelRestApi):
        datamodel = SQLAInterface(MyModel)

    appbuilder.add_api(MyModelApi)


    Create your Views::


    class MyModelView(ModelView):
        datamodel = SQLAInterface(MyModel)


    Next, register your Views::


    appbuilder.add_view(
        MyModelView,
        "My View",
        icon="fa-folder-open-o",
        category="My Category",
        category_icon='fa-envelope'
    )
"""

"""
    Application wide 404 error handler
"""


@appbuilder.app.errorhandler(404)
def page_not_found(e):
    return (
        render_template(
            "404.html", base_template=appbuilder.base_template, appbuilder=appbuilder
        ),
        404,
    )


db.create_all()

# Register Deck and Routine ModelViews in FAB admin UI
from .models import Deck, Routine

class DeckModelView(ModelView):
    datamodel = SQLAInterface(Deck)
    list_columns = ['id', 'name', 'owner_id', 'created_at']

class RoutineModelView(ModelView):
    datamodel = SQLAInterface(Routine)
    list_columns = ['id', 'name', 'owner_id', 'stack', 'deck_id', 'created_at']

try:
    appbuilder.add_view(
        DeckModelView,
        "Decks",
        icon="fa-book",
        category="Manage",
        category_icon='fa-cog'
    )
    appbuilder.add_view(
        RoutineModelView,
        "Routines",
        icon="fa-tasks",
        category="Manage",
        category_icon='fa-cog'
    )
except Exception:
    pass

# Simple API endpoint to return current logged-in user's credits.
from flask import jsonify
from flask_appbuilder.security.decorators import has_access
from flask_appbuilder import expose


@appbuilder.app.route('/api/user/credits', methods=['GET'])
@has_access
def get_user_credits():
    # current_user is available from FAB
    try:
        from flask_appbuilder.security.sqla.models import User
        from flask_login import current_user
        credits = getattr(current_user, 'credits', 0)
        return jsonify({"credits": credits}), 200
    except Exception:
        return jsonify({"credits": 0}), 200
