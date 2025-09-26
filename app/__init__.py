from flask import Flask
from app.extensions import init_extensions
from app.config import Config
from flask_cors import CORS

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)
    
    # Add CORS
    CORS(app, origins="*")
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    from app.routes.speech import speech_bp
    from app.routes.image import image_bp  # NEW
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(speech_bp, url_prefix='/speech')
    app.register_blueprint(image_bp, url_prefix='/image')  # NEW
    
    # Initialize RAG service
    print("Initializing RAG service...")
    from app.services.rag_service import RAGService
    app.rag_service = RAGService(app.config)
    print("RAG service initialization complete!")
    
    # Initialize Image Classification service  # NEW
    print("Initializing Image Classification service...")
    from app.services.image_classification_service import ImageClassificationService
    app.image_service = ImageClassificationService(app.config)
    print("Image Classification service initialization complete!")
    
    return app
