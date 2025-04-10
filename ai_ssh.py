import os
import sys
import uuid
import tempfile
import platform
import time
import speech_recognition as sr
import openai
from google.cloud import texttospeech
from sense_hat import SenseHat

# Suprimă avertismentele ALSA/JACK (dacă apar la nivelul stderr)
sys.stderr = open(os.devnull, 'w')


# === Config OpenAI ===
openai.api_key = os.environ.get("OPENAI_API_KEY")
# Setează calea către credențialele tale Google Cloud TTS
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"

# === Sense HAT ===
sense = SenseHat()

def afiseaza_emoji(tip):
    """
    Funcție simplificată pentru afișarea unui 'emoji'.
    Aici se va afișa doar un mesaj în consolă pentru simplitate.
    """
    print(f"[Emoji: {tip}]")

def detecteaza_stare(text):
    """
    Detectează o stare de bază pe baza textului.
    """
    text = text.lower()
    if any(cuv in text for cuv in ["happy", "great", "excited"]):
        return "fericit"
    if any(cuv in text for cuv in ["sad", "sorry", "unfortunately"]):
        return "trist"
    if any(cuv in text for cuv in ["think", "maybe", "possibly"]):
        return "ganditor"
    if any(cuv in text for cuv in ["confused", "don't know", "unclear"]):
        return "confuz"
    return "idle"

# === Google Cloud TTS ===
class CloudTextToSpeech:
    def __init__(self, key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        self.client = texttospeech.TextToSpeechClient()
        self.system = platform.system()

    def vorbeste(self, text, emotie="idle"):
        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Chirp3-HD-Achernar"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            effects_profile_id=["small-bluetooth-speaker-class-device"],
            pitch=0,
            speaking_rate=1
        )
        response = self.client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_config
        )
        filename = os.path.join(tempfile.gettempdir(), f"speech_{uuid.uuid4().hex}.mp3")
        with open(filename, "wb") as out:
            out.write(response.audio_content)

        afiseaza_emoji("vorbire")  # Se afișează emoji-ul pentru vorbire
        try:
            # Comanda de redare; asigură-te că mpg123 este instalat și configurat corect.
            os.system(f"mpg123 -a plughw:2,0 {filename}")
        except Exception as e:
            print("Eroare la redare audio:", e)
        finally:
            os.remove(filename)
            afiseaza_emoji(emotie)

def asculta_si_raspunde():
    rec = sr.Recognizer()
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    afiseaza_emoji("idle")

    while True:
        try:
            with sr.Microphone() as source:
                print("🎙️ Ascult...")
                audio = rec.listen(source)
            user_input = rec.recognize_google(audio, language="en-US")
            print("🧑 You:", user_input)

            if user_input.lower() in ["stop", "exit", "quit"]:
                print("🔴 Oprit.")
                break

            # Folosim noua interfață pentru API-ul OpenAI ChatCompletion
            raspuns = openai.ChatCompletion.create(
                model="gpt-4o",  # Dacă nu este disponibil, poți folosi "gpt-3.5-turbo"
                messages=[{"role": "user", "content": user_input}]
            )
            mesaj_ai = raspuns.choices[0].message.content
            print("🤖 AI:", mesaj_ai)

            # Detectează o stare de bază pe baza mesajului AI
            emotie = detecteaza_stare(mesaj_ai)
            tts.vorbeste(mesaj_ai, emotie)

        except sr.UnknownValueError:
            print("🤔 Nu am înțeles. Repetă.")
            afiseaza_emoji("trist")
            time.sleep(2)
            afiseaza_emoji("idle")
        except Exception as e:
            print("❌ Eroare majoră:", e)
            afiseaza_emoji("confuz")
            time.sleep(2)
            afiseaza_emoji("idle")

if __name__ == "__main__":
    asculta_si_raspunde()
