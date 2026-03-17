"""
Video Processor Module
Handles video thumbnail generation and processing with comprehensive error handling
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import os

logger = logging.getLogger(__name__)

# Try to import cv2
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available - thumbnail generation disabled")


class VideoProcessor:
    """Handles video processing tasks like thumbnail generation"""

    def __init__(self, thumbnail_dir: Path):
        """
        Initialize video processor.

        Args:
            thumbnail_dir: Directory to store generated thumbnails
        """
        self.thumbnail_dir = thumbnail_dir
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(
            f"VideoProcessor initialized (ffmpeg: {self.ffmpeg_available}, cv2: {CV2_AVAILABLE})"
        )

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if ffmpeg is available"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def generate_thumbnail(
        self,
        video_path: Path,
        timestamp_pct: float = 0.1,
        size: Tuple[int, int] = (320, 240),
    ) -> Optional[Path]:
        """
        Generate a thumbnail from a video file.

        Args:
            video_path: Path to the video file
            timestamp_pct: Percentage into the video to capture (0.0-1.0)
            size: Thumbnail size (width, height)

        Returns:
            Path to generated thumbnail or None on failure
        """
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        thumbnail_path = self.thumbnail_dir / f"{video_path.stem}_thumb.jpg"

        try:
            if self.ffmpeg_available:
                return self._generate_thumbnail_ffmpeg(
                    video_path, thumbnail_path, timestamp_pct, size
                )
            elif CV2_AVAILABLE:
                return self._generate_thumbnail_cv2(
                    video_path, thumbnail_path, timestamp_pct, size
                )
            else:
                logger.warning("No thumbnail generation method available")
                return None

        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return None

    def _generate_thumbnail_ffmpeg(
        self,
        video_path: Path,
        thumbnail_path: Path,
        timestamp_pct: float,
        size: Tuple[int, int],
    ) -> Optional[Path]:
        """Generate thumbnail using ffmpeg"""
        try:
            # Get video duration first
            duration = self._get_video_duration_ffmpeg(video_path)
            if duration is None:
                logger.warning(
                    f"Could not get duration for {video_path}, using 1 second offset"
                )
                timestamp = 1.0
            else:
                timestamp = duration * timestamp_pct

            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-vf",
                f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease",
                str(thumbnail_path),
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=30)

            if result.returncode == 0 and thumbnail_path.exists():
                logger.info(f"Generated thumbnail: {thumbnail_path}")
                return thumbnail_path
            else:
                stderr = (
                    result.stderr.decode()[:500] if result.stderr else "Unknown error"
                )
                logger.error(f"FFmpeg thumbnail failed: {stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg thumbnail generation timed out")
            return None
        except Exception as e:
            logger.error(f"FFmpeg thumbnail error: {e}")
            return None

    def _generate_thumbnail_cv2(
        self,
        video_path: Path,
        thumbnail_path: Path,
        timestamp_pct: float,
        size: Tuple[int, int],
    ) -> Optional[Path]:
        """Generate thumbnail using OpenCV"""
        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return None

            # Get total frames
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                logger.warning(f"Could not determine frame count for {video_path}")
                target_frame = 0
            else:
                target_frame = int(total_frames * timestamp_pct)

            # Seek to target frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

            # Read frame
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error(f"Failed to read frame from {video_path}")
                return None

            # Resize
            frame_resized = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

            # Save
            cv2.imwrite(
                str(thumbnail_path), frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85]
            )

            if thumbnail_path.exists():
                logger.info(f"Generated thumbnail: {thumbnail_path}")
                return thumbnail_path

            return None

        except Exception as e:
            logger.error(f"OpenCV thumbnail error: {e}")
            return None
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def _get_video_duration_ffmpeg(self, video_path: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode == 0:
                return float(result.stdout.decode().strip())

        except Exception:
            pass

        return None

    def get_video_info(self, video_path: Path) -> dict:
        """Get video information"""
        info = {
            "exists": video_path.exists(),
            "size": video_path.stat().st_size if video_path.exists() else 0,
            "duration": None,
            "width": None,
            "height": None,
            "fps": None,
        }

        if not video_path.exists():
            return info

        # Try ffprobe first
        if self.ffmpeg_available:
            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate,duration",
                    "-of",
                    "json",
                    str(video_path),
                ]

                result = subprocess.run(cmd, capture_output=True, timeout=10)

                if result.returncode == 0:
                    import json

                    data = json.loads(result.stdout.decode())
                    if data.get("streams"):
                        stream = data["streams"][0]
                        info["width"] = stream.get("width")
                        info["height"] = stream.get("height")
                        info["duration"] = float(stream.get("duration", 0))

                        # Parse frame rate
                        fps_str = stream.get("r_frame_rate", "0/1")
                        if "/" in fps_str:
                            num, den = fps_str.split("/")
                            info["fps"] = (
                                float(num) / float(den) if float(den) > 0 else 0
                            )

                        return info

            except Exception as e:
                logger.debug(f"ffprobe failed: {e}")

        # Fallback to OpenCV
        if CV2_AVAILABLE:
            try:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    info["fps"] = cap.get(cv2.CAP_PROP_FPS)
                    info["duration"] = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(
                        info["fps"], 1
                    )
                    cap.release()

            except Exception as e:
                logger.debug(f"OpenCV video info failed: {e}")

        return info
