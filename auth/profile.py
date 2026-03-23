from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from . import auth
from extensions import db
import sys
import os

# Add the steganography module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_pwd = request.form['current_password']
        new_pwd = request.form['new_password']
        confirm_pwd = request.form['confirm_password']
        
        if new_pwd != confirm_pwd:
            flash("New passwords don't match.")
            return redirect(url_for('auth.profile'))
        
        if len(new_pwd) < 8:
            flash("New password must be at least 8 characters long.")
            return redirect(url_for('auth.profile'))
        
        if check_password_hash(current_user.password_hash, current_pwd):
            current_user.password_hash = generate_password_hash(new_pwd)
            db.session.commit()
            flash("Password updated successfully.")
        else:
            flash("Incorrect current password.")
            
        return redirect(url_for('auth.profile'))
    
    return render_template('profile.html', user=current_user)

@auth.route('/regenerate-keys', methods=['POST'])
@login_required
def regenerate_keys():
    try:
        from steganography.stego_core import SteganographyCore
        
        # Generate new key pair
        private_key, public_key = SteganographyCore.generate_key_pair()
        
        # Update user's public key
        current_user.public_key = public_key
        db.session.commit()
        
        # Force session to refresh user object
        db.session.expire(current_user)
        db.session.refresh(current_user)
        
        return jsonify({
            'success': True,
            'private_key': private_key,
            'public_key': public_key  # Also return public key for display
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
