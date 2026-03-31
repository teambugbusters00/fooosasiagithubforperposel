# transcribe_app/views.py
# (C) Michael Peter Christen 2024
# Licensed under Apache License Version 2.0


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .transcribe_utils import get_transcripts, add_to_audio_stack, process_audio, merge_and_split_transcripts, translate, logger
from .serializers import (
    TranscribeInputSerializer,
    TranscribeResponseSerializer,
    TranscriptResponseSerializer,
    ListTranscriptsResponseSerializer,
    SizeResponseSerializer
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.http import HttpResponse, Http404
from scipy.io.wavfile import write as wav_write
import numpy as np
import mimetypes
import threading
import pybars
import time
import os
from pathlib import Path


def generate_timestamp(chunk_id):
    """Generate a human-readable timestamp from a chunk_id (milliseconds timestamp)."""
    try:
        timestamp_ms = int(chunk_id)
        timestamp_sec = timestamp_ms / 1000
        return time.strftime('%H:%M:%S', time.localtime(timestamp_sec))
    except (ValueError, TypeError, OSError):
        return ''

# Start the audio processing thread
threading.Thread(target=process_audio).start()

def home(request):
    return HttpResponse("Welcome to the Transcription API!")

@method_decorator(csrf_exempt, name='dispatch')
class TranscribeView(APIView):
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        request_body=TranscribeInputSerializer,
        responses={200: TranscribeResponseSerializer}
    )
    def post(self, request):
        """
        The /transcribe endpoint expects JSON objects with base64-encoded audio binaries.
        Each chunk should have a unique chunk_id.
        The server processes each chunk and transcribes the audio using Whisper.
        """
        serializer = TranscribeInputSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            tenant_id = data.get('tenant_id', '0000')
            translate_from = data.get('translate_from', None)
            translate_to = data.get('translate_to', None)
            audio_b64 = data['audio_b64']
            chunk_id = data['chunk_id']
            add_to_audio_stack(tenant_id, chunk_id, audio_b64, translate_from, translate_to)
            #print("queue length: " + str(audio_stack.qsize()))
            logger.debug(f"Received chunk {chunk_id} with tenant_id {tenant_id}")
            response_data = {'chunk_id': chunk_id, 'tenant_id': tenant_id, 'status': 'processing'}
            #print("received chunk " + chunk_id + " with " + str(len(audio_b64)) + " bytes")
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.error("Invalid data in TranscribeView")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class GetTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('chunk_id', openapi.IN_QUERY, description="Chunk ID", type=openapi.TYPE_STRING),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Retrieve the transcript for a given chunk_id.
        If the chunk_id is not found, an empty transcript is returned.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        t = get_transcripts(tenant_id)
        if len(t) == 0:
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})
        else:
            sentences = request.GET.get('sentences', 'false') == 'true'
            if sentences: t = merge_and_split_transcripts(t)
            chunk_id = request.GET.get('chunk_id')
            if chunk_id in t:
                transcript_data = t.get(chunk_id, {})
                transcript = transcript_data.get('transcript', '')
                # Generate timestamp from chunk_id (it's a timestamp in milliseconds)
                timestamp = generate_timestamp(chunk_id)
                # Get language info
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
            else:
                return Response({'chunk_id': chunk_id, 'transcript': '', 'timestamp': '', 'language': ''})

