"""
Monitor Manager Module
Handles multi-monitor detection and selection with comprehensive error handling
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Try to import mss
try:
    import mss

    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    logger.error("mss not available - monitor detection disabled")


@dataclass
class MonitorInfo:
    """Information about a display monitor"""

    index: int
    width: int
    height: int
    left: int
    top: int
    right: int
    bottom: int
    name: str = ""
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "width": self.width,
            "height": self.height,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "name": self.name,
            "is_primary": self.is_primary,
        }

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def position(self) -> str:
        return f"({self.left}, {self.top})"


class MonitorManager:
    """Handles multi-monitor detection and selection"""

    def __init__(self):
        self._sct = None
        self._monitors: List[MonitorInfo] = []
        self._primary_index = 1  # MSS uses index 1 for primary monitor
        self._refresh_monitors()

    def _refresh_monitors(self) -> bool:
        """Refresh the list of detected monitors"""
        if not MSS_AVAILABLE:
            logger.warning("MSS not available, cannot detect monitors")
            return False

        try:
            if self._sct is None:
                self._sct = mss.mss()

            self._monitors = []

            # MSS monitors[0] is the combined virtual screen
            # monitors[1:] are individual physical monitors
            all_monitors = self._sct.monitors

            for i, monitor in enumerate(all_monitors):
                if i == 0:
                    # Skip virtual screen (combined all monitors)
                    continue

                monitor_info = MonitorInfo(
                    index=i,
                    width=monitor.get("width", 0),
                    height=monitor.get("height", 0),
                    left=monitor.get("left", 0),
                    top=monitor.get("top", 0),
                    right=monitor.get("left", 0) + monitor.get("width", 0),
                    bottom=monitor.get("top", 0) + monitor.get("height", 0),
                    name=f"Monitor {i}",
                    is_primary=(i == 1),  # Index 1 is primary in MSS
                )
                self._monitors.append(monitor_info)

            logger.info(f"Detected {len(self._monitors)} monitor(s)")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh monitors: {e}")
            return False

    def get_monitors(self) -> List[MonitorInfo]:
        """Get list of all detected monitors"""
        if not self._monitors:
            self._refresh_monitors()
        return self._monitors.copy()

    def get_monitor(self, index: int) -> Optional[MonitorInfo]:
        """Get monitor by index (1-based, matching MSS convention)"""
        monitors = self.get_monitors()
        for m in monitors:
            if m.index == index:
                return m
        return None

    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """Get the primary monitor"""
        return self.get_monitor(1)

    def get_total_bounds(self) -> Tuple[int, int, int, int]:
        """Get total bounds of all monitors (left, top, right, bottom)"""
        if not self._monitors:
            self._refresh_monitors()

        if not self._monitors:
            return (0, 0, 1920, 1080)  # Default fallback

        left = min(m.left for m in self._monitors)
        top = min(m.top for m in self._monitors)
        right = max(m.right for m in self._monitors)
        bottom = max(m.bottom for m in self._monitors)

        return (left, top, right, bottom)

    def get_monitor_at_point(self, x: int, y: int) -> Optional[MonitorInfo]:
        """Get the monitor at a specific point"""
        for monitor in self.get_monitors():
            if monitor.left <= x < monitor.right and monitor.top <= y < monitor.bottom:
                return monitor
        return None

    def validate_monitor_index(self, index: int) -> int:
        """Validate and return a valid monitor index"""
        monitors = self.get_monitors()
        if not monitors:
            return 1  # Default to primary

        valid_indices = [m.index for m in monitors]
        if index in valid_indices:
            return index

        logger.warning(f"Invalid monitor index {index}, using primary (1)")
        return 1

    def get_capture_region(
        self,
        monitor_index: int = 1,
        region: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """
        Get the capture region for a monitor.

        Args:
            monitor_index: Index of monitor to capture (1-based)
            region: Optional custom region {x, y, width, height} relative to monitor

        Returns:
            Dict with monitor capture coordinates for MSS
        """
        monitor = self.get_monitor(monitor_index)
        if not monitor:
            # Fallback to primary
            monitor = self.get_primary_monitor()
            if not monitor:
                # Last resort fallback
                return {"left": 0, "top": 0, "width": 1920, "height": 1080}

        if region:
            # Custom region relative to monitor
            x = region.get("x", 0)
            y = region.get("y", 0)
            width = region.get("width", monitor.width)
            height = region.get("height", monitor.height)

            # Clamp to monitor bounds
            x = max(0, min(x, monitor.width - 1))
            y = max(0, min(y, monitor.height - 1))
            width = max(1, min(width, monitor.width - x))
            height = max(1, min(height, monitor.height - y))

            return {
                "left": monitor.left + x,
                "top": monitor.top + y,
                "width": width,
                "height": height,
            }

        # Full monitor capture
        return {
            "left": monitor.left,
            "top": monitor.top,
            "width": monitor.width,
            "height": monitor.height,
        }

    def list_monitors(self) -> List[Dict[str, Any]]:
        """Get list of monitors as dictionaries"""
        return [m.to_dict() for m in self.get_monitors()]

    def get_status(self) -> Dict[str, Any]:
        """Get monitor manager status"""
        return {
            "mss_available": MSS_AVAILABLE,
            "monitor_count": len(self._monitors),
            "monitors": self.list_monitors(),
            "primary_index": self._primary_index,
        }

    def __del__(self):
        """Cleanup on destruction"""
        if self._sct:
            try:
                self._sct.close()
            except Exception:
                pass


def test_black_frame(frame: np.ndarray, threshold: float = 5.0) -> bool:
    """
    Test if a frame appears to be black/empty.

    Args:
        frame: numpy array of the frame
        threshold: mean pixel value threshold below which frame is considered black

    Returns:
        True if frame appears to be black
    """
    try:
        if frame is None or frame.size == 0:
            return True

        mean_val = np.mean(frame)
        return mean_val < threshold
    except Exception:
        return True


def find_active_monitor(sct, monitors: List[MonitorInfo]) -> int:
    """
    Find the monitor with actual content (non-black frames).

    Args:
        sct: MSS instance
        monitors: List of monitor info

    Returns:
        Index of the active monitor
    """
    if not monitors:
        return 1

    best_monitor = 1
    best_mean = 0.0

    for monitor in monitors:
        try:
            screenshot = sct.grab(
                {
                    "left": monitor.left,
                    "top": monitor.top,
                    "width": monitor.width,
                    "height": monitor.height,
                }
            )
            frame = np.array(screenshot)

            if frame.size > 0:
                mean_val = np.mean(frame)
                if mean_val > best_mean:
                    best_mean = mean_val
                    best_monitor = monitor.index
        except Exception:
            continue

    return best_monitor
