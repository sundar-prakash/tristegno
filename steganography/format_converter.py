"""
Audio/Video format conversion utilities
Handles conversion of various formats to WAV (audio) and MP4 (video) for steganography
"""
import os
import subprocess
import wave

def has_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def convert_audio_to_wav(input_path, output_path):
    """Convert audio file to WAV format using ffmpeg"""
    if not has_ffmpeg():
        raise RuntimeError("FFmpeg is required for audio conversion. Please install it from https://ffmpeg.org/")
    
    try:
        # Convert to WAV with specific parameters for steganography
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '44100',  # 44.1kHz sample rate
            '-ac', '2',  # Stereo
            '-y',  # Overwrite output file
            output_path
        ], capture_output=True, check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Audio conversion failed: {e.stderr}")

def convert_video_to_mp4(input_path, output_path):
    """Convert video file to MP4 format using ffmpeg"""
    if not has_ffmpeg():
        raise RuntimeError("FFmpeg is required for video conversion. Please install it from https://ffmpeg.org/")
    
    try:
        # Convert to MP4 with H.264 codec
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',  # H.264 video codec
            '-preset', 'medium',  # Balance between speed and quality
            '-crf', '23',  # Quality level (lower = better quality)
            '-c:a', 'aac',  # AAC audio codec
            '-b:a', '128k',  # Audio bitrate
            '-y',  # Overwrite output file
            output_path
        ], capture_output=True, check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Video conversion failed: {e.stderr}")
