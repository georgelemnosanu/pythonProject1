import os
import sys
import uuid
import tempfile
import platform
import time
import threading
import subprocess
import json
import cv2
import numpy as np
import face_recognition
import speech_recognition as sr
import openai
from google.cloud import texttospeech
from sense_hat import SenseHat

# Global lock pentru microfon
microphone_lock = threading.Lock()

# Redirecționează stderr (pentru a suprima mesajele native ALSA/JACK)
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
os.close(devnull)

# === Config OpenAI și Google TTS ===
openai.api_key = os.environ.get("OPENAI_API_KEY")  # Cheia API trebuie setată în mediul de sistem
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"

# === Sense HAT ===
sense = SenseHat()

# Fișiere pentru memorie persistentă
CONVERSATION_HISTORY_FILE = "conversation_history.json"
USER_DATA_FILE = "user_data.json"
# Fișierul pentru codificarea feței cunoscute
KNOWN_FACE_ENCODING_FILE = "known_face.npy"


#############################################
# Funcții pentru memorie (conversație & user data)
#############################################

def load_conversation_history(max_items=3):
    if os.path.exists(CONVERSATION_HISTORY_FILE):
        try:
            with open(CONVERSATION_HISTORY_FILE, "r") as f:
                history = json.load(f)
            return history[-max_items:]
        except Exception as e:
            print("Error loading conversation history:", e)
    return []


