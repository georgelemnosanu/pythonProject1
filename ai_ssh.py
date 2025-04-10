import os
import sys
import uuid
import tempfile
import platform
import time
import random
import math
from typing import re

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

# === Sense HAT ===
sense = SenseHat()

# Definim calea de salvare a fișierelor într-o locație accesibilă
LOG_FILE = os.path.expanduser("~/asistent_ai/conversatie_log.txt")
USER_FILE = os.path.expanduser("~/asistent_ai/user_data.json")

# Asigură-te că directorul există
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)


def convert_pattern_to_pixels(pattern):
    """Converts a pattern of B (black) and Y (yellow) to pixels"""
    # Define colors
    Y = (255, 255, 0)  # Yellow
    B = (0, 0, 0)  # Black

    pixels = []
    for char in pattern:
        if char == 'Y':
            pixels.append(Y)
        else:  # 'B' or any other character
            pixels.append(B)

    return pixels


def afiseaza_emoji(tip):
    try:
        # Definirea culorilor
        Y = (255, 255, 0)  # galben
        B = (0, 0, 0)  # negru
        R = (255, 0, 0)  # roșu
        W = (255, 255, 255)  # alb
        BL = (135, 206, 235)  # albastru deschis
        G = (0, 255, 0)  # verde

        # Dicționarul de modele LED în format pattern de B și Y
        emoji_patterns = {
            "idle": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "vorbire": "B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y,B,Y",

            "trist": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,Y,Y,Y,Y,Y,B,B,B,Y,Y,Y,Y,B,B,B,B,Y,Y,Y,Y,B,B,B,B,B,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "fericit": "B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,Y,Y,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "ganditor": "B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,Y,B,B,B,Y,B,B,B,Y,Y,B,B,Y,B,B,B,Y,Y,B,B,Y,Y,Y,Y,Y,B,B,B,B,B,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "confuz": "B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,Y,B,B,B,Y,B,B,B,Y,Y,B,B,Y,B,B,Y,B,B,B,B,Y,B,Y,B,B,B,B,B,Y,Y,Y,Y,Y,B,B,B,B,B,Y,B,B,B,B,B,B,B,B,B,B,B,B",

            "cloud": "B,B,B,B,B,B,B,B,B,B,W,W,W,B,B,B,B,W,W,W,W,W,B,B,W,W,W,W,W,W,W,B,W,W,W,W,W,W,W,B,B,W,W,W,W,W,B,B,B,B,W,W,W,B,B,B,B,B,B,B,B,B,B,B",

            "heart": "B,B,Y,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,Y,B,Y,Y,Y,Y,Y,Y,B,B,B,Y,Y,Y,Y,B,B,B,B,B,Y,Y,B,B,B,B,B,B,B,Y,B,B,B,B,B,B,B,B,B,B,B",

            "smile": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "sad_face": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,Y,B,B,B,B,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "neutral": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "wink": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,B,Y,Y,B,B,Y,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "surprise": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,Y,Y,Y,Y,Y,Y,B,B,Y,B,B,B,B,Y,B,B,B,Y,Y,Y,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B,B",

            "question": "B,B,B,B,B,B,B,B,B,B,Y,Y,Y,Y,B,B,B,Y,B,B,B,B,Y,B,B,B,B,B,B,Y,B,B,B,B,B,B,Y,B,B,B,B,B,B,B,Y,B,B,B,B,B,B,B,B,B,B,B,B,B,Y,B,B,B"
        }

        # Check if it's a predefined pattern
        if tip in emoji_patterns:
            pattern = emoji_patterns[tip].replace(" ", "").split(",")
            pixels = convert_pattern_to_pixels(pattern)
            sense.set_pixels(pixels)
        else:
            # Default to idle
            pattern = emoji_patterns["idle"].replace(" ", "").split(",")
            pixels = convert_pattern_to_pixels(pattern)
            sense.set_pixels(pixels)

    except Exception as e:
        print("[Sense HAT] Emoji error:", e)


