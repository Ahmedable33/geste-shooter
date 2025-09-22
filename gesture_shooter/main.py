from game_engine import GameEngine
from hand_tracker import HandTracker, MouseTracker


def main():
    tracker = None
    try:
        try:
            tracker = HandTracker()
        except Exception as cam_err:
            print(f"Webcam indisponible ({cam_err}). Passage en mode souris.")
            tracker = MouseTracker()
        engine = GameEngine()
        engine.run(tracker)
    except Exception as e:
        print(f"Une erreur s'est produite: {e}")
    finally:
        if tracker is not None:
            tracker.shutdown()


if __name__ == "__main__":
    main()
