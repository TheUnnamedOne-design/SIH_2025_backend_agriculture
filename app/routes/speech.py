import os
import tempfile
from flask import Blueprint, request, jsonify, current_app, send_file
from app.services.speech_service import SpeechService
from app.services.location_service import LocationService
from app.services.soil_service import SoilService
from app.services.api_service import APIService

# Create the blueprint
speech_bp = Blueprint('speech', __name__)

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'ogg', 'webm'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        
        # Get form data
        district_name = request.form.get('district')
        state = request.form.get('state')
        choice = int(request.form.get('choice', 1))
        current_crop = request.form.get('current_crop', '')
        preferred_language = request.form.get('preferred_language', 'English')  # New field
        
        print(f"Voice Query Request:")
        print(f"- District: {district_name}, State: {state}")
        print(f"- Choice: {choice}, Crop: {current_crop}")
        print(f"- Preferred Language: {preferred_language}")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_input = temp_file.name
            file.save(temp_input)
            
        # Initialize speech service
        speech_service = SpeechService(current_app.config)
        
        # Process audio file
        processed_file = speech_service.process_audio_file(temp_input)
        
        # Transcribe audio with preferred language
        transcribed_text, detected_language = speech_service.transcribe_audio(
            processed_file, preferred_language
        )
        
        if not transcribed_text.strip():
            return jsonify({'error': 'Could not transcribe audio. Please try again.'}), 400
        
        print(f"Transcribed Text: {transcribed_text}")
        print(f"Detected Language: {detected_language}")
        
        # Translate to English for processing
        english_query = speech_service.translate_to_english(transcribed_text, detected_language)
        print(f"English Query: {english_query}")
        
        # Process with your existing RAG system
        rag_service = current_app.rag_service
        location_service = LocationService()
        
        # Get location data
        latitude, longitude = location_service.get_coordinates(district_name, state)
        if not latitude or not longitude:
            return jsonify({'error': f'Could not find coordinates for {district_name}, {state}'}), 400
        
        elevation = location_service.get_elevation(latitude, longitude)
        print(f"Location: {district_name}, {state} -> {latitude}, {longitude}, {elevation}m")
        
        # Prepare context based on choice
        if choice == 1:
            # Farming advice
            soil_service = SoilService()
            api_service = APIService(current_app.config['OGD_API_KEY'], current_app.config['RESOURCE_ID'])
            context_data = soil_service.get_soil_data(
                district_name, current_app.config['SOIL_DATA_PATH'], 
                latitude, longitude, api_service
            ) + f" elevation of {elevation} mtrs"
        elif choice == 2:
            # Pesticide advice
            context_data = f'''
            from {district_name} of state of {state},
            with an altitude of {elevation},
            the current crop being grown is {current_crop}.
            '''
        else:
            context_data = f"Location: {district_name}, {state}, elevation: {elevation}m"
        
        print(f"Context Data: {context_data[:200]}...")
        
        # Check if RAG index exists
        if rag_service.index is None:
            return jsonify({
                'error': 'No RAG index found. Please build the index first.'
            }), 400
        
        # Get AI answer
        english_answer, retrieved = rag_service.rag_answer(english_query, context_data, choice)
        print(f"English Answer: {english_answer[:100]}...")
        
        if not english_answer.strip():
            return jsonify({'error': 'Could not generate response. Please try again.'}), 500
        
        # Translate answer back to original language
        native_answer = speech_service.translate_from_english(english_answer, detected_language)
        print(f"Native Answer: {native_answer[:100]}...")
        
        # Convert answer to speech
        audio_response_file = speech_service.text_to_speech(native_answer, detected_language)
        
        if not audio_response_file or not os.path.exists(audio_response_file):
            return jsonify({'error': 'Could not generate audio response'}), 500
        
        print(f"Audio response generated: {audio_response_file}")
        
        # Return the audio file directly
        return send_file(
            audio_response_file,
            as_attachment=False,
            mimetype='audio/wav',
            download_name='ai_response.wav'
        )
        
    except Exception as e:
        print(f"Voice Query Error: {e}")
        return jsonify({'error': f'Voice processing failed: {str(e)}'}), 500
        
    finally:
        # Clean up temporary files
        if temp_input and os.path.exists(temp_input):
            try:
                os.unlink(temp_input)
                print(f"Cleaned up temp input: {temp_input}")
            except Exception as e:
                print(f"Failed to cleanup temp input: {e}")
                
        if processed_file and os.path.exists(processed_file):
            try:
                os.unlink(processed_file)
                print(f"Cleaned up processed file: {processed_file}")
            except Exception as e:
                print(f"Failed to cleanup processed file: {e}")


