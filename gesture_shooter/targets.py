import math
import random
from typing import Tuple

import pygame


class Target:
    def __init__(
        self,
        x: int,
        y: int,
        target_type: str = "static",
        bounds: Tuple[int, int] = (1280, 720),
        speed_mul: float = 1.0,
        size_mul: float = 1.0,
        points_mul: float = 1.0,
    ):
        self.x = float(x)
        self.y = float(y)
        self.type = target_type
        self.bounds = bounds
        base_radius = 40 if target_type != "small" else 20
        self.radius = max(8, int(round(base_radius * size_mul)))
        self.color = (0, 255, 0)
        base_points = 10
        self.points = int(round(base_points * points_mul))
        self.vx = 0.0
        self.vy = 0.0

        if target_type == "moving":
            self.color = (255, 255, 0)
            speed = random.uniform(1.0, 3.0) * max(0.1, speed_mul)
            ang = random.uniform(0.0, 2.0 * math.pi)
            self.vx = math.cos(ang) * speed
            self.vy = math.sin(ang) * speed
            base_points = 20
            self.points = int(round(base_points * points_mul))
        elif target_type == "small":
            self.color = (255, 0, 0)
            base_points = 30
            self.points = int(round(base_points * points_mul))

    def update(self):
        if self.type == "moving":
            self.x += self.vx
            self.y += self.vy
            w, h = self.bounds
            # Bounce on edges
            if self.x - self.radius < 0:
                self.x = self.radius
                self.vx *= -1
            elif self.x + self.radius > w:
                self.x = w - self.radius
                self.vx *= -1
            if self.y - self.radius < 0:
                self.y = self.radius
                self.vy *= -1
            elif self.y + self.radius > h:
                self.y = h - self.radius
                self.vy *= -1

    def check_collision(self, pos: Tuple[int, int]) -> bool:
        dx = self.x - float(pos[0])
        dy = self.y - float(pos[1])
        return (dx * dx + dy * dy) <= (self.radius * self.radius)

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (0, 0, 0), (int(self.x), int(self.y)), self.radius, 2)
