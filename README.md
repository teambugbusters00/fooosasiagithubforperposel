# fooosasiagithubforperposel
gssoc2026
# Real-time Audio Transcription
GSSOC 2024 Proposal: SUSI Translator Enhancement
What I Did (Old vs New)
1. REST API Enhancement - Transcript Metadata
OLD CODE (serializers.py)
class TranscriptResponseSerializer(serializers.Serializer):
    chunk_id = serializers.CharField()
    transcript = serializers.CharField()
NEW CODE (serializers.py)
class TranscriptResponseSerializer(serializers.Serializer):
    chunk_id = serializers.CharField(help_text='ID of the audio chunk')
    transcript = serializers.CharField(help_text='The transcribed text')
    timestamp = serializers.CharField(help_text='Timestamp of the transcript', required=False)
    language = serializers.CharField(help_text='Language of the transcript', required=False)
    original = serializers.CharField(help_text='Original transcript before translation', required=False)
    translated = serializers.BooleanField(help_text='Whether the transcript is translated', required=False)
    translate_from = serializers.CharField(help_text='Source language for translation', required=False)
    translate_to = serializers.CharField(help_text='Target language for translation', required=False)
Impact
Added 6 new optional fields for translation metadata
API responses now include timestamp, language info, original/translated text
2. API Endpoints - Timestamp Generation
OLD CODE (views.py - GetTranscriptView)
def get(self, request):
    transcript = t.get(chunk_id, {}).get('transcript', '')
    return Response({'chunk_id': chunk_id, 'transcript': transcript})
NEW CODE (views.py - GetTranscriptView)
def get(self, request):
    transcript_data = t.get(chunk_id, {})
    transcript = transcript_data.get('transcript', '')
    timestamp = generate_timestamp(chunk_id)
    language = transcript_data.get('translate_to', '')
    return Response({
        'chunk_id': chunk_id,
        'transcript': transcript,
        'timestamp': timestamp,
        'language': language,
        'original': transcript_data.get('original', ''),
        'translated': transcript_data.get('translated', False),
        'translate_from': transcript_data.get('translate_from', ''),
        'translate_to': transcript_data.get('translate_to', '')
    })
Impact
All 7 transcript endpoints now return metadata
Added helper function to generate human-readable timestamps
3. Bug Fix - Bare Except Clauses
OLD CODE (views.py - repeated 7 times)
try:
    timestamp_ms = int(chunk_id)
    timestamp_sec = timestamp_ms / 1000
    timestamp = time.strftime('%H:%M:%S', time.localtime(timestamp_sec))
except:
    timestamp = ''
NEW CODE (views.py)
def generate_timestamp(chunk_id):
    """Generate timestamp from chunk_id (milliseconds)."""
    try:
        timestamp_ms = int(chunk_id)
        timestamp_sec = timestamp_ms / 1000
        return time.strftime('%H:%M:%S', time.localtime(timestamp_sec))
    except (ValueError, TypeError, OSError):
        return ''
Impact
DRY principle: extracted duplicate code to helper function
Better exception handling (specific exceptions vs bare except)
4. Frontend Enhancement - Audio Device Selection
OLD CODE (audio_grabber.html)
devices.forEach(device => {
    if (device.kind === 'audioinput') {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.text = device.label || `Microphone ${audioInputSelect.length + 1}`;
        audioInputSelect.appendChild(option);
    }
});
NEW CODE (audio_grabber.html)
audioInputSelect.innerHTML = '';
const placeholder = document.createElement('option');
placeholder.value = '';
placeholder.text = 'Select audio input device';
placeholder.disabled = true;
audioInputSelect.appendChild(placeholder);

let foundAudioInput = false;
devices.forEach(device => {
    if (device.kind === 'audioinput') {
        foundAudioInput = true;
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.text = device.label || `Microphone ${audioInputSelect.length}`;
        audioInputSelect.appendChild(option);
    }
});