@method_decorator(csrf_exempt, name='dispatch')
class GetFirstTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('from', openapi.IN_QUERY, description="Starting chunk ID", type=openapi.TYPE_STRING, default='0'),
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Retrieve the first transcript for a given tenant_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        t = get_transcripts(tenant_id)
        if len(t) == 0:
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})
        else:
            sentences = request.GET.get('sentences', 'false') == 'true'
            if sentences: t = merge_and_split_transcripts(t)
            fromid = request.GET.get('from', '0')
            sorted_keys = sorted(t.keys())
            first_chunk_id = next((k for k in sorted_keys if int(k) >= int(fromid)), None)
            if first_chunk_id:
                transcript_data = t[first_chunk_id]
                transcript = transcript_data.get('transcript', '')
                timestamp = generate_timestamp(first_chunk_id)
                language = transcript_data.get('translate_to', '')
                return Response({
                    'chunk_id': first_chunk_id,
                    'transcript': transcript,
                    'timestamp': timestamp,
                    'language': language,
                    'original': transcript_data.get('original', ''),
                    'translated': transcript_data.get('translated', False),
                    'translate_from': transcript_data.get('translate_from', ''),
                    'translate_to': transcript_data.get('translate_to', '')
                })
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})

@method_decorator(csrf_exempt, name='dispatch')
class PopFirstTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('from', openapi.IN_QUERY, description="Starting chunk ID", type=openapi.TYPE_STRING, default='0'),
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Retrieve and remove the first transcript for a given tenant_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        t = get_transcripts(tenant_id)
        if len(t) == 0:
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})
        else:
            sentences = request.GET.get('sentences', 'false') == 'true'
            if sentences: t = merge_and_split_transcripts(t)
            fromid = request.GET.get('from', '0')
            sorted_keys = sorted(t.keys())
            first_chunk_id = next((k for k in sorted_keys if int(k) >= int(fromid)), None)
            if first_chunk_id:
                transcript_data = t.pop(first_chunk_id, {})
                transcript = transcript_data.get('transcript', '')
                timestamp = generate_timestamp(first_chunk_id)
                language = transcript_data.get('translate_to', '')
                return Response({
                    'chunk_id': first_chunk_id,
                    'transcript': transcript,
                    'timestamp': timestamp,
                    'language': language,
                    'original': transcript_data.get('original', ''),
                    'translated': transcript_data.get('translated', False),
                    'translate_from': transcript_data.get('translate_from', ''),
                    'translate_to': transcript_data.get('translate_to', '')
                })
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})

@method_decorator(csrf_exempt, name='dispatch')
class GetLatestTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('until', openapi.IN_QUERY, description="End chunk ID", type=openapi.TYPE_STRING, default=str(int(time.time() * 1000)))
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Retrieve the latest transcript for a given tenant_id. Optionally translate it into another language.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        transcripts = get_transcripts(tenant_id)
        
        if len(transcripts) == 0:
            return Response({})
        else:
            untilid = request.GET.get('until', str(int(time.time() * 1000)))
            sorted_keys = sorted(transcripts.keys(), reverse=True)
            # remove all keys that are greater than untilid
            sorted_keys = [k for k in sorted_keys if int(k) <= int(untilid)]
            # now extract the first three keys from largest to smallest
            extracted_keys = sorted_keys[:4] if len(sorted_keys) > 3 else sorted_keys
            # from the transcripts dictionary, extract the transcripts for the extracted keys
            extracted_transcripts = {k: transcripts[k] for k in extracted_keys}
            # now sort the extracted transcripts by key again, now lowest to highest
            extracted_transcripts = {k: v for k, v in sorted(extracted_transcripts.items())}
            # Add timestamps and language info to each transcript
            result = {}
            for chunk_id, transcript_data in extracted_transcripts.items():
                timestamp = generate_timestamp(chunk_id)
                result[chunk_id] = {
                    'transcript': transcript_data.get('transcript', ''),
                    'timestamp': timestamp,
                    'language': transcript_data.get('translate_to', ''),
                    'original': transcript_data.get('original', ''),
                    'translated': transcript_data.get('translated', False),
                    'translate_from': transcript_data.get('translate_from', ''),
                    'translate_to': transcript_data.get('translate_to', '')
                }
            return Response(result)
            
