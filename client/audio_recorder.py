"""
Audio Recorder Module
Handles audio recording with thread safety and comprehensive error handling
"""

import logging
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import pyaudio with graceful fallback
try:
    import pyaudio

    AUDIO_AVAILABLE = True
    logger.info("Audio recording available (pyaudio)")
except ImportError:
    AUDIO_AVAILABLE = False
    logger.warning("pyaudio not available - audio recording disabled")


class AudioRecorder:
    """Handles audio recording with thread safety and error handling"""

    CHUNK = 1024
    CHANNELS = 1
    RATE = 44100

    def __init__(self, output_dir: Path, device_index: int = -1):
        """
        Initialize audio recorder.

        Args:
            output_dir: Directory to save audio files
            device_index: Audio device index (-1 for default)
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.device_index = device_index

        self.audio = None
        self.stream = None
        self.frames: List[bytes] = []
        self.is_recording = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._error_count = 0
        self._max_errors = 10
        self._stop_event = threading.Event()

        self.FORMAT = None
        if AUDIO_AVAILABLE:
            self.FORMAT = pyaudio.paInt16
            self._init_audio()

    def _init_audio(self) -> bool:
        """Initialize PyAudio with error handling"""
        if not AUDIO_AVAILABLE:
            return False

        try:
            if self.audio is None:
                self.audio = pyaudio.PyAudio()
            logger.info("Audio system initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    @staticmethod
    def is_available() -> bool:
        """Check if audio recording is available"""
        return AUDIO_AVAILABLE

    @staticmethod
    def list_devices() -> List[Dict[str, Any]]:
        """List available audio input devices"""
        if not AUDIO_AVAILABLE:
            return []

        devices = []
        audio = None
        try:
            audio = pyaudio.PyAudio()
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    devices.append(
                        {
                            "index": i,
                            "name": info["name"],
                            "channels": info["maxInputChannels"],
                            "sample_rate": int(info["defaultSampleRate"]),
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to list audio devices: {e}")
        finally:
            if audio:
                try:
                    audio.terminate()
                except Exception:
                    pass
        return devices

    def start(self) -> bool:
        """Start audio recording with comprehensive error handling"""
        if not AUDIO_AVAILABLE:
            logger.warning("Audio recording not available")
            return False

        with self._lock:
            if self.is_recording:
                logger.debug("Audio recording already in progress")
                return True

            try:
                if not self._init_audio():
                    return False

                # Determine device to use
                device_idx = self.device_index if self.device_index >= 0 else None

                # Get device info for proper configuration
                try:
                    if device_idx is not None:
                        dev_info = self.audio.get_device_info_by_index(device_idx)
                        channels = min(self.CHANNELS, int(dev_info["maxInputChannels"]))
                        rate = int(dev_info["defaultSampleRate"])
                    else:
                        channels = self.CHANNELS
                        rate = self.RATE
                except Exception:
                    channels = self.CHANNELS
                    rate = self.RATE

                # Open stream
                self.stream = self.audio.open(
                    format=self.FORMAT,
                    channels=channels,
                    rate=rate,
                    input=True,
                    input_device_index=device_idx,
                    frames_per_buffer=self.CHUNK,
                    exception_on_overflow=False,
                )

                self.frames = []
                self.is_recording = True
                self._error_count = 0
                self._stop_event.clear()

                # Start recording thread
                self._thread = threading.Thread(target=self._record_loop, daemon=True)
                self._thread.start()

                logger.info(
                    f"Audio recording started (device: {device_idx}, rate: {rate})"
                )
                return True

            except OSError as e:
                logger.error(f"OS error starting audio: {e}")
                self._cleanup()
                return False
            except Exception as e:
                logger.error(f"Failed to start audio recording: {e}")
                self._cleanup()
                return False

    def _record_loop(self):
        """Audio recording loop with error handling"""
        while self.is_recording and not self._stop_event.is_set():
            try:
                if self.stream and self.stream.is_active():
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    with self._lock:
                        self.frames.append(data)
            except OSError as e:
                error_str = str(e).lower()
                if "input overflowed" in error_str or "overflow" in error_str:
                    logger.debug("Audio buffer overflow, continuing...")
                    continue
                logger.error(f"Audio read error: {e}")
                self._error_count += 1
            except Exception as e:
                logger.error(f"Audio recording error: {e}")
                self._error_count += 1

            if self._error_count >= self._max_errors:
                logger.error("Too many audio errors, stopping recording")
                self.is_recording = False
                break

    def stop(self) -> Optional[Path]:
        """Stop recording and save to file"""
        with self._lock:
            self.is_recording = False
            self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2)

        output_path = None
        if self.frames:
            try:
                output_path = self._save_wav()
            except Exception as e:
                logger.error(f"Failed to save audio: {e}")

        self._cleanup()
        return output_path

    def pause(self) -> bool:
        """Pause audio recording"""
        with self._lock:
            if self.stream and self.is_recording:
                try:
                    self.stream.stop_stream()
                    logger.info("Audio recording paused")
                    return True
                except Exception as e:
                    logger.error(f"Failed to pause audio: {e}")
        return False

    def resume(self) -> bool:
        """Resume audio recording"""
        with self._lock:
            if self.stream and self.is_recording:
                try:
                    self.stream.start_stream()
                    logger.info("Audio recording resumed")
                    return True
                except Exception as e:
                    logger.error(f"Failed to resume audio: {e}")
        return False

    def _save_wav(self) -> Optional[Path]:
        """Save recorded audio to WAV file"""
        if not self.frames:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"audio_{timestamp}.wav"

        try:
            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                if self.audio:
                    wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                else:
                    wf.setsampwidth(2)  # Default for paInt16
                wf.setframerate(self.RATE)
                wf.writeframes(b"".join(self.frames))

            logger.info(f"Audio saved: {output_path} ({len(self.frames)} frames)")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save WAV: {e}")
            return None

    def _cleanup(self):
        """Clean up audio resources safely"""
        try:
            if self.stream:
                try:
                    self.stream.stop_stream()
                except Exception:
                    pass
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """Get audio recorder status"""
        return {
            "available": AUDIO_AVAILABLE,
            "recording": self.is_recording,
            "device_index": self.device_index,
            "frames_buffered": len(self.frames),
            "error_count": self._error_count,
        }

    def __del__(self):
        """Cleanup on destruction"""
        self._cleanup()
        if self.audio:
            try:
                self.audio.terminate()
            except Exception:
                pass
