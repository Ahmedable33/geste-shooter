#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Headless rendering for pygame
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
MODULE_DIR = PROJECT_ROOT / "gesture_shooter"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from gesture_shooter.game_engine import GameEngine


def main():
    # Create engine with dummy video driver
    eng = GameEngine(screen_width=1280, screen_height=720)
    try:
        # Show the options overlay
        eng.show_options = True
        eng.paused = True

        # Draw a representative frame
        eng.screen.fill((15, 15, 18))
        eng._draw_options_menu()  # type: ignore[attr-defined]
        out_path = eng._save_screenshot("screenshots/options-menu.png")  # type: ignore[attr-defined]
        print(out_path)
    finally:
        try:
            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
