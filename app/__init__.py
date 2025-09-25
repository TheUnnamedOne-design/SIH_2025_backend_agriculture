from flask import Flask
from app.extensions import init_extensions
from app.config import Config

def create_app(config_class=Config):
    # Explicitly set template folder
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Initialize RAG service at app startup
    print("Initializing RAG service at startup...")
    from app.services.rag_service import RAGService
    app.rag_service = RAGService(app.config)
    print("RAG service initialization complete!")
    
    return app
