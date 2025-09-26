from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import os
from .calls import process_audio_to_wav, ensure_upload_directories, allowed_file

recordings_bp = Blueprint('recordings', __name__)

# In-memory storage (use database in production)
recordings_data = []

# Recording upload endpoint (matches your uploadRecording)
@recordings_bp.route('/upload', methods=['POST'])
def upload_recording():
    """Handle recording file upload with WAV conversion"""
    try:
        print("📁 Recording upload request received")
        
        # Check if recording is present
        if 'recording' not in request.files:
            print("⚠ No recording file in request")
            return jsonify({
                'success': False,
                'error': 'No recording file provided'
            }), 400

        recording_file = request.files['recording']
        if recording_file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        if not allowed_file(recording_file.filename):
            return jsonify({
                'success': False,
                'error': 'File type not allowed. Allowed: m4a, mp3, wav, aac, ogg, flac'
            }), 400

        print(f"📁 File received: {recording_file.filename}")

        # Get metadata from form
        metadata = {}
        if 'metadata' in request.form:
            try:
                metadata = json.loads(request.form.get('metadata'))
                print(f"📋 Metadata: {metadata}")
            except json.JSONDecodeError:
                print("⚠ Invalid metadata JSON, using empty metadata")
                metadata = {}

        # Ensure directories exist
        directories = ensure_upload_directories()
        
        # Generate file ID
        call_id = metadata.get('callId', 'unknown')
        segment_index = metadata.get('segmentIndex')
        timestamp = int(datetime.now().timestamp())
        
        if segment_index is not None:
            file_id = f"call_{call_id}_seg{segment_index}_{timestamp}"
        else:
            file_id = f"call_{call_id}_{timestamp}"
        
        # Save original file
        original_filename = secure_filename(recording_file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        original_saved_name = f"{file_id}_original.{file_extension}"
        original_path = os.path.join(directories['original'], original_saved_name)
        
        print(f"💾 Saving original file: {original_saved_name}")
        recording_file.save(original_path)
        
        # Process to WAV
        processed_result = process_audio_to_wav(original_path, file_id)
        
        if not processed_result['success']:
            # Clean up on error
            if os.path.exists(original_path):
                os.unlink(original_path)
            return jsonify({
                'success': False,
                'error': processed_result['error']
            }), 500

        # Store recording info
        recording_info = {
            'id': len(recordings_data) + 1,
            'fileId': file_id,
            'originalFilename': original_filename,
            'originalPath': original_path,
            'originalSize': os.path.getsize(original_path),
            'wavPath': processed_result['wav_path'],
            'processedPath': processed_result['processed_path'],
            'duration': processed_result['duration'],
            'sampleRate': processed_result['sample_rate'],
            'channels': processed_result['channels'],
            'uploadTime': datetime.now().isoformat(),
            'metadata': metadata
        }

        recordings_data.append(recording_info)

        print("✅ Audio processing completed successfully")

        return jsonify({
            'success': True,
            'message': 'Recording uploaded and processed successfully',
            'data': {
                'id': recording_info['id'],
                'fileId': file_id,
                'originalFile': original_saved_name,
                'size': recording_info['originalSize'],
                'duration': processed_result['duration'],
                'recording': {
                    'wav': {
                        'filename': processed_result['wav_filename'],
                        'downloadUrl': f"/api/calls/download/{file_id}/wav",
                        'size': processed_result.get('wav_size', 0)
                    },
                    'processed': {
                        'filename': processed_result['processed_filename'],
                        'downloadUrl': f"/api/calls/download/{file_id}/processed",
                        'size': processed_result.get('processed_size', 0)
                    },
                    'sampleRate': 44100,
                    'channels': 1
                }
            }
        }), 200

    except Exception as e:
        print(f"❌ Error in upload_recording: {e}")
        return jsonify({
            'success': False,
            'error': 'Upload failed',
            'details': str(e)
        }), 500

# Get recordings endpoint
@recordings_bp.route('/', methods=['GET'])
@recordings_bp.route('/user/<user_id>', methods=['GET'])
def get_recordings(user_id=None):
    try:
        filtered_recordings = recordings_data
        
        if user_id:
            filtered_recordings = [
                r for r in recordings_data 
                if r.get('metadata', {}).get('userId') == user_id
            ]
        
        # Sort by upload time (newest first)
        filtered_recordings.sort(key=lambda x: x['uploadTime'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': {
                'recordings': filtered_recordings,
                'total': len(filtered_recordings)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
