"""
TradeWise Backend - Flask Application Factory
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()


def create_app(config_name=None):
    app = Flask(__name__)

    # Load configuration
    from app.config import config_by_name
    cfg_name = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_by_name.get(cfg_name, config_by_name["development"]))

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)

    # CORS
    CORS(
        app,
        origins=app.config.get("FRONTEND_URL", "*"),
        supports_credentials=True,
    )

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    return app


def _register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.pro_trader_profile import profile_bp
    from app.routes.trades import trades_bp
    from app.routes.comments import comments_bp
    from app.routes.analytics import analytics_bp
    from app.routes.subscribers import subscribers_bp
    from app.routes.earnings import earnings_bp
    from app.routes.kyc import kyc_bp
    from app.routes.account_settings import account_bp
    from app.routes.notifications import notifications_bp
    from app.routes.exports import exports_bp
    from app.routes.webhooks import webhooks_bp
    from app.routes.learner_profile import learner_profile_bp
    from app.routes.learner_feed import learner_feed_bp
    from app.routes.learner_credits import learner_credits_bp
    from app.routes.learner_subscriptions import learner_subscriptions_bp
    from app.routes.learner_payments import learner_payments_bp
    from app.routes.learner_flags import learner_flags_bp
    from app.routes.learner_ratings import learner_ratings_bp
    from app.routes.learner_notifications import learner_notifications_bp
    from app.routes.learner_comments import learner_comments_bp
    from app.routes.pro_traders_public import pro_traders_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(trades_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(comments_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(analytics_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(subscribers_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(earnings_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(kyc_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(account_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(notifications_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(exports_bp, url_prefix="/api/pro-trader")
    app.register_blueprint(webhooks_bp, url_prefix="/api/webhooks")
    app.register_blueprint(learner_profile_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_feed_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_credits_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_subscriptions_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_payments_bp, url_prefix="/api/payments")
    app.register_blueprint(learner_flags_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_ratings_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_notifications_bp, url_prefix="/api/learner")
    app.register_blueprint(learner_comments_bp, url_prefix="/api/learner")
    app.register_blueprint(pro_traders_bp, url_prefix="/api/pro-traders")


def _register_error_handlers(app):
    from flask import jsonify

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized", "message": str(e)}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden", "message": str(e)}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "message": str(e)}), 404

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "Unprocessable entity", "message": str(e)}), 422

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
