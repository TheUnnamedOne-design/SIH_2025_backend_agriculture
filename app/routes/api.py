from flask import Blueprint, jsonify, current_app
from app.services.rag_service import RAGService
from app.services.pdf_service import PDFService

api_bp = Blueprint('api', __name__)

@api_bp.route('/build-index', methods=['POST'])
def build_index():
    """Build or rebuild the FAISS index from PDFs"""
    config = current_app.config
    pdf_service = PDFService(config['ADOBE_CLIENT_ID'], config['ADOBE_CLIENT_SECRET'])
    rag_service = RAGService(config)
    
    new_chunks = rag_service.build_index(config['PDF_FOLDER'], pdf_service)
    
    return jsonify({
        'message': f'Index built successfully. Added {new_chunks} new chunks.',
        'total_chunks': len(rag_service.chunks)
    })

@api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})
