import time
from typing import List, Tuple

import pytest
from hand_tracker import Calibration, MovementFilter


def test_movement_filter_average_and_buffer_resize():
    f = MovementFilter(buffer_size=3)
    f.add_position((0, 0))
    f.add_position((9, 6))
    f.add_position((6, 12))
    assert f.get_filtered_position() == (5, 6)  # (0+9+6)/3=5, (0+6+12)/3=6

    # Resize buffer smaller and ensure only last N are kept
    f.set_buffer_size(2)
    # buffer should now contain last two positions: (9,6), (6,12)
    assert f.get_filtered_position() == (8, 9)  # (9+6)/2, (6+12)/2

    # Add another point and check averaging
    f.add_position((10, 10))
    assert f.get_filtered_position() == (8, 11)  # (6+10)/2, (12+10)/2


def test_calibration_bounds_and_values():
    c = Calibration()
    screen_h = 720

    # When wrist_y = screen_h/2 => sensitivity ~ 1.0
    sens = c.adjust_sensitivity([(0, screen_h // 2)], screen_h)
    assert 0.95 <= sens <= 1.05

    # Very small wrist_y should clamp to >= 0.5
    sens = c.adjust_sensitivity([(0, 10)], screen_h)
    assert sens == pytest.approx(0.5)

    # Large wrist_y should clamp to <= 2.0
    sens = c.adjust_sensitivity([(0, screen_h)], screen_h)
    assert sens == pytest.approx(2.0)