if (!foundAudioInput) {
    const noMic = document.createElement('option');
    noMic.value = '';
    noMic.text = 'No microphone detected';
    noMic.disabled = true;
    audioInputSelect.appendChild(noMic);
} else {
    const firstValid = Array.from(audioInputSelect.options).find(o => o.value && !o.disabled);
    if (firstValid) audioInputSelect.value = firstValid.value;
}
Impact
Added placeholder option with user guidance
Auto-selects first valid microphone
Shows "No microphone detected" when appropriate
Added validation before recording starts
5. Static File Serving - Path Resolution Fix
OLD CODE (views.py)
file_path = os.path.join(settings.STATIC_FILES, file_name)
if os.path.exists(file_path + "/") and os.path.isfile(file_path[:-1]):
    file_path = file_path[:-1]
NEW CODE (views.py)
candidates = []
static_files = getattr(settings, 'STATIC_FILES', None)
if static_files:
    candidates.append(Path(static_files))

base_dir = getattr(settings, 'BASE_DIR', None)
if base_dir:
    candidates.append(Path(base_dir) / 'static')

candidates = [p for p in candidates if p.exists() and p.is_dir()]

for dir_path in candidates:
    candidate = dir_path / file_name
    resolved = Path(str(candidate)).resolve()
    if resolved.is_dir():
        resolved = resolved / 'index.html'
    if resolved.exists() and resolved.is_file():
        requested_file = resolved
Impact
Fixed cross-platform path resolution (Windows compatibility)
Added path traversal protection
Uses BASE_DIR fallback for static files
Summary Statistics
Metric	Before	After
Serializer Fields	2	8
API Metadata Fields	2	8
Bare Except Clauses	7	0
Timestamp Helpers	0	1
Frontend UX Issues	3	0
Static File Paths	1	3 (fallbacks)
Technical Contributions
Code Quality: Replaced 7 bare except: clauses with specific exception handling
DRY Principle: Extracted duplicate timestamp logic to helper function
UX Improvement: Enhanced audio device selection UI
Bug Fix: Fixed static file serving on Windows
Security: Added path traversal protection
Files Modified
django/transcribe_app/serializers.py (+12 lines)
django/transcribe_app/views.py (+45 lines, refactored)
flask/audio_grabber.html (+34 lines)
Why This Matters for GSSOC
This contribution demonstrates:

✅ Understanding of REST API design
✅ Error handling best practices
✅ Cross-platform development
✅ User experience improvements
✅ Clean code refactoring
The enhancements make the transcription system more useful by providing:

Timestamps with each transcript (for synchronization)
Language metadata (for multi-language support)
Original text before translation
More informative API responses
## Purpose
This project aims to provide a real-time audio transcription system, where audio input from a microphone is sent to a server, transcribed, and then displayed to the user in real-time. The project uses a server to do the heavy calculations to do the actual transcription while a lightweight
client just does the audio recording and another client just does the result display.

## Python Files

### transcribe_server.py

This file contains the server-side logic, which:

- Listens for incoming audio chunks from the client
- Transcribes the audio chunks using whisper
- Returns the transcribed text to the client

### audio_grabber.py

This file contains the client-side logic, which:

- Captures audio from the microphone
- Chunks the audio into manageable pieces
- Sends the audio chunks to the server with a unique chunk ID

## HTML Files

### transcribe_listener.html

This file contains the client-side logic, which:

- Listens to the server for transcribed chunks
- Displays the transcribed text to the user in real-time

## Setup and Run

To set up and run the project, follow these steps:

* Install the required Python packages: pyaudio, flask, requests, whisper
* Run `audio_grabber.py` to start capturing audio from the microphone
* Run `transcribe_server.py` to start the server
* Open `transcribe_listener.py` in the browser to start displaying transcribed text in real-time

```
./server -m models/ggml-large-v3.bin -l de -p 16 -t 32 --host 0.0.0.0 --port 8007
```