@speech_bp.route('/voice-query-json', methods=['POST'])
def process_voice_query_json():
    """Alternative endpoint that returns JSON with text response and audio URL"""
    temp_input = None
    processed_file = None
    audio_response_file = None
    
    try:
        # Check if audio file is present
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid audio file'}), 400
        
        # Get form data
        district_name = request.form.get('district')
        state = request.form.get('state')
        choice = int(request.form.get('choice', 1))
        current_crop = request.form.get('current_crop', '')
        preferred_language = request.form.get('preferred_language', 'English')
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_input = temp_file.name
            file.save(temp_input)
        
        # Process voice query (same logic as above)
        speech_service = SpeechService(current_app.config)
        processed_file = speech_service.process_audio_file(temp_input)
        transcribed_text, detected_language = speech_service.transcribe_audio(
            processed_file, preferred_language
        )
        
        if not transcribed_text.strip():
            return jsonify({'error': 'Could not transcribe audio'}), 400
        
        english_query = speech_service.translate_to_english(transcribed_text, detected_language)
        
        # Get location and context data
        rag_service = current_app.rag_service
        location_service = LocationService()
        latitude, longitude = location_service.get_coordinates(district_name, state)
        
        if not latitude or not longitude:
            return jsonify({'error': 'Location not found'}), 400
        
        elevation = location_service.get_elevation(latitude, longitude)
        
        if choice == 1:
            soil_service = SoilService()
            api_service = APIService(current_app.config['OGD_API_KEY'], current_app.config['RESOURCE_ID'])
            context_data = soil_service.get_soil_data(
                district_name, current_app.config['SOIL_DATA_PATH'], 
                latitude, longitude, api_service
            ) + f" elevation of {elevation} mtrs"
        else:
            context_data = f"from {district_name} of state {state}, altitude {elevation}m, crop: {current_crop}"
        
        if rag_service.index is None:
            return jsonify({'error': 'RAG index not found'}), 400
        
        english_answer, retrieved = rag_service.rag_answer(english_query, context_data, choice)
        native_answer = speech_service.translate_from_english(english_answer, detected_language)
        
        # Generate audio response
        audio_response_file = speech_service.text_to_speech(native_answer, detected_language)
        
        return jsonify({
            'transcribed_text': transcribed_text,
            'detected_language': detected_language,
            'english_query': english_query,
            'english_answer': english_answer,
            'native_answer': native_answer,
            'audio_file_path': audio_response_file,
            'retrieved_chunks': [
                {'id': cid, 'text': txt[:200], 'score': score}
                for cid, txt, score in retrieved
            ],
            'context': context_data[:500]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        # Cleanup
        if temp_input and os.path.exists(temp_input):
            try:
                os.unlink(temp_input)
            except:
                pass
        if processed_file and os.path.exists(processed_file):
            try:
                os.unlink(processed_file)
            except:
                pass


@speech_bp.route('/test', methods=['GET'])
def test_speech():
    """Simple test endpoint"""
    return jsonify({'message': 'Speech service is running!', 'status': 'ok'})


@speech_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test if services can be initialized
        speech_service = SpeechService(current_app.config)
        return jsonify({
            'status': 'healthy',
            'speech_service': 'initialized',
            'rag_service': 'available' if current_app.rag_service else 'not_available'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