def afiseaza_ceas():
    """Display the current time on the LED matrix"""
    try:
        # Clear the display
        sense.clear()

        # Get current hour and minute
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Define colors
        R = (255, 0, 0)  # Red for hour
        B = (0, 0, 255)  # Blue for minute
        G = (0, 255, 0)  # Green for center

        # Draw clock face
        # Center pixel
        sense.set_pixel(3, 3, G)
        sense.set_pixel(4, 3, G)
        sense.set_pixel(3, 4, G)
        sense.set_pixel(4, 4, G)

        # Calculate hour hand position (using 12-hour format)
        hour_angle = ((hour % 12) + minute / 60) * (360 / 12)
        hour_x = int(3.5 + 2.5 * math.sin(math.radians(hour_angle)))
        hour_y = int(3.5 - 2.5 * math.cos(math.radians(hour_angle)))
        hour_x = max(0, min(7, hour_x))
        hour_y = max(0, min(7, hour_y))
        sense.set_pixel(hour_x, hour_y, R)

        # Calculate minute hand position
        minute_angle = minute * (360 / 60)
        minute_x = int(3.5 + 3 * math.sin(math.radians(minute_angle)))
        minute_y = int(3.5 - 3 * math.cos(math.radians(minute_angle)))
        minute_x = max(0, min(7, minute_x))
        minute_y = max(0, min(7, minute_y))
        sense.set_pixel(minute_x, minute_y, B)

        # Keep the clock displayed for 5 seconds
        time.sleep(5)

        # Return to idle state
        afiseaza_emoji("idle")

    except Exception as e:
        print("[Sense HAT] Clock display error:", e)


def read_sensors():
    """Read and announce sensor values from Sense HAT"""
    try:
        temperature = round(sense.get_temperature(), 1)
        humidity = round(sense.get_humidity(), 1)
        pressure = round(sense.get_pressure(), 1)

        sensor_text = f"Current readings: Temperature is {temperature} degrees Celsius, Humidity is {humidity} percent, and Pressure is {pressure} millibars."
        print("📊 Sensors:", sensor_text)

        return sensor_text
    except Exception as e:
        print("[Sense HAT] Sensor error:", e)
        return "I'm having trouble reading the sensors right now."


def play_tictactoe():
    """Simple TicTacToe game on SenseHat"""
    try:
        # Colors
        X = (255, 0, 0)  # Red for X
        O = (0, 0, 255)  # Blue for O
        B = (0, 0, 0)  # Black for empty
        G = (0, 255, 0)  # Green for grid

        # Initialize the game
        board = [B] * 9
        grid_pixels = [B] * 64

        # Draw the grid
        for i in range(8):
            grid_pixels[8 * 2 + i] = G  # Horizontal line 1
            grid_pixels[8 * 5 + i] = G  # Horizontal line 2
            grid_pixels[8 * i + 2] = G  # Vertical line 1
            grid_pixels[8 * i + 5] = G  # Vertical line 2

        sense.set_pixels(grid_pixels)
        print("🎮 Starting TicTacToe game")

        # Game loop
        current_player = X
        game_over = False

        while not game_over:
            # Wait for player input
            event = sense.stick.wait_for_event(emptybuffer=True)

            if event.action == "pressed":
                x, y = 0, 0

                # Map joystick direction to grid position
                if event.direction == "up":
                    y = 0
                elif event.direction == "middle":
                    y = 1
                elif event.direction == "down":
                    y = 2

                if event.direction == "left":
                    x = 0
                elif event.direction == "middle":
                    x = 1
                elif event.direction == "right":
                    x = 2

                pos = y * 3 + x

                # Place marker if position is empty
                if board[pos] == B:
                    board[pos] = current_player

                    # Update display
                    for i in range(9):
                        if board[i] != B:
                            row, col = i // 3, i % 3
                            pixel_row = row * 3
                            pixel_col = col * 3

                            # Draw X or O (simplified)
                            if board[i] == X:
                                grid_pixels[8 * (pixel_row + 1) + (pixel_col + 1)] = X
                            else:
                                grid_pixels[8 * (pixel_row + 1) + (pixel_col + 1)] = O

                    sense.set_pixels(grid_pixels)

                    # Switch player
                    current_player = O if current_player == X else X

                    # Check for win or draw
                    # (Simplified - would need more logic for a real game)

                    if event.direction == "pressed" and event.action == "middle":
                        game_over = True

        print("🎮 Game ended")
        time.sleep(2)
        afiseaza_emoji("idle")

    except Exception as e:
        print("[Sense HAT] TicTacToe error:", e)


