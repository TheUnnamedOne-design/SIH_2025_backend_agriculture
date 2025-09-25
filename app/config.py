import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Adobe PDF Services API
    ADOBE_CLIENT_ID = os.environ.get('ADOBE_CLIENT_ID')
    ADOBE_CLIENT_SECRET = os.environ.get('ADOBE_CLIENT_SECRET')
    
    # External API Keys
    TOGETHER_API_KEY = os.environ.get('TOGETHER_API_KEY')
    OGD_API_KEY = os.environ.get('OGD_API_KEY')
    RESOURCE_ID = os.environ.get('RESOURCE_ID')
    
    # File Paths
    PDF_FOLDER = os.environ.get('PDF_FOLDER', 'data/pdfs')
    SOIL_DATA_PATH = os.environ.get('SOIL_DATA_PATH', 'data/soil_data')
    INDEX_PATH = os.environ.get('INDEX_PATH', 'data/embeddings/index.faiss')
    META_PATH = os.environ.get('META_PATH', 'data/embeddings/meta.pkl')
    
    # AI Model Configuration - Read from .env
    EMB_MODEL = os.environ.get('EMB_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    TOGETHER_MODEL = os.environ.get('TOGETHER_MODEL', 'meta-llama/Llama-3.3-70B-Instruct-Turbo-Free')
    MAX_CHARS_PER_CHUNK = int(os.environ.get('MAX_CHARS_PER_CHUNK', '1200'))
    TOP_K = int(os.environ.get('TOP_K', '4'))


    GOOGLE_PROJECT_ID = os.environ.get('GOOGLE_PROJECT_ID', 'sihserver-473213')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Audio processing
    MAX_AUDIO_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'temp_uploads')