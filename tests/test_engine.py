import os
import time

import pygame
import pytest
from game_engine import GameEngine


@pytest.fixture
def engine():
    # Ensure headless drivers are set for pygame in CI
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    e = GameEngine()
    try:
        yield e
    finally:
        try:
            pygame.quit()
        except Exception:
            pass


def test_apply_difficulty_changes_settings(engine: GameEngine):
    engine._apply_difficulty("Easy")
    assert engine.max_ammo == engine.difficulty_levels["Easy"]["max_ammo"]
    assert engine.spawn_interval == engine.difficulty_levels["Easy"]["spawn_interval"]
    assert engine.target_size_mul == pytest.approx(engine.difficulty_levels["Easy"]["size_mul"])

    engine._apply_difficulty("Hard")
    assert engine.max_ammo == engine.difficulty_levels["Hard"]["max_ammo"]
    assert engine.spawn_interval == engine.difficulty_levels["Hard"]["spawn_interval"]
    assert engine.target_speed_mul == pytest.approx(engine.difficulty_levels["Hard"]["speed_mul"])


def test_spawn_and_hit_increases_score_and_spawns_effects(engine: GameEngine):
    engine.targets.clear()
    engine.score = 0
    engine.explosions.clear()
    engine.shockwaves.clear()

    engine.spawn_target()
    assert len(engine.targets) == 1
    t = engine.targets[0]

    # Hit at target center
    engine.check_hit((int(t.x), int(t.y)))
    assert engine.score >= t.points
    assert len(engine.explosions) >= 1
    assert len(engine.shockwaves) >= 1


def test_try_shoot_no_ammo_sets_no_ammo_message(engine: GameEngine):
    engine.ammo = 0
    before = int(time.time() * 1000.0)
    engine._try_shoot((100, 100))
    assert engine.no_ammo_msg_end_ms >= before


def test_reload_completes_after_time(engine: GameEngine):
    engine.ammo = 0
    engine._start_reload()
    assert engine.reloading is True
    # simulate time elapsing
    engine.reload_started_at = (time.time() * 1000.0) - (engine.reload_time_ms + 1)
    engine._update_reload()
    assert engine.reloading is False
    assert engine.ammo == engine.max_ammo
