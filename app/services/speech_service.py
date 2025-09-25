import os
import ffmpeg
from google.cloud import speech_v2
from google.cloud import translate
from gtts import gTTS
import tempfile
from werkzeug.utils import secure_filename
import io
from pydub import AudioSegment

class SpeechService:
    def __init__(self, config):
        self.project_id = config['GOOGLE_PROJECT_ID']
        self.speech_client = speech_v2.SpeechClient()  # Fixed: use speech_v2
        self.translate_client = translate.TranslationServiceClient()
        self.location = "global"
        self.parent = f"projects/{self.project_id}/locations/{self.location}"
        
    def process_audio_file(self, audio_file_path):
        """Process uploaded audio file and convert to required format"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            processed_file = temp_file.name  # Fixed: use secure temp file
        
        # Convert to 16kHz mono WAV
        ffmpeg.input(audio_file_path).output(
            processed_file, 
            ac=1, 
            ar=16000
        ).overwrite_output().run()
        
        return processed_file
    
    def transcribe_audio(self, processed_file_path):
        """Transcribe audio using Speech v2 API with 3 languages"""
        with open(processed_file_path, "rb") as f:
            content = f.read()
        
        # Initialize client with US regional endpoint
        client_options = {"api_endpoint": "us-speech.googleapis.com"}
        client = speech_v2.SpeechClient(client_options=client_options)
        
        # Configuration for automatic language detection
        config = speech_v2.RecognitionConfig(
            auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
            language_codes=[
                "ml-IN",  # Malayalam
                "ta-IN",  # Hindi  
                "en-IN",  # English (India)
            ],
            model="latest_long",
        )
        
        # Create request with US multi-region
        request = speech_v2.RecognizeRequest(
            recognizer=f"projects/{self.project_id}/locations/us/recognizers/_",
            config=config,
            content=content,
        )
        
        try:
            # Recognize speech
            response = client.recognize(request=request)
            
            # Extract transcript and detected language
            transcribed_text = ""
            detected_language = "unknown"
            
            for result in response.results:
                transcribed_text += result.alternatives[0].transcript
                if hasattr(result, 'language_code'):
                    detected_language = result.language_code
            
            print("Detected language:", detected_language)
            print("Transcript:", transcribed_text)
            
            return transcribed_text, detected_language
            
        except Exception as e:
            print(f"Speech v2 transcription error: {e}")
            return "", "en-IN"


    

    def translate_to_english(self, text, source_language):
        """Translate text to English"""
        if source_language == "en":
            return text
            
        translation = self.translate_client.translate_text(
            request={
                "parent": self.parent,
                "contents": [text],
                "mime_type": "text/plain",
                "source_language_code": source_language,
                "target_language_code": "en",
            }
        )
        return translation.translations[0].translated_text
    
    def translate_from_english(self, text, target_language):
        """Translate English text back to target language"""
        if target_language == "en":
            return text
            
        retranslation = self.translate_client.translate_text(
            request={
                "parent": self.parent,
                "contents": [text],
                "mime_type": "text/plain",
                "source_language_code": "en",
                "target_language_code": target_language,
            }
        )
        return retranslation.translations[0].translated_text
    
    def text_to_speech(self, text, language_code):
        """Convert text to speech and return as WAV"""
        
        
        try:
            lang = language_code.split("-")[0]
            tts = gTTS(text, lang=lang)
            
            # Save to bytes buffer first
            mp3_buffer = io.BytesIO()
            tts.write_to_fp(mp3_buffer)
            mp3_buffer.seek(0)
            
            # Convert MP3 to WAV for better compatibility
            audio = AudioSegment.from_mp3(mp3_buffer)
            
            # Save as WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                wav_file = temp_file.name
            
            audio.export(wav_file, format="wav")
            return wav_file
            
        except Exception as e:
            print(f"TTS Error: {e}")
            raise e