@method_decorator(csrf_exempt, name='dispatch')
class PopLatestTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('until', openapi.IN_QUERY, description="End chunk ID", type=openapi.TYPE_STRING, default=str(int(time.time() * 1000))),
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Retrieve and remove the latest transcript for a given tenant_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        untilid = request.GET.get('until', str(int(time.time() * 1000)))
        sentences = request.GET.get('sentences', 'false') == 'true'
        t = get_transcripts(tenant_id)
        if sentences: t = merge_and_split_transcripts(t)
        sorted_keys = sorted(t.keys(), reverse=True)
        latest_chunk_id = next((k for k in sorted_keys if int(k) < int(untilid)), None)
        if latest_chunk_id in t:
            transcript_data = t.pop(latest_chunk_id, {})
            transcript = transcript_data.get('transcript', '')
            timestamp = generate_timestamp(latest_chunk_id)
            language = transcript_data.get('translate_to', '')
            return Response({
                'chunk_id': latest_chunk_id,
                'transcript': transcript,
                'timestamp': timestamp,
                'language': language,
                'original': transcript_data.get('original', ''),
                'translated': transcript_data.get('translated', False),
                'translate_from': transcript_data.get('translate_from', ''),
                'translate_to': transcript_data.get('translate_to', '')
            })
        else:
            return Response({'chunk_id': '-1', 'transcript': '', 'timestamp': '', 'language': ''})

@method_decorator(csrf_exempt, name='dispatch')
class DeleteTranscriptView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('chunk_id', openapi.IN_QUERY, description="Chunk ID", type=openapi.TYPE_STRING),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
        ],
        responses={200: TranscriptResponseSerializer}
    )
    def get(self, request):
        """
        Delete a transcript for a given tenant_id and chunk_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        chunk_id = request.GET.get('chunk_id')
        sentences = request.GET.get('sentences', 'false') == 'true'
        t = get_transcripts(tenant_id)
        if sentences: t = merge_and_split_transcripts(t)
        if chunk_id in t:
            transcript_data = t.pop(chunk_id)
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
        else:
            return Response({'chunk_id': chunk_id, 'transcript': '', 'timestamp': '', 'language': ''})

@method_decorator(csrf_exempt, name='dispatch')
class ListTranscriptsView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('from', openapi.IN_QUERY, description="Starting chunk ID", type=openapi.TYPE_STRING, default='0'),
            openapi.Parameter('until', openapi.IN_QUERY, description="End chunk ID", type=openapi.TYPE_STRING, default=str(int(time.time() * 1000))),
        ],
        responses={200: ListTranscriptsResponseSerializer}
    )
    def get(self, request):
        """
        List all transcripts for a given tenant_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        fromid = request.GET.get('from', '0')
        untilid = request.GET.get('until', str(int(time.time() * 1000)))
        sentences = request.GET.get('sentences', 'false') == 'true'
        t = get_transcripts(tenant_id)
        if sentences: t = merge_and_split_transcripts(t)
        transcripts = {k: v for k, v in t.items() if int(fromid) <= int(k) <= int(untilid)}
        # Build response with timestamps and language
        result = []
        for chunk_id, transcript_data in sorted(transcripts.items()):
            timestamp = generate_timestamp(chunk_id)
            result.append({
                'chunk_id': chunk_id,
                'transcript': transcript_data.get('transcript', ''),
                'timestamp': timestamp,
                'language': transcript_data.get('translate_to', ''),
                'original': transcript_data.get('original', ''),
                'translated': transcript_data.get('translated', False),
                'translate_from': transcript_data.get('translate_from', ''),
                'translate_to': transcript_data.get('translate_to', '')
            })
        return Response({'transcripts': result})

