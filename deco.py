from functools import wraps
from flask_login import current_user
from flask import abort


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kw):
        if not current_user.is_admin:
            return abort(403)
        return func(*args, **kw)

    return wrapper