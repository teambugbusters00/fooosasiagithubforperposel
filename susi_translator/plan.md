# System Architecture: Real-time Audio Transcription & Translation

This document outlines the architecture and design of the Real-time Audio Transcription and Translation system.

## 1. Overview
The system provides a distributed, real-time pipeline for capturing audio, transcribing it into text using OpenAI Whisper, and optionally translating it into multiple languages. It is designed for low latency and multi-tenant support.

## 2. System Components

### 2.1. Client-Side
*   **Audio Grabber (`audio_grabber.py` / `audio_grabber.html`)**: Captures audio from the microphone, chunks it into manageable pieces, and streams Base64-encoded audio to the backend.
*   **Transcribe Listener (`transcribe_listener.html`)**: A web-based client that polls or streams transcribed text for real-time display.

### 2.2. Backend (Server-Side)
The project provides two backend implementations:
*   **Django (`susi_translator/django/`)**: A robust implementation using Django REST Framework (DRF), providing structured API endpoints and Swagger documentation.
*   **Flask (`susi_translator/flask/`)**: A lightweight implementation for rapid deployment and simple transcription tasks.

### 2.3. Core Engines
*   **Transcription Engine**: 
    *   **Local**: Uses the `openai-whisper` library.
    *   **Remote**: Can connect to a `whisper.cpp` server for high-performance offloading.
*   **Translation Engine**: 
    *   Uses Susi AI translation APIs (`m2m.susi.ai` for neural translation or `llm.susi.ai` for LLM-based translation).

## 3. Data Flow

1.  **Audio Capture**: Client records audio and identifies pauses/silence to create `chunk_id`s.
2.  **Ingestion**: Client sends JSON payloads (Base64 audio + `tenant_id` + `chunk_id`) to the `/transcribe` endpoint.
3.  **Queuing**: The backend places incoming chunks into a thread-safe `Queue`.
4.  **Processing**: A background worker thread (`process_audio`):
    *   Pops chunks from the queue.
    *   Normalizes audio data.
    *   Invokes the Whisper model for transcription.
    *   Stores the result in an in-memory dictionary.
5.  **Translation (Optional)**: If requested, a secondary thread/process translates the transcript.
6.  **Retrieval**: The display client fetches transcripts via `/get_transcript` or `/list_transcripts`.

## 4. Multi-tenancy & Data Management
*   **Isolation**: All data is partitioned by `tenant_id`, ensuring users only see their own transcripts.
*   **In-Memory Storage**: Transcripts are stored in dictionaries for high-speed access without database overhead.
*   **Cleanup**: A background process (`clean_old_transcripts`) automatically removes data older than 2 hours to prevent memory leaks.

## 5. Technology Stack
*   **Language**: Python 3.x
*   **Frameworks**: Django (DRF), Flask
*   **ML Libraries**: OpenAI Whisper, PyTorch, NumPy
*   **Communication**: REST API (JSON), Base64 Encoding
*   **Utilities**: `pyaudio` (recording), `scipy` (WAV processing)

## 6. Key API Endpoints
*   `POST /transcribe`: Upload audio chunks.
*   `GET /get_transcript`: Retrieve transcript for a specific chunk.
*   `GET /list_transcripts`: List all transcripts for a tenant.
*   `GET /pop_latest_transcript`: Fetch and remove the most recent transcript.
