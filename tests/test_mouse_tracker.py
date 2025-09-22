import sys
import types

from hand_tracker import MouseTracker


def make_fake_pygame(buttons=(False, False, False), pos=(100, 200)):
    mod = types.ModuleType("pygame")
    mouse = types.SimpleNamespace()

    def get_pressed():
        return buttons

    def get_pos():
        return pos

    mouse.get_pressed = get_pressed
    mouse.get_pos = get_pos
    mod.mouse = mouse
    return mod


def test_mouse_tracker_gestures_shoot_reload_pause(monkeypatch):
    pg = make_fake_pygame(buttons=(True, True, True), pos=(100, 100))
    monkeypatch.setitem(sys.modules, "pygame", pg)

    mt = MouseTracker(screen_width=300, screen_height=300)
    g = mt.detect_gestures(None)
    assert g["shoot"] is True
    assert g["reload"] is True
    assert g["pause"] is True
    assert mt.is_shooting_gesture(None) is True


def test_mouse_tracker_aim_clamped(monkeypatch):
    # position beyond bounds should clamp
    pg = make_fake_pygame(buttons=(False, False, False), pos=(5000, -10))
    monkeypatch.setitem(sys.modules, "pygame", pg)

    mt = MouseTracker(screen_width=640, screen_height=480)
    x, y = mt.get_aim_position(None)
    assert x == 639
    assert y == 0