def remove_emojis(text):
    """Remove common emoji characters from text"""
    emoji_patterns = re.compile("["
                                u"\U0001F600-\U0001F64F"  # emoticons
                                u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                u"\U0001F700-\U0001F77F"  # alchemical symbols
                                u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                                u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                                u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                                u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                                u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                                u"\U00002702-\U000027B0"  # Dingbats
                                u"\U000024C2-\U0001F251"
                                "]+", flags=re.UNICODE)
    return emoji_patterns.sub(r'', text)


def detecteaza_stare(text):
    text = text.lower()
    # Verificăm stări noi înainte de cele existente
    if any(cuv in text for cuv in ["love", "heart", "affection"]):
        return "heart"
    if any(cuv in text for cuv in ["cloud", "overcast", "grey", "gray"]):
        return "cloud"
    if any(cuv in text for cuv in ["happy", "great", "excited", "glad"]):
        return "smile"
    if any(cuv in text for cuv in ["sad", "sorry", "unfortunately"]):
        return "sad_face"
    if any(cuv in text for cuv in ["think", "maybe", "possibly"]):
        return "ganditor"
    if any(cuv in text for cuv in ["confused", "don't know", "unclear"]):
        return "confuz"
    if any(cuv in text for cuv in ["surprised", "wow", "amazing", "unbelievable"]):
        return "surprise"
    if any(cuv in text for cuv in ["wink", "joke", "kidding"]):
        return "wink"
    if any(cuv in text for cuv in ["neutral", "ok", "fine"]):
        return "neutral"
    if any(cuv in text for cuv in ["question", "wondering", "curious"]):
        return "question"
    return "idle"


def self_code(instruction):
    """Adds new code functionality based on instruction"""
    print(f"🔧 Self-modifying code: {instruction}")
    # In a real implementation, this would add new code
    # For now, we'll just add the sensor reading function
    global read_sensors
    if "sensor" in instruction.lower():
        # We've already defined read_sensors above, so we'll just use it
        pass

    return "I've added the requested functionality."


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

        # Afișăm modelul corespunzător stării
        afiseaza_emoji(emotie)
        try:
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
        # Update the last interaction time
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


def get_random_curious_prompt():
    """Generate a random curious prompt based on time of day and other factors"""
    current_hour = datetime.now().hour

    # Morning prompts (6 AM - 12 PM)
    morning_prompts = [
        "Did you have breakfast today? What did you eat?",
        "What are you looking forward to today?",
        "Morning person or night owl? I'm curious!",
        "Any exciting plans for today?"
    ]

    # Afternoon prompts (12 PM - 6 PM)
    afternoon_prompts = [
        "How's your day going so far?",
        "What's the most interesting thing you've done today?",
        "Did you have lunch yet? What did you have?",
        "Have you read anything interesting lately?"
    ]

    # Evening prompts (6 PM - 11 PM)
    evening_prompts = [
        "How was your day? Anything special happen?",
        "What was the highlight of your day?",
        "Any plans for the evening?",
        "What's your favorite way to relax in the evening?"
    ]

    # Night prompts (11 PM - 6 AM)
    night_prompts = [
        "Still up? What keeps you awake at this hour?",
        "Are you a night owl or just staying up late tonight?",
        "What's your favorite midnight snack?",
        "Do you have trouble sleeping sometimes too?"
    ]

    # General prompts (any time)
    general_prompts = [
        "What's your favorite hobby?",
        "Have you tried any new foods lately?",
        "What's something you're looking forward to?",
        "If you could travel anywhere, where would you go?",
        "What kind of music do you enjoy?",
        "Have you seen any good movies or shows lately?",
        "What makes you smile?",
        "What's something new you've learned recently?",
        "Do you have any pets?",
        "Tea or coffee? Or something else entirely?"
    ]

    # Select prompt based on time of day
    if 6 <= current_hour < 12:
        time_specific_prompts = morning_prompts
    elif 12 <= current_hour < 18:
        time_specific_prompts = afternoon_prompts
    elif 18 <= current_hour < 23:
        time_specific_prompts = evening_prompts
    else:
        time_specific_prompts = night_prompts

    # Combine time-specific and general prompts with more weight on time-specific
    all_prompts = time_specific_prompts * 2 + general_prompts
    return random.choice(all_prompts)


