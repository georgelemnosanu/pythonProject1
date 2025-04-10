import os
import sys
import uuid
import tempfile
import platform
import subprocess
import time
from google.cloud import texttospeech

# Setează calea către credențialele Google (actualizează calea după necesități)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"


class TestTTS:
    def __init__(self):
        try:
            self.client = texttospeech.TextToSpeechClient()
        except Exception as e:
            print("Error initializing TTS client:", e)
            sys.exit(1)
        self.system = platform.system()

    def say(self, text):
        """Sintetizează textul și redă fișierul audio."""
        print("Sintetizând: ", text)
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Chirp3-HD-Achernar"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0
        )
        try:
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
        except Exception as e:
            print("Error synthesizing speech:", e)
            return

        filename = os.path.join(tempfile.gettempdir(), f"test_{uuid.uuid4().hex}.mp3")
        try:
            with open(filename, "wb") as f:
                f.write(response.audio_content)
            print("Redarea fișierului audio...")
            # Asigură-te că ai instalat mpg123 și că dispozitivul audio este configurat corect
            subprocess.call(["mpg123", "-a", "plughw:2,0", filename])
        except Exception as ex:
            print("Error playing audio:", ex)
        finally:
            if os.path.exists(filename):
                os.remove(filename)


if __name__ == "__main__":
    tts = TestTTS()
    tts.say("Hello darling, this is a test. I am still speaking using Google Text-to-Speech.")
    time.sleep(1)
    print("Test finished.")
