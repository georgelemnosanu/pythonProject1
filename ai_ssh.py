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

# Redirecționează descriptorul stderr pentru a suprima mesajele ALSA/JACK
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
os.close(devnull)

# === Config OpenAI și Google TTS ===
openai.api_key = os.environ.get("OPENAI_API_KEY")  # Cheia API se așteaptă să fie setată în mediul de sistem
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"

# === Sense HAT ===
sense = SenseHat()


def afiseaza_emoji(tip):
    """
    Funcție simplificată pentru afișarea unui "emoji" (aici, doar un mesaj în consolă).
    """
    print(f"[Emoji: {tip}]")


def detecteaza_stare(text):
    """
    Detectează o stare de bază pe baza textului și returnează un indicator.
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
        """
        Sintetizează textul cu Google Cloud TTS și-l redă folosind mpg123.
        Dacă stop_event este setat în timpul redării, aceasta este întreruptă.
        """
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
            process = subprocess.Popen(["mpg123", "-a", "plughw:2,0", filename])
            self.current_process = process
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
            if stop_event is not None:
                stop_event.set()
            afiseaza_emoji(emotie)


def wake_word_detection():
    """
    Ascultă timp de 5 secunde pentru a detecta cuvântul de trezire ("nora"/"hey nora").
    Returnează True dacă este detectat.
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("Aștept wake word ('nora' / 'hey nora')...")
        rec.adjust_for_ambient_noise(source)
        try:
            audio = rec.listen(source, timeout=5, phrase_time_limit=3)
            text = rec.recognize_google(audio, language="en-US")
            print("Am auzit:", text)
            if "nora" in text.lower():
                print("Wake word detectat!")
                return True
        except Exception:
            pass
    return False


def listen_user_input(timeout=10, phrase_limit=5):
    """
    Ascultă inputul vocal al utilizatorului cu timeout și phrase_time_limit
    pentru detectarea tăcerii. Dacă nu se înțelege, returnează șirul gol.
    """
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        print("What would you like to say, darling?")
        rec.adjust_for_ambient_noise(source)
        try:
            audio = rec.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            user_text = rec.recognize_google(audio, language="en-US")
            print("Tu ai spus:", user_text)
            return user_text
        except Exception as e:
            print("I'm sorry, darling, can you repeat please?")
            return ""


def get_chat_response(user_text):
    """
    Trimite textul utilizatorului la ChatGPT și returnează răspunsul,
    includând un context de sistem care îl conferă personalitate asistentului.
    """
    try:
        system_message = {
            "role": "system",
            "content": (
                "You are Andra, a loving, enthusiastic, and humorous girlfriend AI. "
                "Speak in a warm, affectionate tone, always addressing the user as 'darling'. "
                "Your responses are caring, witty, and supportive, and you love to make the user smile."
            )
        }
        raspuns = openai.ChatCompletion.create(
            model="gpt-4o",  # sau "gpt-3.5-turbo" dacă preferi
            messages=[
                system_message,
                {"role": "user", "content": user_text}
            ]
        )
        mesaj_ai = raspuns.choices[0].message.content
        print("🤖 Andra:", mesaj_ai)
        return mesaj_ai
    except Exception as e:
        print("❌ Eroare la apelarea API-ului ChatGPT:", e)
        return "I'm sorry, darling, I encountered an error."


def monitor_interruption(tts_instance, stop_event):
    """
    Monitorizează intrările vocale la intervale scurte în timpul redării TTS.
    Dacă se detectează "nora", "stop", "exit" sau "quit", se setează stop_event
    și se întrerupe redarea.
    """
    rec = sr.Recognizer()
    while not stop_event.is_set():
        try:
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source)
                audio = rec.listen(source, timeout=0.8, phrase_time_limit=1)
                text = rec.recognize_google(audio, language="en-US")
                if any(word in text.lower() for word in ["nora", "stop", "exit", "quit"]):
                    print("Interruption detected:", text)
                    stop_event.set()
                    if tts_instance.current_process is not None:
                        tts_instance.current_process.terminate()
                    break
        except Exception:
            pass
        time.sleep(0.1)


def main_loop():
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    awake = False

    # Inițial așteptăm wake word pentru a activa modul conversațional
    while True:
        if not awake:
            if not wake_word_detection():
                continue
            else:
                awake = True
                print("Andra is now awake, darling!")

        user_input = listen_user_input(timeout=10, phrase_limit=5)
        if user_input.lower() in ["stop", "exit", "quit", "that's all", "bye"]:
            tts.vorbeste("Alright darling, talk to you later!", "idle")
            awake = False
            print("Returning to sleep mode...")
            continue

        if user_input.strip() == "":
            tts.vorbeste("Can you repeat please, darling?", "confuz")
            continue

        mesaj_ai = get_chat_response(user_input)
        emotie = detecteaza_stare(mesaj_ai)
        stop_event = threading.Event()

        monitor_thread = threading.Thread(target=monitor_interruption, args=(tts, stop_event))
        monitor_thread.start()

        tts.vorbeste(mesaj_ai, emotie, stop_event=stop_event)
        monitor_thread.join()


if __name__ == "__main__":
    main_loop()
