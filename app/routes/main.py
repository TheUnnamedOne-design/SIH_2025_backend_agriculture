from flask import Blueprint, render_template, request, jsonify, current_app
from app.services.pdf_service import PDFService
from app.services.soil_service import SoilService
from app.services.api_service import APIService
from app.services.location_service import LocationService

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
        
        # Initialize other services
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
        
        # Get RAG answer using the service instance
        answer, retrieved = rag_service.rag_answer(user_query, context_data, user_choice)
        
        return jsonify({
            'answer': answer,
            'retrieved_chunks': [
                {'id': cid, 'text': txt[:200], 'score': score}
                for cid, txt, score in retrieved
            ],
            'context': context_data[:500]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
