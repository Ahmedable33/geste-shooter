from collections import deque
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp


class MovementFilter:
    def __init__(self, buffer_size: int = 5):
        self._buffer_size = max(1, int(buffer_size))
        self.buffer: deque[Tuple[int, int]] = deque(maxlen=self._buffer_size)

    def set_buffer_size(self, buffer_size: int) -> None:
        buffer_size = max(1, int(buffer_size))
        if buffer_size == self._buffer_size:
            return
        old = list(self.buffer)
        self._buffer_size = buffer_size
        self.buffer = deque(old[-buffer_size:], maxlen=buffer_size)

    def add_position(self, pos: Optional[Tuple[int, int]]) -> None:
        if pos is not None:
            self.buffer.append(pos)

    def get_filtered_position(self) -> Optional[Tuple[int, int]]:
        if not self.buffer:
            return None
        avg_x = int(round(sum(p[0] for p in self.buffer) / len(self.buffer)))
        avg_y = int(round(sum(p[1] for p in self.buffer) / len(self.buffer)))
        return (avg_x, avg_y)


class Calibration:
    def __init__(self):
        self.sensitivity: float = 1.0
        self.deadzone: int = 5

    def adjust_sensitivity(self, landmarks: Optional[List[Tuple[int, int]]], screen_height: int) -> float:
        if not landmarks or len(landmarks) == 0:
            return self.sensitivity
        wrist_y = landmarks[0][1]
        # Normalize by half screen height; closer to camera often appears larger -> lower y may not be reliable,
        # but this gives a simple dynamic range in [0.5, 2.0]
        base = max(1, screen_height // 2)
        self.sensitivity = max(0.5, min(2.0, wrist_y / base))
        return self.sensitivity


class HandTracker:
    def __init__(self, camera_id: int = 0, screen_width: int = 1280, screen_height: int = 720, filter_size: int = 5):
        self.screen_width = screen_width
        self.screen_height = screen_height

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.cap = cv2.VideoCapture(camera_id)
        # Request camera resolution similar to screen for direct mapping
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.screen_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.screen_height)

        if not self.cap.isOpened():
            raise RuntimeError("Impossible d'ouvrir la webcam. Vérifiez la connexion et les permissions.")

        self.filter = MovementFilter(buffer_size=filter_size)
        self.calibration = Calibration()

    def shutdown(self) -> None:
        try:
            if self.cap:
                self.cap.release()
            if getattr(self, "hands", None):
                try:
                    self.hands.close()
                except Exception:
                    pass
        except Exception:
            pass

    def _fingers_up(self, landmarks: List[Tuple[int, int]]) -> dict:
        # Using y-coordinates: smaller y means "up" when camera image origin is top-left.
        # Index finger joints: MCP=5, PIP=6, DIP=7, TIP=8
        def is_extended(tip_idx: int, pip_idx: int) -> bool:
            return landmarks[tip_idx][1] < landmarks[pip_idx][1]

        state = {
            "index": is_extended(8, 6),
            "middle": is_extended(12, 10),
            "ring": is_extended(16, 14),
            "pinky": is_extended(20, 18),
        }
        # For thumb, horizontal relation can be used, but we omit to keep it robust across handedness/orientation.
        return state

    def get_hand_landmarks(self) -> Optional[List[Tuple[int, int]]]:
        success, img = self.cap.read()
        if not success or img is None:
            return None

        # Mirror for natural interaction
        img = cv2.flip(img, 1)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)

        if results.multi_hand_landmarks:
            hlms = results.multi_hand_landmarks[0]
            pts: List[Tuple[int, int]] = []
            for lm in hlms.landmark:
                x = int(lm.x * self.screen_width)
                y = int(lm.y * self.screen_height)
                pts.append((x, y))
            return pts
        return None

    def is_shooting_gesture(self, landmarks: Optional[List[Tuple[int, int]]]) -> bool:
        if not landmarks or len(landmarks) < 21:
            return False
        fingers = self._fingers_up(landmarks)
        index_extended = fingers["index"]
        others_folded = not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]
        return index_extended and others_folded

    def detect_gestures(self, landmarks: Optional[List[Tuple[int, int]]]) -> dict:
        gestures = {"shoot": False, "reload": False, "pause": False}
        if not landmarks or len(landmarks) < 21:
            return gestures
        fingers = self._fingers_up(landmarks)

        # Shoot: index only
        gestures["shoot"] = fingers["index"] and not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]

        # Reload: fist (all folded)
        all_folded = not fingers["index"] and not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]
        gestures["reload"] = all_folded

        # Pause: open palm (all four extended)
        all_open = fingers["index"] and fingers["middle"] and fingers["ring"] and fingers["pinky"]
        gestures["pause"] = all_open

        return gestures

    def get_aim_position(self, landmarks: Optional[List[Tuple[int, int]]]) -> Optional[Tuple[int, int]]:
        if not landmarks or len(landmarks) <= 8:
            return None
        # Calibrate and optionally adjust smoothing
        sens = self.calibration.adjust_sensitivity(landmarks, self.screen_height)
        # Adjust smoothing according to sensitivity (closer -> more responsive -> smaller buffer)
        if sens >= 1.6:
            self.filter.set_buffer_size(3)
        elif sens >= 1.2:
            self.filter.set_buffer_size(4)
        elif sens >= 0.8:
            self.filter.set_buffer_size(5)
        else:
            self.filter.set_buffer_size(7)

        pos = landmarks[8]  # index tip
        # Deadzone filtering: reduce small jitter
        if self.filter.buffer:
            last = self.filter.buffer[-1]
            if abs(pos[0] - last[0]) < self.calibration.deadzone and abs(pos[1] - last[1]) < self.calibration.deadzone:
                pos = last
        self.filter.add_position(pos)
        return self.filter.get_filtered_position()


# Debug fallback: mouse-based tracker for testing without webcam
class MouseTracker:
    def __init__(self, screen_width: int = 1280, screen_height: int = 720):
        # Screen dims are used only for clamping if needed
        self.screen_width = screen_width
        self.screen_height = screen_height

    def shutdown(self) -> None:
        pass

    def get_hand_landmarks(self) -> Optional[List[Tuple[int, int]]]:
        return None

    def is_shooting_gesture(self, landmarks: Optional[List[Tuple[int, int]]]) -> bool:
        # Left mouse button
        try:
            import pygame
            return pygame.mouse.get_pressed()[0]
        except Exception:
            return False

    def detect_gestures(self, landmarks: Optional[List[Tuple[int, int]]]) -> dict:
        gestures = {"shoot": False, "reload": False, "pause": False}
        try:
            import pygame
            pressed = pygame.mouse.get_pressed()
            gestures["shoot"] = bool(pressed[0])
            gestures["reload"] = bool(pressed[2])  # right click reload
            # pause kept on keyboard 'P' via engine; middle-click can also pause
            gestures["pause"] = bool(pressed[1])
        except Exception:
            pass
        return gestures

    def get_aim_position(self, landmarks: Optional[List[Tuple[int, int]]]) -> Optional[Tuple[int, int]]:
        try:
            import pygame
            x, y = pygame.mouse.get_pos()
            # Clamp to screen
            x = max(0, min(self.screen_width - 1, int(x)))
            y = max(0, min(self.screen_height - 1, int(y)))
            return (x, y)
        except Exception:
            return None