@method_decorator(csrf_exempt, name='dispatch')
class TranscriptsSizeView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('tenant_id', openapi.IN_QUERY, description="Tenant ID", type=openapi.TYPE_STRING, default='0000'),
            openapi.Parameter('sentences', openapi.IN_QUERY, description="Merge and split transcripts into sentences", type=openapi.TYPE_BOOLEAN, default=False),
            openapi.Parameter('from', openapi.IN_QUERY, description="Starting chunk ID", type=openapi.TYPE_STRING, default='0'),
            openapi.Parameter('until', openapi.IN_QUERY, description="End chunk ID", type=openapi.TYPE_STRING, default=str(int(time.time() * 1000))),
        ],
        responses={200: SizeResponseSerializer}
    )
    def get(self, request):
        """
        Get the size of the transcripts for a given tenant_id.
        """
        tenant_id = request.GET.get('tenant_id', '0000')
        t = get_transcripts(tenant_id)
        sentences = request.GET.get('sentences', 'false') == 'true'
        if sentences: t = merge_and_split_transcripts(t)
        fromid = request.GET.get('from', '0')
        untilid = request.GET.get('until', str(int(time.time() * 1000)))
        transcripts = {k: v for k, v in t.items() if k.isdigit() and int(fromid) <= int(k) <= int(untilid)}
        return Response({'size': len(transcripts)})
    
@method_decorator(csrf_exempt, name='dispatch')
class ServeRootStaticFileView(APIView):
    """
    Serve static files directly from the root path via an API endpoint.
    Optionally apply Handlebars.js-like transformations using PyBars.
    """

    def get(self, request, file_name=None):
        if not file_name or file_name.strip() == '':
            file_name = 'index.html'

        candidates = []
        static_files = getattr(settings, 'STATIC_FILES', None)
        if static_files:
            candidates.append(Path(static_files))

        static_dirs = getattr(settings, 'STATICFILES_DIRS', None)
        if static_dirs:
            for p in static_dirs:
                candidates.append(Path(p))

        base_dir = getattr(settings, 'BASE_DIR', None)
        if base_dir:
            candidates.append(Path(base_dir) / 'static')

        candidates = [p for p in candidates if p.exists() and p.is_dir()]

        if not candidates:
            raise Http404('Static directory not found.')

        requested_file = None
        for dir_path in candidates:
            try:
                dir_path_str = str(dir_path)
                candidate = dir_path / file_name
                candidate_str = str(candidate)

                # Prevent path traversal attacks
                resolved = Path(candidate_str).resolve()
                dir_resolved = Path(dir_path_str).resolve()
                if not (resolved == dir_resolved or dir_resolved in resolved.parents):
                    continue

                if resolved.is_dir():
                    resolved = resolved / 'index.html'

                if resolved.exists() and resolved.is_file():
                    requested_file = resolved
                    logger.info(f'Serving static file: {resolved}')
                    break
            except (OSError, RuntimeError) as e:
                logger.warning(f'Error accessing static path {dir_path}: {e}')
                continue

        if not requested_file:
            # Fall back to the classic orbiter UI if index.html is missing in STATIC_FILES
            if file_name == 'index.html':
                fallback = Path(settings.BASE_DIR) / 'orbiter-bootstrap3' / 'main.html'
                if fallback.exists() and fallback.is_file():
                    requested_file = fallback
                else:
                    raise Http404(f"File '{file_name}' not found.")
            else:
                raise Http404(f"File '{file_name}' not found.")

        guessed_type, _ = mimetypes.guess_type(str(requested_file))

        if guessed_type and guessed_type.startswith('text'):
            with requested_file.open('r', encoding='utf-8') as f:
                file_content = f.read()

            if request.GET.get('transform', 'false').lower() == 'true':
                context = {
                    'title': 'Dynamic Page',
                    'content': 'This content was dynamically injected.',
                }
                compiler = pybars.Compiler()
                template = compiler.compile(file_content)
                file_content = template(context)

            return HttpResponse(file_content, content_type=guessed_type or 'text/plain')

        with requested_file.open('rb') as f:
            file_content = f.read()
        return HttpResponse(file_content, content_type=guessed_type or 'application/octet-stream')
        
        