def asculta_si_raspunde():
    # Import re here
    import re

    rec = sr.Recognizer()
    tts = CloudTextToSpeech("/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json")
    afiseaza_emoji("idle")

    context = [
        {"role": "system",
         "content": "Ești un asistent personal cu o personalitate caldă și amuzantă, cu inițiativă. Îți amintești lucruri despre utilizator, îi spui pe nume dacă ți-l spune, și reacționezi ca un companion loial. Nu spui niciodată că ești un AI. Ești curios, glumeț, și empatic."}
    ]

    user_data = incarca_user_data()

    # Add the user's name to the context if it exists
    if user_data.get("nume"):
        context.append({"role": "system",
                        "content": f"The user's name is {user_data['nume']}. Always remember this and address them by name occasionally."})
        print(f"📝 Loaded user name: {user_data['nume']}")

    # Track inactivity
    last_interaction_time = time.time()
    curiosity_timer = time.time()
    CURIOSITY_INTERVAL = 60 * 5  # 5 minutes between curious prompts
    LISTENING_TIMEOUT = 30  # Seconds to listen before timeout

    # Track if the mic is currently on
    mic_active = False

    while True:
        try:
            current_time = time.time()

            # Check if it's time to be curious (only when mic is not active)
            if not mic_active and current_time - curiosity_timer > CURIOSITY_INTERVAL:
                curious_prompt = get_random_curious_prompt()
                print(f"🤔 Getting curious: {curious_prompt}")
                tts.vorbeste(curious_prompt, "question")
                curiosity_timer = current_time
                # Don't immediately turn on mic, wait for user to respond
                time.sleep(2)

            # Turn on mic for listening
            print("🎙️ Ascult...")
            afiseaza_emoji("idle")
            mic_active = True

            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source)
                print("🔊 Say something...")
                try:
                    # Use a timeout to avoid keeping mic on indefinitely
                    audio = rec.listen(source, timeout=LISTENING_TIMEOUT)
                    mic_active = False
                except sr.WaitTimeoutError:
                    print("⏱️ Listening timeout, turning off mic temporarily")
                    mic_active = False
                    time.sleep(1)  # Brief pause before potentially turning mic back on
                    continue

            user_input = rec.recognize_google(audio, language="en-US")
            print("🧑 You:", user_input)

            # Reset timers on successful input
            last_interaction_time = time.time()
            curiosity_timer = time.time()

            if user_input.lower() in ["stop", "exit", "quit"]:
                print("🔴 Oprit.")
                break

            # Check for game request
            if "play game" in user_input.lower() or "tic tac toe" in user_input.lower():
                context.append({"role": "user", "content": user_input})
                context.append({"role": "assistant", "content": "Let's play Tic Tac Toe on the SenseHat display!"})
                tts.vorbeste("Let's play Tic Tac Toe! Use the joystick to place your marks.", "smile")
                play_tictactoe()
                continue

            # Check for sensor reading request
            if "read sensors" in user_input.lower() or "sensor" in user_input.lower():
                sensor_text = read_sensors()
                context.append({"role": "user", "content": user_input})
                context.append({"role": "assistant", "content": sensor_text})
                tts.vorbeste(sensor_text, "idle")
                continue

            # Check for time/clock request
            if any(word in user_input.lower() for word in ["time", "clock", "hour", "what time"]):
                now = datetime.now()
                time_str = now.strftime("%H:%M")
                context.append({"role": "user", "content": user_input})
                context.append({"role": "assistant", "content": f"The current time is {time_str}."})
                tts.vorbeste(f"The current time is {time_str}.", "idle")
                afiseaza_ceas()
                continue

            # Name remembering - special handling
            if "my name is" in user_input.lower() or "i am" in user_input.lower() and len(user_input.split()) < 6:
                # Extract name after "my name is" or after "I am" if it's a short phrase
                if "my name is" in user_input.lower():
                    name = user_input.lower().split("my name is")[-1].strip().capitalize()
                else:
                    name = user_input.lower().split("i am")[-1].strip().capitalize()

                # Clean up the name and remove any punctuation
                name = re.sub(r'[^\w\s]', '', name).strip().capitalize()

                if name:
                    user_data["nume"] = name
                    # Save immediately
                    salveaza_user_data(user_data)
                    # Add to context as system message for stronger remembering
                    context = [msg for msg in context if not (msg.get("role") == "system" and "user's name is" in msg