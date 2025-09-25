import os
# import ffmpeg  # Remove this line
from pydub import AudioSegment  # Add this instead
from google.cloud import speech_v2
from google.cloud import translate
from gtts import gTTS
import tempfile
from werkzeug.utils import secure_filename
import io

class SpeechService:
    def __init__(self, config):
        self.project_id = config['GOOGLE_PROJECT_ID']
        self.speech_client = speech_v2.SpeechClient()
        self.translate_client = translate.TranslationServiceClient()
        self.location = "global"
        self.parent = f"projects/{self.project_id}/locations/{self.location}"
        
    def get_language_code(self, frontend_language):
        """Map frontend language names to language codes"""
        language_map = {
            "Malayalam": "ml-IN",
            "Hindi": "hi-IN",
            "English": "en-IN",
            "Tamil": "ta-IN",
            "Telugu": "te-IN",
            "Bengali": "bn-IN",
            "Marathi": "mr-IN",
            "Gujarati": "gu-IN",
            "Kannada": "kn-IN",
            "Punjabi": "pa-IN",
            "Odia": "or-IN"
        }
        return language_map.get(frontend_language, "en-IN")
        
    def process_audio_file(self, audio_file_path):
        """Process uploaded audio file using pydub instead of ffmpeg"""
        try:
            print(f"Processing audio file: {audio_file_path}")
            
            # Load audio file with pydub
            audio = AudioSegment.from_file(audio_file_path)
            
            # Convert to mono, 16kHz (required for Google Speech)
            audio = audio.set_channels(1)  # Mono
            audio = audio.set_frame_rate(16000)  # 16kHz sample rate
            
            # Create temporary file for processed audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                processed_file = temp_file.name
            
            # Export as WAV
            audio.export(processed_file, format="wav")
            print(f"Audio processed and saved to: {processed_file}")
            
            return processed_file
            
        except Exception as e:
            print(f"Audio processing error: {e}")
            raise e
    
    def transcribe_audio(self, processed_file_path, preferred_language_name=None):
        """Transcribe audio with preferred language using Speech v2 API"""
        try:
            with open(processed_file_path, "rb") as f:
                content = f.read()
            
            # Initialize client with US regional endpoint
            client_options = {"api_endpoint": "us-speech.googleapis.com"}
            client = speech_v2.SpeechClient(client_options=client_options)
            
            # Get preferred language code
            if preferred_language_name:
                primary_lang = self.get_language_code(preferred_language_name)
            else:
                primary_lang = "en-IN"  # Default
                
            # All available languages
            all_langs = ["ml-IN", "hi-IN", "en-IN", "ta-IN", "te-IN", 
                        "mr-IN", "gu-IN", "kn-IN", "pa-IN", "bn-IN", "or-IN"]
            
            # Put preferred language first, others as alternatives
            language_codes = [primary_lang] + [lang for lang in all_langs if lang != primary_lang]
            
            # Configuration for automatic language detection
            config = speech_v2.RecognitionConfig(
                auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
                language_codes=language_codes[:3],  # Use top 3 for better performance
                model="latest_long",
            )
            
            # Create request with US multi-region
            request = speech_v2.RecognizeRequest(
                recognizer=f"projects/{self.project_id}/locations/us/recognizers/_",
                config=config,
                content=content,
            )
            
            # Recognize speech
            response = client.recognize(request=request)
            
            # Extract transcript and detected language
            transcribed_text = ""
            detected_language = primary_lang  # Default to preferred
            
            for result in response.results:
                if result.alternatives:
                    transcribed_text += result.alternatives[0].transcript
                    # Check for language detection
                    if hasattr(result, 'language_code') and result.language_code:
                        detected_language = result.language_code
                        
            print(f"Preferred language: {preferred_language_name} ({primary_lang})")
            print(f"Detected language: {detected_language}")
            print(f"Transcript: {transcribed_text}")
            
            return transcribed_text, detected_language
            
        except Exception as e:
            print(f"Speech transcription error: {e}")
            return "", primary_lang if preferred_language_name else "en-IN"

    def translate_to_english(self, text, source_language):
        """Translate text to English"""
        if not text or not text.strip():
            return text
        
        source_lang = source_language.lower().split('-')[0]
        
        if source_lang in ["en", "eng", "english"]:
            return text
            
        try:
            translation = self.translate_client.translate_text(
                request={
                    "parent": self.parent,
                    "contents": [text],
                    "mime_type": "text/plain", 
                    "source_language_code": source_lang,
                    "target_language_code": "en",
                }
            )
            return translation.translations[0].translated_text
            
        except Exception as e:
            print(f"Translation error (source: {source_lang} -> en): {e}")
            return text

    def translate_from_english(self, text, target_language):
        """Translate English text back to target language"""
        if not text or not text.strip():
            return text
        
        target_lang = target_language.lower().split('-')[0]
        
        if target_lang in ["en", "eng", "english"]:
            return text
            
        try:
            retranslation = self.translate_client.translate_text(
                request={
                    "parent": self.parent,
                    "contents": [text],
                    "mime_type": "text/plain",
                    "source_language_code": "en",
                    "target_language_code": target_lang,
                }
            )
            return retranslation.translations[0].translated_text
            
        except Exception as e:
            print(f"Translation error (en -> {target_lang}): {e}")
            return text
    
    def text_to_speech(self, text, language_code):
        """Convert text to speech audio file"""
        try:
            lang = language_code.split("-")[0]  # Extract base language code
            
            tts = gTTS(text, lang=lang, slow=False)
            
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
            print(f"TTS audio saved: {wav_file}")
            return wav_file
            
        except Exception as e:
            print(f"TTS Error: {e}")
            raise e
