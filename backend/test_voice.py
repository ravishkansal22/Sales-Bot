"""
Ghost Negotiator Voice Input Test
Requirements:
    pip install SpeechRecognition pyaudio

Run:
    python voice_input_test.py
"""

import speech_recognition as sr

recognizer = sr.Recognizer()

# Improve handling of normal room noise
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8
recognizer.non_speaking_duration = 0.5

print("=" * 60)
print("Ghost Negotiator Voice Input Test")
print("Speak naturally after the prompt appears.")
print("Press Ctrl+C to exit.")
print("=" * 60)

while True:
    try:
        with sr.Microphone() as source:
            print("\nAdjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)

            print("🎤 Listening...")
            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=20
            )

            print("Processing...")
            text = recognizer.recognize_google(audio)

            print("\nRecognized Text:")
            print("-" * 60)
            print(text)
            print("-" * 60)

    except sr.WaitTimeoutError:
        print("No speech detected.")
    except sr.UnknownValueError:
        print("Could not understand the audio.")
    except sr.RequestError as e:
        print(f"Speech service error: {e}")
    except KeyboardInterrupt:
        print("\nExiting test.")
        break
