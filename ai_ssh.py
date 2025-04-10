import os
import sys
import uuid
import tempfile
import platform
import time
import threading
import subprocess
import json
import speech_recognition as sr
import openai
from google.cloud import texttospeech
from sense_hat import SenseHat

# Redirecționează stderr pentru a suprima mesajele native (ALSA/JACK)
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
os.close(devnull)

# === Config OpenAI și Google TTS ===
openai.api_key = os.environ.get("OPENAI_API_KEY")  # Asigură-te că OPENAI_API_KEY este setată
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"

# === Sense HAT ===
sense = SenseHat()

# Fișiere pentru memorie persistentă
CONVERSATION_HISTORY_FILE = "conversation_history.json"
USER_DATA_FILE = "user_data.json"

#############################################
# Modele LED pentru Sense HAT (8x8)
#############################################

emoji_patterns = {
    "happy": [
        "B B Y Y Y Y B B",
        "B Y Y Y Y Y Y B",
        "Y Y R Y Y R Y Y",
        "Y Y R Y Y R Y Y",
        "Y Y Y Y Y Y Y Y",
        "Y Y R Y Y R Y Y",
        "B Y Y R R Y Y B",
        "B B Y Y Y Y B B"
    ],
    "sad": [
        "B B Y Y Y Y B B",
        "B Y Y Y Y Y Y B",
        "Y Y R Y Y R Y Y",
        "Y Y R Y Y R Y Y",
        "Y Y Y Y Y Y Y Y",
        "Y Y Y R R Y Y Y",
        "B Y R Y Y R Y B",
        "B B Y Y Y Y B B"
    ],
    "confuz": [
        "B B Y Y Y Y B B",
        "B Y Y Y Y Y Y B",
        "Y Y R R Y R R Y",
        "Y Y Y Y Y Y Y Y",
        "Y Y Y Y Y Y Y Y",
        "Y Y R R R R R Y",
        "B Y Y Y Y Y Y B",
        "B B Y Y Y Y B B"
    ],
    "idle": [
        "U B B U U B B U",
        "U B U B B U B U",
        "B U R B B R U B",
        "B U B B B B U B",
        "B B U R R U B B",
        "U U U U U U U U",
        "U B B U U B B U",
        "U B B B B B B U"
    ],
    "ganditor": [
        "B B B B B B B B",
        "B B R R B B B B",
        "B R B B R B B B",
        "B B B B R B B B",
        "B B B R B B B B",
        "B B R B B B B B",
        "B B B B B B B B",
        "B B R B B B B B"
    ],
    "love": [
        "B R R B B R R B",
        "R R R R R R R R",
        "R R R R R R R R",
        "R R R R R R R R",
        "R R R R R R R R",
        "B R R R R R R B",
        "B B R R R R B B",
        "B B B R R B B B"
    ],
    "go": [
        "B B B B B B B B",
        "P P P P B P P P",
        "P B B B B P B P",
        "P B B B B P B P",
        "P B P P B P B P",
        "P B B P B P B P",
        "P P P P B P P P",
        "B B B B B B B B"
    ]
}

# Maparea culorilor pentru LED
color_map = {
    'B': (0, 0, 0),  # black
    'Y': (255, 255, 0),  # yellow
    'R': (255, 0, 0),  # red
    'W': (255, 255, 255),  # white
    'U': (0, 0, 255),  # blue
    'O': (255, 165, 0),  # orange
    'P': (128, 0, 128),  # purple
    'K': (255, 192, 203)  # pink
}


def afiseaza_led(pattern_name):
    """Afișează pe matricea LED modelul specificat."""
    if pattern_name not in emoji_patterns:
        print(f"No LED pattern for {pattern_name}.")
        return
    rows = emoji_patterns[pattern_name]
    pixels = []
    for row in rows:
        letters = row.split()
        for letter in letters:
            pixels.append(color_map.get(letter, (0, 0, 0)))
    sense.set_pixels(pixels)


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
# Funcții pentru afișarea "emoji" & detectarea stării
#############################################

def afiseaza_emoji(tip):
    print(f"[Emoji: {tip}]")
    # Dacă există un pattern LED definit cu același nume, îl afișează
    if tip.lower() in emoji_patterns:
        afiseaza_led(tip.lower())


def detecteaza_stare(text):
    text = text.lower()
    if any(cuv in text for cuv in ["happy", "great", "excited"]):
        return "happy"
    if any(cuv in text for cuv in ["sad", "sorry", "unfortunately"]):
        return "sad"
    if any(cuv in text for cuv in ["think", "maybe", "possibly"]):
        return "ganditor"
    if any(cuv in text for cuv in ["confused", "don't know", "unclear"]):
        return "confuz"
    return "idle"


#############################################
# Funcția pentru citirea senzorilor Sense HAT
#############################################

def read_sensors():
    try:
        temperature = round(sense.get_temperature(), 1)
        humidity = round(sense.get_humidity(), 1)
        pressure = round(sense.get_pressure(), 1)
        sensor_text = (
            f"The current temperature is {temperature}°C, "
            f"humidity is {humidity}%, and pressure is {pressure} millibars."
        )
        print("📊 Sensors:", sensor_text)
        return sensor_text
    except Exception as e:
        print("Error reading sensors:", e)
        return "I'm sorry, darling, I'm having trouble reading the sensors right now."


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
            # Modificat pentru card 2 (Headphones)
            process = subprocess.Popen(["mpg123", "-a", "plughw:2,0", filename])
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
# Funcții pentru wake word și ascultarea inputului
#############################################

def wake_word_detection():
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
    # Înainte de a asculta, indică pe LED că este timpul să vorbești
    afiseaza_led("go")
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
            model="gpt-4o",  # or "gpt-3.5-turbo"
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

    while True:
        if not awake:
            if not wake_word_detection():
                continue
            else:
                awake = True
                print("Nora is now awake, darling!")
                tts.vorbeste("Yes, darling!", "idle")

        user_input = listen_user_input(timeout=15, phrase_limit=7)

        # Comandă pentru afișarea unui pattern LED dacă utilizatorul spune "show me ..."
        if "show me" in user_input.lower():
            parts = user_input.lower().split("show me", 1)
            if len(parts) == 2:
                pattern = parts[1].strip()
                if pattern in emoji_patterns:
                    print(f"Displaying {pattern} pattern on LED.")
                    afiseaza_led(pattern)
                    time.sleep(3)
                    afiseaza_led("idle")
                continue

        # Citește senzorii dacă inputul conține cuvinte legate de senzor
        if any(keyword in user_input.lower() for keyword in ["sensor", "temperature", "humidity", "pressure"]):
            sensor_text = read_sensors()
            tts.vorbeste(sensor_text, "idle")
            continue

        # Actualizează numele dacă se spune "my name is ..."
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
