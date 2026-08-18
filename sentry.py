import ollama
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr
import os
import time
import datetime
import asyncio
import edge_tts
import uuid
import ctypes
import subprocess
import webbrowser
import urllib.parse  # NEW: For formatting web search URLs safely


def speak(text):
    """Makes Century speak using high-quality Neural Voices, with an offline fallback."""
    print(f"CENTURY: {text}")

    clean_text = text.replace("*", "").replace("#", "").replace("_", "").replace("`", "").replace('"', '')
    audio_file = os.path.abspath(f"reply_{uuid.uuid4().hex}.mp3")

    async def generate_audio():
        communicate = edge_tts.Communicate(clean_text, "en-US-JennyNeural", rate="+5%")
        await communicate.save(audio_file)

    try:
        # Attempt to use the high-quality online voice
        asyncio.run(generate_audio())

        alias = "century_audio"
        ctypes.windll.winmm.mciSendStringW(f'open "{audio_file}" alias {alias}', None, 0, 0)
        ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
        ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)

        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except Exception:
                pass

    except Exception as e:
        # FALLBACK: If there is no internet, use the built-in offline Windows voice
        print("[Network Error: Falling back to offline voice]")
        ps_command = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.SelectVoice("Microsoft Zira Desktop"); $synth.Speak("{clean_text}")'
        subprocess.run(["powershell", "-Command", ps_command], creationflags=subprocess.CREATE_NO_WINDOW)


def listen_for_command():
    """Listens using sounddevice and transcribes it."""
    fs = 16000
    seconds = 5
    filename = "temp_audio.wav"
    command_text = ""

    print("\nListening... (Speak now for 5 seconds)")

    myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
    sd.wait()
    sf.write(filename, myrecording, fs)

    recognizer = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio = recognizer.record(source)
        try:
            command_text = recognizer.recognize_google(audio).lower()
            print(f"You said: {command_text}")
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

    if os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as e:
            pass

    return command_text


def generate_response(prompt):
    """Sends the prompt to the local Phi-3 model via Ollama."""
    try:
        now = datetime.datetime.now()
        current_time_str = now.strftime("%I:%M %p on %A, %B %d, %Y")
        system_prompt = f"You are Century. You act like a chill, friendly, and slightly sarcastic human best friend. Don't act like a robot. Speak casually and naturally. Keep responses very short (1 to 3 sentences). The current date and time is {current_time_str}."
        full_prompt = f"{system_prompt}\nUser: {prompt}"

        response = ollama.chat(model='phi3', messages=[
            {'role': 'user', 'content': full_prompt}
        ])
        return response['message']['content']
    except Exception as e:
        return f"Error communicating with AI engine: {e}"


# --- NEW: SYSTEM CONTROL SKILLS ---
def open_application(app_name):
    """Attempts to open common Windows applications or websites."""
    speak(f"Opening {app_name}")
    try:
        if "notepad" in app_name:
            subprocess.Popen(["notepad.exe"])
        elif "calculator" in app_name:
            subprocess.Popen(["calc.exe"])
        elif "browser" in app_name or "edge" in app_name:
            subprocess.Popen(["msedge.exe"])
        elif "explorer" in app_name or "files" in app_name:
            subprocess.Popen(["explorer.exe"])
        elif "youtube" in app_name:
            webbrowser.open("https://www.youtube.com")
        elif "google" in app_name:
            webbrowser.open("https://www.google.com")
        elif "spotify" in app_name:
            # Using the Spotify URI protocol to launch the desktop app
            os.startfile("spotify:")
        else:
            speak(f"I don't have a shortcut configured for {app_name} yet.")
            return False
        return True
    except Exception as e:
        speak(f"I encountered an error trying to open {app_name}.")
        print(e)
        return False


def close_application(app_name):
    """Attempts to forcefully close an application using Windows taskkill."""
    speak(f"Attempting to close {app_name}")
    try:
        if "notepad" in app_name:
            os.system("taskkill /f /im notepad.exe")
        elif "calculator" in app_name:
            os.system("taskkill /f /im calculator.exe")  # Note: Modern Windows calc is tricky
        elif "browser" in app_name or "edge" in app_name:
            os.system("taskkill /f /im msedge.exe")
        else:
            speak(f"I don't know the process name for {app_name}.")
    except Exception as e:
        speak(f"Failed to close {app_name}.")
        print(e)


# --- NEW: WEB SEARCH SKILL ---
def perform_search(command):
    """Parses the command and opens a Google or YouTube search."""
    try:
        if "youtube" in command:
            # Extract the topic you want to search for
            search_term = command.split("youtube")[-1].replace("for", "").strip()
            if search_term:
                speak(f"Searching YouTube for {search_term}")
                # Format the URL for YouTube search
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_term)}"
                webbrowser.open(url)
            else:
                speak("Opening YouTube")
                webbrowser.open("https://www.youtube.com")

        elif "spotify" in command:
            # Extract what you want to play/search on Spotify
            if "play" in command:
                search_term = command.split("play")[-1].replace("on spotify", "").strip()
            else:
                search_term = command.split("spotify")[-1].replace("for", "").strip()

            if search_term:
                speak(f"Searching Spotify for {search_term}")
                # Use the spotify:search: URI to open the app directly to a search page
                os.startfile(f"spotify:search:{urllib.parse.quote(search_term)}")
            else:
                speak("Opening Spotify")
                os.startfile("spotify:")

        elif "google" in command or "search for" in command:
            # Extract the topic for Google
            if "google for" in command:
                search_term = command.split("google for")[-1].strip()
            elif "search for" in command:
                search_term = command.split("search for")[-1].strip()
            else:
                search_term = command.split("google")[-1].strip()

            if search_term:
                speak(f"Searching Google for {search_term}")
                # Format the URL for Google search
                url = f"https://www.google.com/search?q={urllib.parse.quote(search_term)}"
                webbrowser.open(url)
            else:
                speak("Opening Google")
                webbrowser.open("https://www.google.com")
        else:
            speak("I didn't catch what you want to search for.")
    except Exception as e:
        speak("I encountered an error trying to search the web.")
        print(e)


# -----------------------------

def run_sentry():
    """The main loop for the AI assistant."""
    speak("Century system initialized and standing by.")

    while True:
        command = listen_for_command()

        if command:
            if "century" in command:
                if "shutdown" in command or "sleep" in command:
                    speak("Shutting down core systems. Goodbye.")
                    break

                actual_query = command.replace("century", "").strip()

                if actual_query:
                    # --- SKILL ROUTING ---
                    if "time" in actual_query and ("what" in actual_query or "tell" in actual_query):
                        now = datetime.datetime.now().strftime("%I:%M %p")
                        speak(f"It is currently {now}.")
                        continue

                    # NEW: Open App Routing
                    if "open" in actual_query:
                        app_to_open = actual_query.replace("open", "").strip()
                        open_application(app_to_open)
                        continue

                    # NEW: Close App Routing
                    if "close" in actual_query:
                        app_to_close = actual_query.replace("close", "").strip()
                        close_application(app_to_close)
                        continue

                    # NEW: Web Search Routing
                    if "search" in actual_query:
                        perform_search(actual_query)
                        continue
                    # ----------------------

                    speak("Processing...")
                    answer = generate_response(actual_query)
                    speak(answer)
                else:
                    speak("Yes? How can I help?")

        time.sleep(1)


if __name__ == "__main__":
    run_sentry()