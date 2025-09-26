from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import os
import uuid
from pydub import AudioSegment
from pydub.effects import normalize

calls_bp = Blueprint('calls', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'m4a', 'mp3', 'wav', 'aac', 'ogg', 'flac'}

# In-memory storage (use database in production)
call_history = []

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_directories():
    """Ensure upload directories exist"""
    base_dir = current_app.config.get('UPLOAD_FOLDER', 'call_recordings')
    
    directories = {
        'original': os.path.join(base_dir, 'original'),
        'converted': os.path.join(base_dir, 'converted'),
        'processed': os.path.join(base_dir, 'processed')
    }
    
    for dir_path in directories.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return directories

def process_audio_to_wav(input_path, file_id):
    """Process audio file and convert to WAV"""
    try:
        print(f"🎵 Processing audio file: {input_path}")
        
        # Load audio file
        audio = AudioSegment.from_file(input_path)
        print(f"   Original: {len(audio)/1000:.1f}s, {audio.frame_rate}Hz, {audio.channels} channels")
        
        # Convert to standard format (44.1kHz, mono)
        if audio.frame_rate != 44100:
            audio = audio.set_frame_rate(44100)
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        directories = ensure_upload_directories()
        
        # Basic WAV conversion
        wav_filename = f"{file_id}_converted.wav"
        wav_path = os.path.join(directories['converted'], wav_filename)
        audio.export(wav_path, format="wav")
        print(f"   WAV created: {wav_filename}")
        
        # Enhanced processing
        try:
            normalized_audio = normalize(audio)
            high_passed = normalized_audio.high_pass_filter(100)
            processed_audio = high_passed.low_pass_filter(8000)
            
            processed_filename = f"{file_id}_processed.wav"
            processed_path = os.path.join(directories['processed'], processed_filename)
            processed_audio.export(processed_path, format="wav")
            print(f"   Processed WAV created: {processed_filename}")
        except Exception as e:
            print(f"   Warning: Advanced processing failed: {e}")
            processed_filename = wav_filename
            processed_path = wav_path
        
        return {
            'success': True,
            'wav_filename': wav_filename,
            'wav_path': wav_path,
            'processed_filename': processed_filename,
            'processed_path': processed_path,
            'duration': len(audio) / 1000.0,
            'sample_rate': 44100,
            'channels': 1,
            'wav_size': os.path.getsize(wav_path),
            'processed_size': os.path.getsize(processed_path)
        }
        
    except Exception as e:
        print(f"❌ Audio processing error: {e}")
        return {'success': False, 'error': str(e)}

# Call end endpoint (matches your sendCallEndEvent)
@calls_bp.route('/end', methods=['POST'])
def call_end():
    """Handle call end metadata (no file upload)"""
    try:
        print("📞 Call end metadata received")
        
        # Get JSON data from request body
        call_data = request.get_json()
        
        if not call_data:
            return jsonify({
                'success': False,
                'error': 'No call data provided'
            }), 400

        print(f"📋 Call data: {call_data}")

        # Validate required fields
        required_fields = ['callId', 'userId', 'duration', 'startTime', 'endTime', 'language']
        for field in required_fields:
            if field not in call_data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Create call record
        call_record = {
            'id': len(call_history) + 1,
            'callId': call_data.get('callId'),
            'userId': call_data.get('userId'),
            'duration': call_data.get('duration'),
            'startTime': call_data.get('startTime'),
            'endTime': call_data.get('endTime'),
            'language': call_data.get('language'),
            'recordingPath': call_data.get('recordingPath'),
            'deviceInfo': call_data.get('deviceInfo', {}),
            'metadata': call_data.get('metadata', {}),
            'createdAt': datetime.now().isoformat()
        }

        # Store in memory (replace with database in production)
        call_history.append(call_record)

        print(f"📞 Call Ended:")
        print(f"   Call ID: {call_record['callId']}")
        print(f"   User: {call_record['userId']}")
        print(f"   Duration: {call_record['duration']}s ({call_record['duration']//60}m {call_record['duration']%60}s)")
        print(f"   Language: {call_record['language']}")
        print(f"   Recording: {'Yes' if call_record['recordingPath'] else 'No'}")
        print(f"   Device: {call_record['deviceInfo'].get('platform', 'unknown')}")
        print(f"   Total Calls: {len(call_history)}")
        print("-" * 50)

        return jsonify({
            'success': True,
            'message': 'Call end event recorded successfully',
            'data': {
                'callId': call_record['callId'],
                'recordId': call_record['id'],
                'timestamp': call_record['createdAt']
            }
        }), 200

    except Exception as e:
        print(f"❌ Error in call_end: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to record call end event',
            'details': str(e)
        }), 500

# Get call history endpoint (matches your getCallHistory)
@calls_bp.route('/history', methods=['GET'])
def get_call_history():
    try:
        user_id = request.args.get('userId')
        limit = int(request.args.get('limit', 10))
        
        filtered_calls = call_history
        
        if user_id:
            filtered_calls = [call for call in call_history if call['userId'] == user_id]
        
        # Sort by creation time (newest first)
        filtered_calls.sort(key=lambda x: x['createdAt'], reverse=True)
        
        # Apply limit
        limited_calls = filtered_calls[:limit]
        
        return jsonify({
            'success': True,
            'data': {
                'calls': limited_calls,
                'total': len(filtered_calls),
                'limit': limit
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Download processed files
@calls_bp.route('/download/<file_id>/<file_type>', methods=['GET'])
def download_call_recording(file_id, file_type):
    """Download processed WAV file"""
    try:
        print(f"📥 Download request: {file_id}/{file_type}")
        
        directories = ensure_upload_directories()
        
        if file_type == 'wav':
            filename = f"{file_id}_converted.wav"
            file_path = os.path.join(directories['converted'], filename)
            download_name = f"recording_{file_id}.wav"
        elif file_type == 'processed':
            filename = f"{file_id}_processed.wav"
            file_path = os.path.join(directories['processed'], filename)
            download_name = f"processed_{file_id}.wav"
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Use "wav" or "processed"'
            }), 400

        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404

        print(f"✅ Sending file: {download_name}")
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='audio/wav'
        )

    except Exception as e:
        print(f"❌ Download error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Get call info endpoint
@calls_bp.route('/info/<call_id>', methods=['GET'])
def get_call_info(call_id):
    """Get detailed information about a specific call"""
    try:
        call_record = next((call for call in call_history if call['callId'] == call_id), None)
        
        if not call_record:
            return jsonify({
                'success': False,
                'error': 'Call not found'
            }), 404

        return jsonify({
            'success': True,
            'data': call_record
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
