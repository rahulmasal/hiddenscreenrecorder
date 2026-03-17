"""
Video Compressor Module
Handles video compression using ffmpeg or OpenCV fallback with comprehensive error handling
"""

import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional

import cv2

logger = logging.getLogger(__name__)


class VideoCompressor:
    """Handles video compression using ffmpeg or OpenCV fallback"""

    QUALITY_CRF = {"low": 28, "medium": 23, "high": 18}

    def __init__(self, quality: str = "medium"):
        """
        Initialize video compressor.

        Args:
            quality: Compression quality (low, medium, high)
        """
        self.quality = quality
        self.ffmpeg_available = self._check_ffmpeg()
        logger.info(f"VideoCompressor initialized (ffmpeg: {self.ffmpeg_available})")

    @staticmethod
    def _check_ffmpeg() -> bool:
        """Check if ffmpeg is available on the system"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False

    def compress(
        self, input_path: Path, output_path: Optional[Path] = None
    ) -> Tuple[bool, Optional[Path]]:
        """
        Compress video file with comprehensive error handling.

        Args:
            input_path: Path to input video file
            output_path: Path for output file (optional, defaults to .compressed.mp4)

        Returns:
            Tuple of (success, output_path)
        """
        if output_path is None:
            output_path = input_path.with_suffix(".compressed.mp4")

        try:
            if not input_path.exists():
                logger.error(f"Input file does not exist: {input_path}")
                return False, None

            if self.ffmpeg_available:
                return self._compress_ffmpeg(input_path, output_path)
            else:
                return self._compress_opencv(input_path, output_path)

        except Exception as e:
            logger.error(f"Video compression failed: {e}")
            return False, None

    def _compress_ffmpeg(
        self, input_path: Path, output_path: Path
    ) -> Tuple[bool, Optional[Path]]:
        """Compress using ffmpeg with error handling"""
        try:
            crf = self.QUALITY_CRF.get(self.quality, 23)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-c:v",
                "libx264",
                "-crf",
                str(crf),
                "-preset",
                "fast",
                "-movflags",
                "+faststart",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, timeout=300)

            if result.returncode == 0 and output_path.exists():
                original_size = input_path.stat().st_size
                compressed_size = output_path.stat().st_size
                savings = (
                    (1 - compressed_size / original_size) * 100
                    if original_size > 0
                    else 0
                )
                logger.info(
                    f"FFmpeg compression: {original_size} -> {compressed_size} bytes ({savings:.1f}% saved)"
                )
                return True, output_path
            else:
                stderr = (
                    result.stderr.decode()[:500] if result.stderr else "Unknown error"
                )
                logger.error(f"FFmpeg failed: {stderr}")
                return False, None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg compression timed out")
            return False, None
        except Exception as e:
            logger.error(f"FFmpeg compression error: {e}")
            return False, None

    def _compress_opencv(
        self, input_path: Path, output_path: Path
    ) -> Tuple[bool, Optional[Path]]:
        """Fallback compression using OpenCV re-encoding"""
        cap = None
        writer = None
        try:
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                logger.error(f"Failed to open video for compression: {input_path}")
                return False, None

            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 10
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if width <= 0 or height <= 0:
                logger.error("Invalid video dimensions")
                return False, None

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

            if not writer.isOpened():
                logger.error("Failed to create compressed video writer")
                return False, None

            quality_map = {"low": 50, "medium": 70, "high": 85}
            quality = quality_map.get(self.quality, 70)

            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Re-encode frame with quality setting
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                _, encoded = cv2.imencode(".jpg", frame, encode_param)
                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

                if frame is not None:
                    writer.write(frame)
                frame_count += 1

            cap.release()
            writer.release()

            if output_path.exists():
                original_size = input_path.stat().st_size
                compressed_size = output_path.stat().st_size
                savings = (
                    (1 - compressed_size / original_size) * 100
                    if original_size > 0
                    else 0
                )
                logger.info(
                    f"OpenCV compression: {original_size} -> {compressed_size} bytes ({savings:.1f}% saved)"
                )
                return True, output_path

            return False, None

        except Exception as e:
            logger.error(f"OpenCV compression error: {e}")
            return False, None
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            if writer is not None:
                try:
                    writer.release()
                except Exception:
                    pass

    def get_compression_info(self) -> dict:
        """Get information about compression capabilities"""
        return {
            "ffmpeg_available": self.ffmpeg_available,
            "quality": self.quality,
            "crf": self.QUALITY_CRF.get(self.quality, 23),
        }
