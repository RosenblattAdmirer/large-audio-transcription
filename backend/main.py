# backend/main.py
import os
import uuid
import io
import asyncio

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from google.cloud import storage, pubsub_v1
from pydub import AudioSegment  # requires ffmpeg installed in the container

app = FastAPI()

# Environment variables (set these in Cloud Run or via .env in development)
PROJECT_ID = os.environ.get("GCP_PROJECT", "audio-trad1")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "audio-trad1-audio-files")
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", "audio-transcription-topic")
TRANSCRIPT_FOLDER = os.environ.get("TRANSCRIPT_FOLDER", "transcripts")

# Initialize GCP clients
storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(AUDIO_BUCKET)
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)


def get_audio_duration(file_bytes: bytes) -> float:
    """Return duration (in seconds) of the audio file."""
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))
    return len(audio) / 1000.0  # duration in seconds


@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    try:
        file_contents = await file.read()
        # Compute audio duration
        duration = get_audio_duration(file_contents)
        # Estimate transcription time (e.g., 2x real time as a rough approximation)
        estimated_transcription_time = duration * 2

        # Generate a unique file id
        file_id = str(uuid.uuid4())
        audio_filename = f"audios/{file_id}_{file.filename}"
        blob = bucket.blob(audio_filename)
        blob.upload_from_string(file_contents, content_type=file.content_type)

        # Return metadata so that frontend can show info and later trigger transcription
        return JSONResponse({
            "file_id": file_id,
            "filename": audio_filename,
            "audio_length_seconds": duration,
            "estimated_transcription_time_seconds": estimated_transcription_time
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
async def transcribe_audio(file_id: str, filename: str):
    """
    Trigger the transcription process by publishing a message to Pub/Sub.
    The payload includes the file_id and filename.
    """
    try:
        message = {
            "file_id": file_id,
            "filename": filename,
            "bucket": AUDIO_BUCKET,
            "transcript_folder": TRANSCRIPT_FOLDER
        }
        # Publish the message (the publisher accepts bytes)
        future = publisher.publish(topic_path, data=str(message).encode("utf-8"))
        future.result()  # wait for publication
        return JSONResponse({"status": "transcription triggered", "file_id": file_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def check_status(file_id: str):
    """
    Check if the transcript file exists. If so, return a download URL.
    For simplicity, we generate a signed URL.
    """
    transcript_filename = f"{TRANSCRIPT_FOLDER}/{file_id}.txt"
    blob = bucket.blob(transcript_filename)
    if blob.exists():
        # Generate a signed URL valid for 10 minutes.
        download_url = blob.generate_signed_url(expiration=600)
        return JSONResponse({"status": "complete", "download_url": download_url})
    else:
        return JSONResponse({"status": "pending"})


# Optionally, you can have an endpoint to force-download (streaming)
@app.get("/download")
async def download_transcript(file_id: str):
    transcript_filename = f"{TRANSCRIPT_FOLDER}/{file_id}.txt"
    blob = bucket.blob(transcript_filename)
    if blob.exists():
        tmp_file = f"/tmp/{file_id}.txt"
        blob.download_to_filename(tmp_file)
        return FileResponse(tmp_file, filename=f"{file_id}.txt")
    else:
        raise HTTPException(status_code=404, detail="Transcript not ready")
