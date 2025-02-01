# backend/worker.py
import os
import json
import io
from fastapi import FastAPI, Request, HTTPException
from google.cloud import storage, speech_v1p1beta1 as speech

app = FastAPI()

PROJECT_ID = os.environ.get("GCP_PROJECT", "audio-trad1")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "audio-trad1-audio-files")
TRANSCRIPT_FOLDER = os.environ.get("TRANSCRIPT_FOLDER", "transcripts")

storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(AUDIO_BUCKET)
speech_client = speech.SpeechClient()

@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    """
    Endpoint for receiving Pub/Sub push messages.
    The message payload should include: file_id, filename, bucket, transcript_folder.
    """
    envelope = await request.json()
    if "message" not in envelope:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")

    message_data = envelope["message"].get("data")
    if not message_data:
        raise HTTPException(status_code=400, detail="No data in Pub/Sub message")

    # Decode the message payload
    payload = json.loads(message_data.encode("utf-8").decode("unicode_escape"))
    file_id = payload["file_id"]
    filename = payload["filename"]
    transcript_filename = f"{TRANSCRIPT_FOLDER}/{file_id}.txt"

    # Get the audio file URI from Cloud Storage
    gcs_uri = f"gs://{AUDIO_BUCKET}/{filename}"

    # Configure the asynchronous recognition request
    audio = speech.RecognitionAudio(uri=gcs_uri)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )
    # Start asynchronous transcription (for long audio, use long_running_recognize)
    operation = speech_client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=600)  # adjust timeout as needed

    # Combine the transcription results
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript + "\n"

    # Save transcript to Cloud Storage
    blob = bucket.blob(transcript_filename)
    blob.upload_from_string(transcript, content_type="text/plain")

    return {"status": "transcription complete", "transcript_file": transcript_filename}
