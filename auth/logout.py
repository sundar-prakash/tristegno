from flask import redirect, url_for, flash
from flask_login import logout_user
from . import auth

@auth.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('index'))
