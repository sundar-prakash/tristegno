from flask import Blueprint

stego_bp = Blueprint('stego', __name__, template_folder='templates')

# Import routes AFTER blueprint creation to avoid circular imports
from . import routes
