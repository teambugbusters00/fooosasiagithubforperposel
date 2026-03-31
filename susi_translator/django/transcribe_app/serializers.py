# transcribe_app/serializers.py
# (C) Michael Peter Christen 2024
# Licensed under Apache License Version 2.0

from rest_framework import serializers

class TranscribeInputSerializer(serializers.Serializer):
    audio_b64 = serializers.CharField(required=True, help_text='Base64 encoded audio data')
    chunk_id = serializers.CharField(required=True, help_text='ID of the audio chunk')
    tenant_id = serializers.CharField(required=False, default='0000', help_text='Tenant ID')
    translate_from = serializers.CharField(required=False, default='translate_from', help_text='Source Language')
    translate_to = serializers.CharField(required=False, default='translate_to', help_text='Target Language')

class TranscribeResponseSerializer(serializers.Serializer):
    chunk_id = serializers.CharField(help_text='ID of the audio chunk')
    tenant_id = serializers.CharField(help_text='Tenant ID')
    status = serializers.CharField(help_text='Processing flag')

class TranscriptResponseSerializer(serializers.Serializer):
    chunk_id = serializers.CharField(help_text='ID of the audio chunk')
    transcript = serializers.CharField(help_text='The transcribed text')
    timestamp = serializers.CharField(help_text='Timestamp of the transcript', required=False)
    language = serializers.CharField(help_text='Language of the transcript', required=False)
    original = serializers.CharField(help_text='Original transcript before translation', required=False)
    translated = serializers.BooleanField(help_text='Whether the transcript is translated', required=False)
    translate_from = serializers.CharField(help_text='Source language for translation', required=False)
    translate_to = serializers.CharField(help_text='Target language for translation', required=False)

class ListTranscriptsResponseSerializer(serializers.Serializer):
    transcripts = TranscriptResponseSerializer(many=True)

class SizeResponseSerializer(serializers.Serializer):
    size = serializers.IntegerField(help_text='The number of transcripts')
