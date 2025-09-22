import math

import pytest
from targets import Target


def test_target_collision():
    t = Target(100, 100, target_type="static", bounds=(200, 200))
    # Aim inside radius
    assert t.check_collision((100, 100)) is True
    # Aim at edge
    assert t.check_collision((100 + t.radius, 100)) is True
    # Aim outside
    assert t.check_collision((100 + t.radius + 1, 100)) is False


def test_target_moving_bounce_left_right():
    # Start near left edge, moving left, should bounce to the right
    t = Target(10, 100, target_type="moving", bounds=(200, 200), speed_mul=1.0)
    t.radius = 12
    t.vx = -5.0
    t.vy = 0.0
    t.update()
    assert t.x == t.radius  # clamped
    assert t.vx > 0  # bounced

    # Move to right edge and bounce
    t.x = 200 - 10
    t.vx = 7.0
    # after update should clamp and invert
    t.update()
    assert t.x == 200 - t.radius
    assert t.vx < 0


def test_target_multipliers_affect_radius_speed_points():
    # small target base radius 20, points 30
    t_small_easy = Target(50, 50, target_type="small", bounds=(200, 200), size_mul=1.2, points_mul=0.5)
    assert t_small_easy.radius >= 20  # increased a bit by size_mul
    assert t_small_easy.points == int(round(30 * 0.5))

    # moving with speed multiplier should scale velocity magnitude
    t_move_fast = Target(50, 50, target_type="moving", bounds=(200, 200), speed_mul=2.0)
    speed = math.hypot(t_move_fast.vx, t_move_fast.vy)
    assert speed >= 2.0  # base min 1.0, with *2.0 should be >=2
