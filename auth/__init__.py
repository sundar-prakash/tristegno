from flask import Blueprint

auth = Blueprint('auth', __name__)

from . import login, register, logout, profile

