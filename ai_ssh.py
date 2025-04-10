import os
import sys
import uuid
import tempfile
import time
import speech_recognition as sr
import openai
from google.cloud import texttospeech

# Configurări
openai.api_key = "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"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/root/asistent_ai/maximal-mason-456321-g9-1853723212a3.json"


def google_tts(text, emotie="idle"):
    """
    Folosește Google Cloud TTS pentru a sintetiza textul și redă-l folosind mpg123.
    """
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
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
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    filename = os.path.join(tempfile.gettempdir(), f"speech_{uuid.uuid4().hex}.mp3")
    with open(filename, "wb") as out:
        out.write(response.audio_content)

    try:
        os.system(f"mpg123 {filename}")
    except Exception as e:
        print("Eroare la redare audio:", e)
    finally:
        os.remove(filename)


def wake_word_detection():
    """
    Ascultă pentru a detecta cuvântul de trezire „assistant”.
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Aștept cuvântul de trezire ('assistant')...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio, language="en-US")
            print("Am auzit:", text)
            if "assistant" in text.lower():
                print("Cuvântul de trezire detectat!")
                return True
        except Exception as e:
            print("Nu s-a detectat cuvântul de trezire:", e)
    return False


def listen_user_input():
    """
    Ascultă inputul vocal al utilizatorului.
    Folosim parametrul phrase_time_limit pentru a încheia înregistrarea atunci când utilizatorul
    încetează să vorbească (detectarea liniștii).
    """
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Ascult, te rog, ce dorești să spui...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            # phrase_time_limit înseamnă că, dacă nu se detectează vorbire timp de 5 secunde,
            # înregistrarea se oprește
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=5)
            user_text = recognizer.recognize_google(audio, language="en-US")
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
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Dacă nu este disponibil, poți folosi "gpt-3.5-turbo"
            messages=[{"role": "user", "content": user_text}]
        )
        message = response.choices[0].message.content
        print("ChatGPT răspunde:", message)
        return message
    except Exception as e:
        print("Eroare la apelarea API-ului ChatGPT:", e)
        return "I'm sorry, I encountered an error."


def main():
    while True:
        # Detectează wake word
        if wake_word_detection():
            user_input = listen_user_input()
            if user_input.lower() in ["exit", "quit", "stop"]:
                print("Programul se închide.")
                break
            if user_input:
                response_text = get_chat_response(user_input)
                google_tts(response_text)
        else:
            # Dacă nu se detectează wake word, așteptăm puțin și încercăm din nou
            time.sleep(1)


if __name__ == "__main__":
    main()
