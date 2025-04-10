import os
import sys
import uuid
import tempfile
import platform
import time
import random
import math
import re
import speech_recognition as sr
import openai
import json
from datetime import datetime
from google.cloud import texttospeech
from sense_hat import SenseHat

# Dezactivează mesajele de eroare ALSA/JACK
sys.stderr = open(os.devnull, 'w')

# === Config OpenAI ===
openai.api_key = "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"

# Setează calea către cheia Google Cloud TTS
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/cale/catre/cheia_google.json"

# === Sense HAT ===
sense = SenseHat()

# Căi pentru salvarea datelor
LOG_FILE = os.path.expanduser("~/asistent_ai/conversatie_log.txt")
USER_FILE = os.path.expanduser("~/asistent_ai/user_data.json")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)


def afiseaza_emoji(tip):
    """
    Setează o culoare diferită pe Sense Hat pentru fiecare stare.
    (Aceasta este o versiune simplificată. În codul original puteai afișa modele LED.)
    """
    culori = {
        "idle": (0, 255, 0),  # Verde
        "question": (255, 0, 255),  # Mov
        "smile": (255, 255, 0),  # Galben
        "confuz": (255, 0, 0)  # Roșu
    }
    culoare = culori.get(tip, (255, 255, 255))
    sense.clear(culoare)


class CloudTextToSpeech:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient()

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

        afiseaza_emoji(emotie)
        try:
            # Redă fișierul audio folosind mpg123
            os.system(f"mpg123 -a plughw:2,0 {filename}")
        except Exception as e:
            print("Eroare la redare audio:", e)
        finally:
            os.remove(filename)
            afiseaza_emoji("idle")


def incarca_user_data():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error loading user data file. Creating new one.")
            return {"nume": None, "preferinte": [], "last_interaction": None}
    return {"nume": None, "preferinte": [], "last_interaction": None}


def salveaza_user_data(user_data):
    try:
        user_data["last_interaction"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(USER_FILE, "w") as f:
            json.dump(user_data, f)
        print(f"✅ User data saved successfully. Name: {user_data.get('nume')}")
    except Exception as e:
        print(f"❌ Error saving user data: {e}")


def log_conversatie(user_input, raspuns):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(f"USER: {user_input}\n")
            f.write(f"AI: {raspuns}\n\n")
    except Exception as e:
        print(f"❌ Error logging conversation: {e}")


def wake_word_detection():
    """
    Funcție simplă pentru detectarea cuvântului de trezire (wake word).
    Ascultă câteva secunde și, dacă în text se găsește 'assistant' (sau variante),
    atunci returnează True.
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("Spune cuvântul de trezire (ex.: 'assistant')...")
        rec.adjust_for_ambient_noise(source)
        try:
            audio = rec.listen(source, timeout=5)
            text = rec.recognize_google(audio, language="en-US")
            print("Ai spus:", text)
            if "assistant" in text.lower():
                print("Cuvânt de trezire detectat!")
                return True
        except Exception as e:
            print("Nu s-a detectat niciun cuvânt de trezire:", e)
    return False


def asculta_si_raspunde():
    rec = sr.Recognizer()
    tts = CloudTextToSpeech()
    afiseaza_emoji("idle")

    user_data = incarca_user_data()

    # Dacă numele utilizatorului există, îl putem folosi după preferințe
    if user_data.get("nume"):
        print(f"📝 Loaded user name: {user_data['nume']}")

    while True:
        # Așteptăm cuvântul de trezire
        if not wake_word_detection():
            print("Nu s-a detectat wake word, reîncerc...")
            continue

        print("🎙️ Ascultare activată...")
        afiseaza_emoji("idle")
        try:
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source)
                print("🔊 Vorbește acum...")
                audio = rec.listen(source, timeout=10)
            user_input = rec.recognize_google(audio, language="en-US")
            print("🧑 You:", user_input)
            if user_input.lower() in ["stop", "exit", "quit"]:
                print("🔴 Oprit.")
                break

            # Apel către ChatGPT
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": user_input}]
            )
            mesaj_ai = response.choices[0].message.content
            print("🤖 AI:", mesaj_ai)
            log_conversatie(user_input, mesaj_ai)

            # Setăm o stare simplă pentru emoji, în funcție de conținut
            if "?" in mesaj_ai:
                stare = "question"
            elif "happy" in mesaj_ai.lower():
                stare = "smile"
            else:
                stare = "idle"

            # Redă răspunsul vocal
            tts.vorbeste(mesaj_ai, stare)

        except sr.UnknownValueError:
            print("🤔 Nu am înțeles. Te rog repetă.")
            afiseaza_emoji("confuz")
            time.sleep(2)
            afiseaza_emoji("idle")
        except Exception as e:
            print("❌ Eroare majoră:", e)
            afiseaza_emoji("confuz")
            time.sleep(2)
            afiseaza_emoji("idle")


if __name__ == "__main__":
    asculta_si_raspunde()
