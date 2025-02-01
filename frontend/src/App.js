// frontend/src/App.js
import React, { useState } from 'react';
import axios from 'axios';
import './App.css'; // For minimal, centered styling

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [metadata, setMetadata] = useState(null);
  const [transcriptionStatus, setTranscriptionStatus] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const uploadFile = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await axios.post(
        "/upload",
        formData,
        {
          onUploadProgress: progressEvent => {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
          },
          headers: {
            "Content-Type": "multipart/form-data"
          }
        }
      );
      setMetadata(response.data);
    } catch (error) {
      console.error("Upload error", error);
    }
  };

  const triggerTranscription = async () => {
    if (!metadata) return;
    try {
      await axios.post("/transcribe", {
        file_id: metadata.file_id,
        filename: metadata.filename
      });
      setTranscriptionStatus("pending");
      pollStatus(metadata.file_id);
    } catch (error) {
      console.error("Error triggering transcription", error);
    }
  };

  const pollStatus = async (file_id) => {
    const interval = setInterval(async () => {
      const res = await axios.get("/status", { params: { file_id } });
      if (res.data.status === "complete") {
        clearInterval(interval);
        // Automatically download the transcript
        window.location.href = res.data.download_url;
      }
    }, 5000); // Poll every 5 seconds
  };

  return (
    <div className="App">
      <h1>Audio Transcription</h1>
      <input type="file" accept="audio/*" onChange={handleFileChange} />
      <button onClick={uploadFile}>Upload Audio</button>
      {uploadProgress > 0 && uploadProgress < 100 && (
        <div>Uploading: {uploadProgress}%</div>
      )}
      {metadata && (
        <div>
          <p>Audio Length: {metadata.audio_length_seconds.toFixed(2)} seconds</p>
          <p>Estimated Transcription Time: {metadata.estimated_transcription_time_seconds.toFixed(2)} seconds</p>
          <button onClick={triggerTranscription}>Transcribe</button>
        </div>
      )}
      {transcriptionStatus && <p>Transcription in progress...</p>}
    </div>
  );
}

export default App;
