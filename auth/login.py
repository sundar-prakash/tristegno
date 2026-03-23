from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user
from werkzeug.security import check_password_hash
from . import auth
from .models import User
from extensions import db
from flask_login import login_user
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.")
    return render_template('login.html')
