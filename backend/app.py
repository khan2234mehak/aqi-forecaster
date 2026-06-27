"""
AQI Forecaster - Flask Application
===================================
Entry point: python app.py
"""
import os
import sys
import logging
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

def create_app():
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / "frontend" / "templates"),
        static_folder=str(Path(__file__).parent.parent / "frontend" / "static"),
    )

    # Config
    app.config["DATABASE_URL"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/aqi_forecaster"
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "aqi-forecaster-dev-key-change-in-prod")
    app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    CORS(app, origins=["http://localhost:3000", "http://localhost:5005", "*"])

    # Register blueprints
    from backend.routes.api import api
    app.register_blueprint(api)

    # Frontend routes
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "AQI Forecaster API"}

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5005))
    print(f"""
╔══════════════════════════════════════╗
║   🌫️  AQI Forecaster API Started    ║
║   http://localhost:{port}              ║
║   Docs: /api/cities                  ║
╚══════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
