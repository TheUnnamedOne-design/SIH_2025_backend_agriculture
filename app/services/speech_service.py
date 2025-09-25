import os
import ffmpeg
from google.cloud import speech
from google.cloud import translate
from gtts import gTTS
import tempfile
from werkzeug.utils import secure_filename
import io
from pydub import AudioSegment

class SpeechService:
    def __init__(self, config):
        self.project_id = config['GOOGLE_PROJECT_ID']
        self.speech_client = speech.SpeechClient()
        self.translate_client = translate.TranslationServiceClient()
        self.location = "global"
        self.parent = f"projects/{self.project_id}/locations/{self.location}"
        
    def process_audio_file(self, audio_file_path):
        """Process uploaded audio file and convert to required format"""
        processed_file = tempfile.mktemp(suffix='.wav')
        
        # Convert to 16kHz mono WAV
        ffmpeg.input(audio_file_path).output(
            processed_file, 
            ac=1, 
            ar=16000
        ).overwrite_output().run()
        
        return processed_file
    
    def transcribe_audio(self, processed_file_path):
        """Transcribe audio to text with language detection"""
        with open(processed_file_path, "rb") as f:
            content = f.read()
        
        audio = speech.RecognitionAudio(content=content)
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            enable_automatic_punctuation=True,
            language_code="ml",  # Default: Malayalam
            alternative_language_codes=[
                "en", "hi", "bn", "mr", "te", "ta", "gu", "kn", "pa", "or"
            ],
        )
        
        response = self.speech_client.recognize(config=config, audio=audio)
        
        transcribed_text = ""
        detected_language = "en"  # Default to English
        
        for result in response.results:
            transcribed_text += result.alternatives[0].transcript
            if hasattr(result, "language_code"):
                detected_language = result.language_code
        
        return transcribed_text, detected_language
    

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

