from flask import Flask, render_template
from extensions import db, login_manager, csrf, limiter
from config import config
import os
import logging

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Setup logging
    log_handlers = [logging.StreamHandler()]
    if config_name != 'production':
        log_handlers.append(logging.FileHandler(app.config['LOG_FILE']))

    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=log_handlers
    )
    
    from flask_login import current_user
    app.jinja_env.globals.update(current_user=current_user)
    
    # Register blueprints
    from auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from steganography import stego_bp
    app.register_blueprint(stego_bp, url_prefix='/stego')
    
    from auth.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @app.route('/')
    def index():
        return render_template("index.html")
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', 
                             error_code=404, 
                             error_message="Page not found"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Server Error: {error}')
        return render_template('error.html', 
                             error_code=500, 
                             error_message="Internal server error"), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return render_template('error.html', 
                             error_code=413, 
                             error_message="File too large. Maximum size is 200MB"), 413
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
