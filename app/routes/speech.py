from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import os
import tempfile
from app.services.speech_service import SpeechService
from app.services.location_service import LocationService
from app.services.soil_service import SoilService
from app.services.api_service import APIService

speech_bp = Blueprint('speech', __name__)

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'flac', 'ogg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@speech_bp.route('/voice-query', methods=['POST'])
def process_voice_query():
    temp_input = None
    processed_file = None
    audio_response_file = None
    
    try:
        # Check if audio file is present
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid audio file format'}), 400
        
        # Get other form data
        district_name = request.form.get('district')
        state = request.form.get('state')
        choice = int(request.form.get('choice', 1))
        current_crop = request.form.get('current_crop', '')
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_input = temp_file.name
            file.save(temp_input)
            
        # Initialize speech service
        speech_service = SpeechService(current_app.config)
        
        # Process audio file
        processed_file = speech_service.process_audio_file(temp_input)
        
        # Transcribe audio
        transcribed_text, detected_language = speech_service.transcribe_audio(processed_file)
        
        # Translate to English for processing
        english_query = speech_service.translate_to_english(transcribed_text, detected_language)
        
        # Process with your existing RAG system
        rag_service = current_app.rag_service
        location_service = LocationService()
        
        # Get location data
        latitude, longitude = location_service.get_coordinates(district_name, state)
        if not latitude or not longitude:
            return jsonify({'error': 'Could not find location coordinates'}), 400
        
        elevation = location_service.get_elevation(latitude, longitude)

        print(detected_language)
        
        # Prepare context
        if choice == 1:
            soil_service = SoilService()
            api_service = APIService(current_app.config['OGD_API_KEY'], current_app.config['RESOURCE_ID'])
            context_data = soil_service.get_soil_data(
                district_name, current_app.config['SOIL_DATA_PATH'], 
                latitude, longitude, api_service
            ) + f" elevation of {elevation} mtrs"
        else:
            context_data = f'''
            from {district_name} of state of {state},
            with an altitude of {elevation},
            the current crop being grown is {current_crop}.
            '''
        
        # Get AI answer
        english_answer, retrieved = rag_service.rag_answer(english_query, context_data, choice)
        
        # Translate answer back to original language
        native_answer = speech_service.translate_from_english(english_answer, detected_language)
        
        # Convert answer to speech
        audio_response_file = speech_service.text_to_speech(native_answer, detected_language)
        
        # Return the audio file directly
        return send_file(
            audio_response_file,
            as_attachment=False,
            mimetype='audio/mpeg',
            download_name='ai_response.mp3'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        # Clean up temporary files
        if temp_input and os.path.exists(temp_input):
            os.unlink(temp_input)
        if processed_file and os.path.exists(processed_file):
            os.unlink(processed_file)
        # Note: audio_response_file will be cleaned up after sending

@speech_bp.route('/voice-query-json', methods=['POST'])
def process_voice_query_json():
    """Alternative endpoint that returns JSON with metadata (without audio file)"""
    temp_input = None
    processed_file = None
    
    try:
        # Same processing as above...
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid audio file format'}), 400
        
        district_name = request.form.get('district')
        state = request.form.get('state')
        choice = int(request.form.get('choice', 1))
        current_crop = request.form.get('current_crop', '')
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_input = temp_file.name
            file.save(temp_input)
            
        speech_service = SpeechService(current_app.config)
        processed_file = speech_service.process_audio_file(temp_input)
        transcribed_text, detected_language = speech_service.transcribe_audio(processed_file)
        english_query = speech_service.translate_to_english(transcribed_text, detected_language)
        
        rag_service = current_app.rag_service
        location_service = LocationService()
        

        latitude, longitude = location_service.get_coordinates(district_name, state)
        if not latitude or not longitude:
            return jsonify({'error': 'Could not find location coordinates'}), 400
        
        elevation = location_service.get_elevation(latitude, longitude)
        
        if choice == 1:
            soil_service = SoilService()
            api_service = APIService(current_app.config['OGD_API_KEY'], current_app.config['RESOURCE_ID'])
            context_data = soil_service.get_soil_data(
                district_name, current_app.config['SOIL_DATA_PATH'], 
                latitude, longitude, api_service
            ) + f" elevation of {elevation} mtrs"
        else:
            context_data = f'''
            from {district_name} of state of {state},
            with an altitude of {elevation},
            the current crop being grown is {current_crop}.
            '''
        
        english_answer, retrieved = rag_service.rag_answer(english_query, context_data, choice)
        native_answer = speech_service.translate_from_english(english_answer, detected_language)

        print(detected_language)
        
        # Return JSON response only (no audio file)
        return jsonify({
            'transcribed_text': transcribed_text,
            'detected_language': detected_language,
            'english_query': english_query,
            'english_answer': english_answer,
            'native_answer': native_answer,
            'retrieved_chunks': [
                {'id': cid, 'text': txt[:200], 'score': score}
                for cid, txt, score in retrieved
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        if temp_input and os.path.exists(temp_input):
            os.unlink(temp_input)
        if processed_file and os.path.exists(processed_file):
            os.unlink(processed_file)

@speech_bp.route('/text-to-speech', methods=['POST'])
def convert_text_to_speech():
    """Convert text to speech and return audio file directly"""
    try:
        data = request.json
        text = data.get('text')
        language_code = data.get('language_code', 'en')
        
        speech_service = SpeechService(current_app.config)
        audio_file = speech_service.text_to_speech(text, language_code)
        
        return send_file(
            audio_file,
            as_attachment=False,
            mimetype='audio/mpeg',
            download_name='speech_output.mp3'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
