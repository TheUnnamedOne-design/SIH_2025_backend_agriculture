from flask import Blueprint, render_template, request, jsonify, current_app
from app.services.pdf_service import PDFService
from app.services.soil_service import SoilService
from app.services.api_service import APIService
from app.services.location_service import LocationService
import uuid
import time

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    print("Index route called - rendering template")
    return render_template('index.html')

@main_bp.route('/test')  
def test():
    return "<h1>Flask is working!</h1><p>This is a test page.</p>"

@main_bp.route('/simple')
def simple():
    return render_template('simple.html')

@main_bp.route('/health')
def health():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Server is running'
    })



@main_bp.route('/query', methods=['POST'])
def process_query():
    try:
        # Use the app-level RAG service (already initialized)
        rag_service = current_app.rag_service
        
        data = request.json
        user_query = data.get('query')
        user_choice = data.get('choice', 1)
        district_name = data.get('district')
        state = data.get('state')
        current_crop = data.get('current_crop', '')
        
        # ===== FIXED: Session Management =====
        session_id = data.get('session_id')
        
        # Generate new session if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            print(f"DEBUG: Generated new session_id: {session_id}")
        else:
            print(f"DEBUG: Using existing session_id: {session_id}")
        
        # Initialize session storage if not exists
        if not hasattr(rag_service, 'user_sessions'):
            rag_service.user_sessions = {}
            rag_service.session_metadata = {}
        
        # Clean up old sessions
        current_time = time.time()
        if not hasattr(rag_service, 'last_cleanup'):
            rag_service.last_cleanup = current_time
        
        if current_time - rag_service.last_cleanup > 1800:
            cleanup_old_sessions(rag_service, max_age=3600)
            rag_service.last_cleanup = current_time
        
        # ===== FIXED: Proper Session Setup =====
        session_needs_init = False
        
        if session_id not in rag_service.user_sessions:
            print(f"DEBUG: Initializing new session for {session_id}")
            session_needs_init = True
            # Initialize session with separate conversation history
            rag_service.user_sessions[session_id] = {
                'chat_session': None,
                'conversation_history': [],
                'choice': user_choice
            }
            rag_service.session_metadata[session_id] = {
                'created_at': current_time,
                'last_used': current_time,
                'choice': user_choice,
                'location': f"{district_name}, {state}"
            }
        else:
            # Update session metadata
            rag_service.session_metadata[session_id]['last_used'] = current_time
            
            # Check if choice changed - if so, reinitialize chat session only
            if rag_service.user_sessions[session_id]['choice'] != user_choice:
                print(f"DEBUG: Choice changed for session {session_id}, reinitializing chat session")
                rag_service.user_sessions[session_id]['chat_session'] = None  # Reset chat session
                rag_service.user_sessions[session_id]['choice'] = user_choice
                rag_service.session_metadata[session_id]['choice'] = user_choice
                session_needs_init = True
        
        # ===== FIXED: Set Active Session Context =====
        # Always set the active session context BEFORE any RAG operations
        current_session = rag_service.user_sessions[session_id]
        rag_service.conversation_history = current_session['conversation_history']
        
        # Initialize or get existing chat session
        if session_needs_init or current_session['chat_session'] is None:
            current_session['chat_session'] = rag_service.initialize_chat_session(user_choice)
        
        # Set the active chat session
        rag_service.chat_session = current_session['chat_session']
        
        print(f"DEBUG: Session {session_id} has {len(rag_service.conversation_history)} conversation entries")
        
        # ===== Rest of your original code =====
        config = current_app.config
        location_service = LocationService()
        
        # Get coordinates and elevation
        latitude, longitude = location_service.get_coordinates(district_name, state)
        print(f"DEBUG: {district_name}, {state} -> Coordinates: {latitude}, {longitude}")

        if not latitude or not longitude:
            return jsonify({'error': 'Could not find location coordinates'}), 400
        
        elevation = location_service.get_elevation(latitude, longitude)
        print(f"DEBUG: Elevation: {elevation}")
        
        # Prepare context based on choice
        if user_choice == 1:
            # Farming advice
            soil_service = SoilService()
            api_service = APIService(config['OGD_API_KEY'], config['RESOURCE_ID'])
            context_data = soil_service.get_soil_data(
                district_name, config['SOIL_DATA_PATH'], 
                latitude, longitude, api_service
            ) + f" elevation of {elevation} mtrs"
        elif user_choice == 2:
            # Pesticide advice
            context_data = f'''
            from {district_name} of state of {state},
            with an altitude of {elevation},
            the current crop being grown is {current_crop}.
            '''
        
        # Check if index exists
        if rag_service.index is None:
            return jsonify({
                'error': 'No index found. Please build the index first by calling /api/build-index'
            }), 400
        
        # Get RAG answer using the service instance (now with proper session memory!)
        answer, retrieved = rag_service.rag_answer(user_query, context_data, user_choice)
        
        # ===== FIXED: Save Session State Back =====
        # After RAG processing, save the updated conversation history back to session
        rag_service.user_sessions[session_id]['conversation_history'] = rag_service.conversation_history
        
        # Enhanced response with session info
        response = {
            'answer': answer,
            'retrieved_chunks': [
                {'id': cid, 'text': txt[:200], 'score': score}
                for cid, txt, score in retrieved
            ],
            'context': context_data[:500],
            'session_id': session_id,
            'session_info': {
                'is_new_session': session_needs_init,
                'conversation_length': len(rag_service.conversation_history),
                'choice': user_choice
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"ERROR in process_query: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ===== Session Management Utilities =====

def cleanup_old_sessions(rag_service, max_age=3600):
    """Remove sessions older than max_age seconds"""
    current_time = time.time()
    sessions_to_remove = []
    
    for session_id, metadata in rag_service.session_metadata.items():
        if current_time - metadata['last_used'] > max_age:
            sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        if session_id in rag_service.user_sessions:
            del rag_service.user_sessions[session_id]
        if session_id in rag_service.session_metadata:
            del rag_service.session_metadata[session_id]
        print(f"DEBUG: Cleaned up old session: {session_id}")
    
    if sessions_to_remove:
        print(f"DEBUG: Cleaned up {len(sessions_to_remove)} old sessions")


# ===== Enhanced Session Management Endpoints =====

@main_bp.route('/session/reset', methods=['POST'])
def reset_session():
    """Reset a specific conversation session"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400
        
        rag_service = current_app.rag_service
        
        if hasattr(rag_service, 'user_sessions') and session_id in rag_service.user_sessions:
            del rag_service.user_sessions[session_id]
            if hasattr(rag_service, 'session_metadata') and session_id in rag_service.session_metadata:
                del rag_service.session_metadata[session_id]
            
            return jsonify({
                'message': f'Session {session_id} reset successfully',
                'session_id': session_id
            })
        else:
            return jsonify({'message': 'Session not found or already reset'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/session/status/<session_id>', methods=['GET'])
def session_status(session_id):
    """Get status of a conversation session"""
    try:
        rag_service = current_app.rag_service
        
        if (hasattr(rag_service, 'user_sessions') and 
            session_id in rag_service.user_sessions):
            
            metadata = rag_service.session_metadata.get(session_id, {})
            session_data = rag_service.user_sessions[session_id]
            
            return jsonify({
                'session_exists': True,
                'session_id': session_id,
                'metadata': metadata,
                'conversation_length': len(session_data['conversation_history']),
                'recent_queries': [h.get('user', '')[:100] for h in session_data['conversation_history'][-3:]]
            })
        else:
            return jsonify({
                'session_exists': False,
                'session_id': session_id
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/sessions/active', methods=['GET'])
def active_sessions():
    """Get list of all active sessions"""
    try:
        rag_service = current_app.rag_service
        
        if not hasattr(rag_service, 'session_metadata'):
            return jsonify({'active_sessions': []})
        
        current_time = time.time()
        sessions = []
        
        for session_id, metadata in rag_service.session_metadata.items():
            session_data = rag_service.user_sessions.get(session_id, {})
            sessions.append({
                'session_id': session_id,
                'created_at': metadata.get('created_at', 0),
                'last_used': metadata.get('last_used', 0),
                'age_minutes': round((current_time - metadata.get('last_used', 0)) / 60, 1),
                'choice': metadata.get('choice'),
                'location': metadata.get('location'),
                'conversation_length': len(session_data.get('conversation_history', []))
            })
        
        # Sort by most recent first
        sessions.sort(key=lambda x: x['last_used'], reverse=True)
        
        return jsonify({
            'active_sessions': sessions,
            'total_count': len(sessions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ===== NEW: Debug Endpoint =====
@main_bp.route('/debug/session/<session_id>', methods=['GET'])
def debug_session(session_id):
    """Debug endpoint to see session state"""
    try:
        rag_service = current_app.rag_service
        
        if (hasattr(rag_service, 'user_sessions') and 
            session_id in rag_service.user_sessions):
            
            session_data = rag_service.user_sessions[session_id]
            
            return jsonify({
                'session_exists': True,
                'session_id': session_id,
                'conversation_history': session_data['conversation_history'],
                'conversation_length': len(session_data['conversation_history']),
                'has_chat_session': session_data['chat_session'] is not None,
                'choice': session_data.get('choice')
            })
        else:
            return jsonify({
                'session_exists': False,
                'session_id': session_id,
                'available_sessions': list(getattr(rag_service, 'user_sessions', {}).keys())
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500



