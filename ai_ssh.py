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

# Redirecționează descriptorul stderr la nivel de sistem pentru a suprime mesajele ALSA/JACK
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
os.close(devnull)

# === Config OpenAI și Google TTS ===
openai.api_key = os.environ.get("OPENAI_API_KEY")  # Asigură-te că variabila de mediu este setată
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
        self.current_process = None  # Pentru controlul redării

    def vorbeste(self, text, emotie="idle", stop_event=None):
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

        afiseaza_emoji("vorbire")  # Se afișează emoji pentru vorbire

        try:
            # Pornim redarea în modul controlabil
            process = subprocess.Popen(["mpg123", "-a", "plughw:2,0", filename])
            self.current_process = process
            # Bucla de așteptare a redării, într-o manieră care permite întreruperea
            while process.poll() is None:
                if stop_event is not None and stop_event.is_set():
                    process.terminate()
                    break
                time.sleep(0.2)
        except Exception as e:
            print("Eroare la redare audio:", e)
        finally:
            self.current_process = None
            os.remove(filename)
            afiseaza_emoji(emotie)

def wake_word_detection():
    """
    Ascultă 5 secunde pentru a detecta cuvântul de trezire "assistant".
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
        except Exception:
            pass
    return False

def listen_user_input():
    """
    Ascultă inputul utilizatorului cu detectarea liniștii (phrase_time_limit).
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("Ascult, te rog, ce dorești să spui...")
        rec.adjust_for_ambient_noise(source)
        try:
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
        raspuns = openai.ChatCompletion.create(
            model="gpt-4o",  # Alternativ, "gpt-3.5-turbo"
            messages=[{"role": "user", "content": user_text}]
        )
        mesaj_ai = raspuns.choices[0].message.content
        print("🤖 AI:", mesaj_ai)
        return mesaj_ai
    except Exception as e:
        print("❌ Eroare la apelarea API-ului ChatGPT:", e)
        return "I'm sorry, I encountered an error."

def monitor_interruption(tts_instance, stop_event):
    """
    Monitorizează intrările de la microfon pentru cuvinte de întrerupere ("assistant" sau "stop").
    Dacă se detectează, setează stop_event pentru a întrerupe redarea TTS.
    Această funcție rulează într-un thread separat.
    """
    rec = sr.Recognizer()
    while not stop_event.is_set():
        try:
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source)
                # Ascultăm cu un timeout scurt și phrase_time_limit scurt
                audio = rec.listen(source, timeout=2, phrase_time_limit=2)
                text = rec.recognize_google(audio, language="en-US")
                # Dacă se detectează cuvinte de întrerupere
                if any(word in text.lower() for word in ["assistant", "stop", "quit", "exit"]):
                    print("Interrupere detectată:", text)
                    stop_event.set()
                    # Dacă există un proces TTS curent, îl terminăm
                    if tts_instance.current_process is not None:
                        tts_instance.current_process.terminate()
                    break
        except Exception:
            # Ignorăm erorile și repetăm
            pass
        time.sleep(0.5)

def main_loop():
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    while True:
        # Detectăm wake word
        if not wake_word_detection():
            continue  # Dacă nu este detectat, revenim la început

        user_input = listen_user_input()
        if user_input.lower() in ["stop", "exit", "quit"]:
            print("Programul se închide.")
            break
        if user_input.strip() == "":
            continue

        mesaj_ai = get_chat_response(user_input)
        emotie = detecteaza_stare(mesaj_ai)

        # Creăm un eveniment pentru întrerupere și pornim thread-ul de monitorizare
        stop_event = threading.Event()
        monitor_thread = threading.Thread(target=monitor_interruption, args=(tts, stop_event))
        monitor_thread.start()

        # Pornim redarea TTS
        tts.vorbeste(mesaj_ai, emotie, stop_event=stop_event)

        monitor_thread.join()  # Așteptăm încheierea monitorizării înainte de a reporni

if __name__ == "__main__":
    main_loop()