def update_conversation_history(user_text, ai_text):
    history = []
    if os.path.exists(CONVERSATION_HISTORY_FILE):
        try:
            with open(CONVERSATION_HISTORY_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append({"user": user_text, "nora": ai_text})
    try:
        with open(CONVERSATION_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print("Error updating conversation history:", e)


def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print("Error loading user data:", e)
    return {}


def update_user_data(name):
    data = load_user_data()
    data["name"] = name
    try:
        with open(USER_DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("Error updating user data:", e)


#############################################
# Funcții pentru afișare "emoji" & detectare stare
#############################################

def afiseaza_emoji(tip):
    print(f"[Emoji: {tip}]")


def detecteaza_stare(text):
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


#############################################
# Funcții pentru webcam folosind face_recognition
#############################################

def load_known_face_encoding():
    if os.path.exists(KNOWN_FACE_ENCODING_FILE):
        try:
            return np.load(KNOWN_FACE_ENCODING_FILE)
        except Exception as e:
            print("Error loading known face encoding:", e)
    return None


def save_known_face_encoding(face_encoding):
    try:
        np.save(KNOWN_FACE_ENCODING_FILE, face_encoding)
    except Exception as e:
        print("Error saving known face encoding:", e)


def monitor_webcam(tts_instance):
    cap = cv2.VideoCapture(0)
    known_face_encoding = load_known_face_encoding()
    face_detected = False
    last_seen = 0
    absent_threshold = 3  # secunde de absență pentru a declanșa salutul
    processing_new_face = False
    new_face_counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Could not read frame from webcam.")
            time.sleep(1)
            continue

        # Convertim cadrul din BGR (OpenCV) în RGB (face_recognition necesită RGB)
        rgb_frame = frame[:, :, ::-1]
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        current_time = time.time()

        if len(face_encodings) > 0:
            current_encoding = face_encodings[0]
            print("Face captured.")
            last_seen = current_time
            if known_face_encoding is not None:
                # Comparația se face cu toleranța implicită sau specificată, de exemplu, 0.6
                matches = face_recognition.compare_faces([known_face_encoding], current_encoding, tolerance=0.6)
                if matches[0]:
                    new_face_counter = 0
                    if not face_detected and (current_time - last_seen) >= absent_threshold:
                        user_data = load_user_data()
                        name = user_data.get("name", "darling")
                        print("Welcome back, " + name + "!")
                        tts_instance.vorbeste("Welcome back, " + name + "!", "idle")
                    face_detected = True
                    processing_new_face = False
                else:
                    new_face_counter += 1
                    print("New face counter: " + str(new_face_counter))
                    if new_face_counter >= 2 and not processing_new_face:
                        processing_new_face = True
                        print("I see someone new! Who are you?")
                        response = ask_for_new_face(tts_instance)
                        if response and "my name is" in response.lower():
                            parts = response.lower().split("my name is", 1)
                            if len(parts) == 2:
                                new_name = parts[1].strip().split()[0]
                                update_user_data(new_name)
                                save_known_face_encoding(current_encoding)
                                known_face_encoding = current_encoding
                                print("Nice to meet you, " + new_name + "!")
                                tts_instance.vorbeste("Nice to meet you, " + new_name + "!", "fericit")
                        else:
                            print("No valid identification received.")
                        face_detected = False
                        time.sleep(3)
                        processing_new_face = False
                        new_face_counter = 0
            else:
                # Dacă nu avem o față cunoscută, și dacă user_data conține un nume, salvăm codificarea
                user_data = load_user_data()
                if "name" in user_data:
                    save_known_face_encoding(current_encoding)
                    known_face_encoding = current_encoding
                    print("Saved your face as " + user_data["name"])
                    face_detected = True
                    processing_new_face = False
                    last_seen = current_time
        else:
            print("No face detected.")
            face_detected = False
        time.sleep(1)


#############################################
# Funcția auxiliară pentru a obține răspunsul vocal în identificare (ask_for_new_face)
#############################################

def ask_for_new_face(tts_instance):
    global microphone_lock
    with microphone_lock:
        tts_instance.vorbeste("I see someone new! Who are you?", "confuz")
        time.sleep(1)  # Așteaptă finalizarea TTS-ului
        rec = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source)
                print("Listening for new face identification...")
                audio = rec.listen(source, timeout=10, phrase_time_limit=5)
                response = rec.recognize_google(audio, language="en-US")
                print("New face response:", response)
                return response
        except Exception as e:
            print("Error in ask_for_new_face:", e)
            return None


#############################################
# Clasa pentru Google Cloud TTS
#############################################

class CloudTextToSpeech:
    def __init__(self, key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        self.client = texttospeech.TextToSpeechClient()
        self.system = platform.system()
        self.current_process = None

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

        afiseaza_emoji("vorbire")
        try:
            process = subprocess.Popen(["mpg123", "-a", "plughw:0,0", filename])
            self.current_process = process
            while process.poll() is None:
                if stop_event is not None and stop_event.is_set():
                    process.kill()
                    break
                time.sleep(0.2)
        except Exception as e:
            print("Error during audio playback:", e)
        finally:
            self.current_process = None
            os.remove(filename)
            if stop_event is not None:
                stop_event.set()
            afiseaza_emoji(emotie)


#############################################
# Funcții de wake word și ascultarea inputului (folosind lock)
#############################################

def wake_word_detection():
    with microphone_lock:
        rec = sr.Recognizer()
        with sr.Microphone() as source:
            print("Aștept wake word ('nora' / 'hey nora')...")
            rec.adjust_for_ambient_noise(source)
            try:
                audio = rec.listen(source, timeout=5, phrase_time_limit=3)
                text = rec.recognize_google(audio, language="en-US")
                print("Am auzit:", text)
                if "nora" in text.lower():
                    if text.lower().strip() in ["hey nora", "nora"]:
                        print("Wake confirmation: Yes, darling!")
                    print("Wake word detectat!")
                    return True
            except Exception:
                pass
    return False


def listen_user_input(timeout=15, phrase_limit=7):
    with microphone_lock:
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


#############################################
# Funcția pentru a obține răspunsul de la ChatGPT
#############################################

def get_chat_response(user_text):
    try:
        history = load_conversation_history(max_items=3)
        history_str = ""
        if history:
            interactions = []
            for item in history:
                interactions.append(f"User said: {item['user']}\nNora replied: {item['nora']}")
            history_str = "\n".join(interactions)
        user_data = load_user_data()
        name_context = ""
        if "name" in user_data:
            name_context = f"Remember, your name is {user_data['name']}. "
        system_message = {
            "role": "system",
            "content": (
                    "You are Nora, a loving, enthusiastic, and humorous girlfriend AI. "
                    "Speak in a warm, affectionate tone, always addressing the user as 'darling'. "
                    "Your responses are caring, witty, and supportive, and vary your language to avoid repetition. " +
                    name_context +
                    ("Recent conversation history:\n" + history_str if history_str else "") +
                    "\nKeep your answer brief and concise (no more than three lines) and do not include emojis."
            )
        }
        raspuns = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                system_message,
                {"role": "user", "content": user_text}
            ]
        )
        mesaj_ai = raspuns.choices[0].message.content
        print("🤖 Nora:", mesaj_ai)
        update_conversation_history(user_text, mesaj_ai)
        return mesaj_ai
    except Exception as e:
        print("❌ Error calling ChatGPT API:", e)
        return "I'm sorry, darling, I encountered an error."


#############################################
# Funcția de monitorizare a întreruperii în timpul redării TTS
#############################################

def monitor_interruption(tts_instance, stop_event):
    with microphone_lock:
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
                            tts_instance.current_process.kill()
                        break
            except Exception:
                pass
            time.sleep(0.05)


#############################################
# Funcția principală
#############################################

def main_loop():
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    awake = False

    # Pornește monitorizarea webcam-ului într-un thread daemon
    webcam_thread = threading.Thread(target=monitor_webcam, args=(tts,), daemon=True)
    webcam_thread.start()

    while True:
        if not awake:
            if not wake_word_detection():
                continue
            else:
                awake = True
                print("Nora is now awake, darling!")
                tts.vorbeste("Yes, darling!", "idle")

        user_input = listen_user_input(timeout=15, phrase_limit=7)

        # Actualizează numele dacă utilizatorul spune "my name is ..."
        if user_input.lower().startswith("my name is"):
            parts = user_input.split("my name is", 1)
            if len(parts) == 2:
                name = parts[1].strip().split()[0]
                update_user_data(name)
                print(f"Got it, darling, I'll remember your name as {name}!")
                tts.vorbeste(f"Alright, darling, I'll remember your name is {name}.", "idle")
                continue

        if user_input.lower() in ["stop", "exit", "quit", "that's all", "bye"]:
            tts.vorbeste("Alright, darling, talk to you later!", "idle")
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
