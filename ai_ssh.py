import os
import sys
import uuid
import tempfile
import platform
import time
import threading
import subprocess
import speech_recognition as sr
import openai
from google.cloud import texttospeech
from sense_hat import SenseHat

# Redirecționează stderr la nivel de sistem pentru a suprime mesajele ALSA/JACK
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
os.close(devnull)

# === Config OpenAI și Google TTS ===
openai.api_key = os.environ.get("OPENAI_API_KEY")  # Setează cheia API în mediul tău
# Setează calea către fișierul de credențiale Google
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"

# === Sense HAT ===
sense = SenseHat()

def afiseaza_emoji(tip):
    """
    Funcție simplificată pentru afișarea unui 'emoji' (aici doar un mesaj în consolă).
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

class CloudTextToSpeech:
    def __init__(self, key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        self.client = texttospeech.TextToSpeechClient()
        self.system = platform.system()
        self.current_process = None  # Pentru posibilă întrerupere

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

        afiseaza_emoji("vorbire")
        try:
            # Folosim subprocess pentru a putea controla procesul de redare
            process = subprocess.Popen(["mpg123", "-a", "plughw:2,0", filename])
            self.current_process = process
            process.wait()  # Așteptăm finalizarea redării
        except Exception as e:
            print("Eroare la redare audio:", e)
        finally:
            self.current_process = None
            os.remove(filename)
            afiseaza_emoji(emotie)

def wake_word_detection():
    """
    Ascultă câteva secunde pentru a detecta cuvântul de trezire "assistant".
    Returnează True dacă este detectat.
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("Aștept cuvântul de trezire ('assistant')...")
        rec.adjust_for_ambient_noise(source)
        try:
            audio = rec.listen(source, timeout=5, phrase_time_limit=3)
            text = rec.recognize_google(audio, language="en-US")
            print("Am auzit:", text)
            if "assistant" in text.lower():
                print("Cuvântul de trezire detectat!")
                return True
        except Exception as e:
            # Poți ignora erorile de timp
            pass
    return False

def listen_user_input():
    """
    Ascultă inputul utilizatorului și se oprește când nu se mai detectează vorbire.
    Folosim phrase_time_limit pentru a detecta tăcerea.
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("Ascult, te rog, ce dorești să spui...")
        rec.adjust_for_ambient_noise(source)
        try:
            # Dacă nu se mai vorbește timp de 5 secunde, se oprește ascultarea
            audio = rec.listen(source, timeout=10, phrase_time_limit=5)
            user_text = rec.recognize_google(audio, language="en-US")
            print("Tu ai spus:", user_text)
            return user_text
        except Exception as e:
            print("Nu am reușit să înțeleg vorbirea:", e)
            return ""

def get_chat_response(user_text):
    """
    Trimite textul utilizatorului la ChatGPT și returnează răspunsul.
    """
    try:
        # Folosim noua interfață: nu modificați această parte!
        raspuns = openai.ChatCompletion.create(
            model="gpt-4o",  # Sau "gpt-3.5-turbo" dacă este necesar
            messages=[{"role": "user", "content": user_text}]
        )
        mesaj_ai = raspuns.choices[0].message.content
        print("🤖 AI:", mesaj_ai)
        return mesaj_ai
    except Exception as e:
        print("❌ Eroare la apelarea API-ului ChatGPT:", e)
        return "I'm sorry, I encountered an error."

def interrupt_check(tts_instance, check_interval=1):
    """
    Monitorizează, la fiecare 'check_interval' secunde, dacă se detectează un nou wake word.
    Dacă da, întrerupe redarea TTS (dacă aceasta este în curs).
    """
    while tts_instance.current_process is not None:
        if wake_word_detection():
            print("Nou wake word detectat! Oprirea redării TTS...")
            try:
                tts_instance.current_process.terminate()
            except Exception as e:
                print("Eroare la întreruperea TTS:", e)
            break
        time.sleep(check_interval)

def main_loop():
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    while True:
        # Așteaptă cuvântul de trezire
        if not wake_word_detection():
            continue  # Dacă nu se detectează, revenim la începutul buclei

        # După ce se detectează wake word, ascultăm inputul utilizatorului
        user_input = listen_user_input()
        if user_input.lower() in ["stop", "exit", "quit"]:
            print("🔴 Oprit.")
            break
        if user_input.strip() == "":
            continue

        # Obține răspunsul ChatGPT
        mesaj_ai = get_chat_response(user_input)

        # Pornim TTS într-un thread separat
        tts_thread = threading.Thread(target=tts.vorbeste, args=(mesaj_ai, detecteaza_stare(mesaj_ai)))
        tts_thread.start()

        # În timp ce TTS-ul redă, monitorizăm dacă se detectează noul wake word (pentru întrerupere)
        interrupt_check(tts)
        tts_thread.join()  # Așteptăm să se termine redarea

if __name__ == "__main__":
    main_loop()
