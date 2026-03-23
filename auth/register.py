from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user
from werkzeug.security import generate_password_hash
from . import auth
from .models import User
from extensions import db

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')
        
        if password != confirm_password:
            flash("Passwords don't match.")
            return redirect(url_for('auth.register'))
        
        if len(password) < 8:
            flash("Password must be at least 8 characters long.")
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for('auth.register'))
        
        # Create user without keys - keys will be generated on first encode operation
        hashed_pw = generate_password_hash(password)
        user = User(email=email, password_hash=hashed_pw)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash("Registration successful! You're now logged in.")
        return redirect(url_for('index'))
    
    return render_template('register.html')
