from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os

image_bp = Blueprint('image', __name__)

@image_bp.route('/classify', methods=['POST'])
def classify_image():
    """Classify uploaded image using ConvNeXt model"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get prediction from image classification service
        result = current_app.image_service.predict_from_file_upload(file)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'predicted_class': result['predicted_class'],
            'confidence': result['confidence'],
            'all_predictions': result.get('all_predictions', {})
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@image_bp.route('/classify-path', methods=['POST'])
def classify_image_path():
    """Classify image from file path"""
    try:
        data = request.get_json()
        if not data or 'image_path' not in data:
            return jsonify({'error': 'No image_path provided'}), 400
        
        image_path = data['image_path']
        if not os.path.exists(image_path):
            return jsonify({'error': f'Image not found: {image_path}'}), 404
        
        # Get prediction
        result = current_app.image_service.predict_image(image_path)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'predicted_class': result['predicted_class'],
            'confidence': result['confidence'],
            'all_predictions': result.get('all_predictions', {})
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@image_bp.route('/model-info', methods=['GET'])
def model_info():
    """Get information about the loaded ConvNeXt model"""
    try:
        service = current_app.image_service
        if service.model is None:
            return jsonify({'error': 'Model not loaded'}), 500
        
        return jsonify({
            'model_loaded': True,
            'device': str(service.device),
            'classes': list(service.idx_to_class.values()) if service.idx_to_class else [],
            'num_classes': len(service.idx_to_class) if service.idx_to_class else 0,
            'checkpoint_path': service.checkpoint_path,
            'model_type': 'ConvNeXt Tiny'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@image_bp.route('/predict', methods=['POST'])
def predict():
    """Alternative endpoint name for image classification"""
    return classify_image()
