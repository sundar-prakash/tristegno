from flask_login import UserMixin
from extensions import db
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # Remove private_key storage - security risk!
    public_key = db.Column(db.String(500))
    operations = db.relationship('SteganographyOperation', backref='user', lazy=True, cascade='all, delete-orphan')

class SteganographyOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    operation_type = db.Column(db.String(50), nullable=False)  # 'encode' or 'decode'
    original_filename = db.Column(db.String(255), nullable=False)
    processed_filename = db.Column(db.String(255))
    file_type = db.Column(db.String(50), nullable=False)  # 'image', 'audio', 'video'
    message_length = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # Support IPv6
    success = db.Column(db.Boolean, nullable=False, default=False)
