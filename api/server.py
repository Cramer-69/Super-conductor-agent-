"""
FastAPI server for voice-enabled conductor agent.
Provides REST API and web interface for mobile access.
"""

import os
import sys
import uuid
from pathlib import Path

# Add conductor_agent directory to sys.path so bare internal imports work
_pkg_dir = str(Path(__file__).resolve().parent.parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from conductor.agent import ConductorAgent
from voice.voice_processor import get_voice_processor
from utils.logger import logger
from config.settings import settings

# Initialize FastAPI app
app = FastAPI(
    title="Conductor Voice Agent",
    description="Voice-enabled AI assistant with persistent memory",
    version="1.0.0"
)

# Add CORS middleware for mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for mobile
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services (lazy initialization to avoid startup crashes)
conductor = None
voice_processor = None

def _is_cloud() -> bool:
    """True on Cloud Run / Render / Railway / Heroku — skip ChromaDB."""
    return any(
        os.getenv(v)
        for v in ("K_SERVICE", "RENDER", "RAILWAY", "HEROKU")
    )


def get_conductor():
    """Lazy initialization of conductor agent."""
    global conductor
    if conductor is None:
        # Use minimal conductor in cloud environments (no ChromaDB)
        is_cloud = (
            os.getenv("K_SERVICE")  # Cloud Run
            or os.getenv("RENDER")
            or os.getenv("RAILWAY")
            or os.getenv("HEROKU")
        )
        
        try:
            if is_cloud:
                from conductor.minimal import MinimalConductor
                conductor = MinimalConductor()
                logger.info("Using minimal conductor (cloud mode - no memory)")
            else:
                conductor = ConductorAgent()
                logger.info("Using full conductor (local mode - with memory)")
        except Exception as e:
            logger.error(f"Failed to initialize conductor: {e}")
            # Ultimate fallback - minimal conductor
            try:
                from conductor.minimal import MinimalConductor
                conductor = MinimalConductor()
                logger.info("Fallback to minimal conductor due to error")
            except:
                raise ValueError(f"Could not initialize any conductor: {e}")
    return conductor

def get_voice():
    """Lazy initialization of voice processor."""
    global voice_processor
    if voice_processor is None:
        voice_processor = get_voice_processor()
    return voice_processor

# Create temp directory for audio files
TEMP_DIR = Path("temp_audio")
TEMP_DIR.mkdir(exist_ok=True)


# Request/Response Models
class ChatRequest(BaseModel):
    query: str
    platform_filter: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: list
    audio_url: Optional[str] = None


class VoiceSettings(BaseModel):
    voice: str = "nova"


# In-memory voice settings (could be persisted later)
current_voice_settings = VoiceSettings()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web interface."""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return """
        <html>
            <body>
                <h1>Conductor Voice Agent</h1>
                <p>Web interface will be available soon.</p>
                <p>API is running. Try POST /api/chat</p>
            </body>
        </html>
        """


@app.on_event("startup")
async def _startup_log_config():
    """Log API-key configuration so missing keys are obvious in cloud logs."""
    providers = settings.configured_providers()
    if providers:
        logger.info(f"Configured LLM providers: {', '.join(providers)}")
    else:
        logger.warning(
            "No LLM API key configured. The /api/chat endpoint will fail "
            "until OPENAI_API_KEY (or another provider key) is set. "
            "See README -> Deploy."
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    providers = settings.configured_providers()
    return {
        "status": "healthy",
        "service": "conductor-voice-agent",
        "version": "1.0.0",
        "mode": "minimal" if _is_cloud() else "full",
        "providers": providers,
        "api_keys_configured": bool(providers),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Text-based chat endpoint.
    
    Args:
        request: Chat request with query and optional platform filter
        
    Returns:
        Chat response with answer and sources
    """
    try:
        logger.info(f"Chat request: {request.query[:100]}...")
        
        result = get_conductor().chat(
            query=request.query,
            platform_filter=request.platform_filter
        )
        
        return ChatResponse(
            response=result['response'],
            sources=result['sources']
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...)):
    """
    Voice-based chat endpoint.
    Accepts audio input, transcribes it, generates response, and returns audio.
    
    Args:
        audio: Audio file (webm, mp3, wav, etc.)
        
    Returns:
        JSON with transcription, response text, and URL to audio response
    """
    try:
        # Save uploaded audio temporarily
        audio_id = str(uuid.uuid4())
        input_path = TEMP_DIR / f"input_{audio_id}.webm"
        
        with open(input_path, "wb") as f:
            content = await audio.read()
            f.write(content)
        
        logger.info(f"Received audio file: {input_path}")
        
        # Transcribe audio to text
        vp = get_voice()
        transcription = await vp.transcribe_audio(input_path)
        logger.info(f"Transcription: {transcription}")
        
        # Get response from conductor
        result = get_conductor().chat(query=transcription)
        response_text = result['response']
        
        # Synthesize speech from response
        output_path = TEMP_DIR / f"output_{audio_id}.mp3"
        await vp.synthesize_speech(
            text=response_text,
            output_path=output_path,
            voice=current_voice_settings.voice
        )
        
        # Clean up input file
        input_path.unlink()
        
        return {
            "transcription": transcription,
            "response": response_text,
            "sources": result['sources'],
            "audio_url": f"/api/audio/{output_path.name}"
        }
        
    except Exception as e:
        logger.error(f"Error in voice chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    """
    Serve generated audio file.
    
    Args:
        filename: Name of audio file
        
    Returns:
        Audio file
    """
    file_path = TEMP_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Transcribe audio to text only.
    
    Args:
        audio: Audio file
        
    Returns:
        Transcribed text
    """
    try:
        # Save temporarily
        audio_id = str(uuid.uuid4())
        temp_path = TEMP_DIR / f"temp_{audio_id}.webm"
        
        with open(temp_path, "wb") as f:
            content = await audio.read()
            f.write(content)
        
        # Transcribe
        transcription = await voice_processor.transcribe_audio(temp_path)
        
        # Clean up
        temp_path.unlink()
        
        return {"transcription": transcription}
        
    except Exception as e:
        logger.error(f"Error in transcribe endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/synthesize")
async def synthesize(text: str, voice: Optional[str] = None):
    """
    Synthesize speech from text.
    
    Args:
        text: Text to convert to speech
        voice: Optional voice to use
        
    Returns:
        URL to audio file
    """
    try:
        audio_id = str(uuid.uuid4())
        output_path = TEMP_DIR / f"synth_{audio_id}.mp3"
        
        await voice_processor.synthesize_speech(
            text=text,
            output_path=output_path,
            voice=voice or current_voice_settings.voice
        )
        
        return {"audio_url": f"/api/audio/{output_path.name}"}
        
    except Exception as e:
        logger.error(f"Error in synthesize endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voices")
async def get_voices():
    """Get available TTS voices."""
    return {"voices": voice_processor.get_available_voices()}


@app.post("/api/settings/voice")
async def set_voice(settings: VoiceSettings):
    """Update voice settings."""
    current_voice_settings.voice = settings.voice
    return {"voice": current_voice_settings.voice}


@app.get("/api/settings/voice")
async def get_voice():
    """Get current voice settings."""
    return {"voice": current_voice_settings.voice}


# Mount static files (will create later)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    
    logger.info(f"Starting Conductor Voice Agent on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
