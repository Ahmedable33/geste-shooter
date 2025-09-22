import math
import os
import random
import time
from typing import List, Optional, Tuple

import pygame
import pygame.sndarray
import numpy as np
from targets import Target


class GameEngine:
    def __init__(self, screen_width: int = 1280, screen_height: int = 720):
        pygame.init()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Gesture Shooting Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)

        self.running = True
        self.paused = False

        self.score = 0

        self.max_ammo = 6
        self.ammo = self.max_ammo
        self.reloading = False
        self.reload_time_ms = 1200
        self.reload_started_at = 0.0
        self.reload_gesture_active = False
        self.pause_gesture_active = False

        self.targets = []
        self.spawn_timer = 0
        self.spawn_interval = 60
        self.spawn_interval_min = 20
        self.start_time = time.time()

        self.last_shot_time = 0
        self.shot_cooldown_ms = 250
        self.shoot_key_held = False

        self.crosshair_radius = 12

        # Effects containers
        self.explosions: List[dict] = []
        self.muzzle_flashes: List[dict] = []
        self.shockwaves: List[dict] = []
        self.tracers: List[dict] = []
        self.no_ammo_msg_end_ms = 0

        # Audio
        self.audio_enabled = False
        self.sounds = {"shot": None, "hit": None, "reload": None, "dry": None}
        self.sound_volumes = {"shot": 0.9, "hit": 0.8, "reload": 0.8, "dry": 0.7}
        self.master_volume = 0.8
        self.muted = False
        self._init_audio()

        # Options menu state
        self.show_options = False
        self._options_dragging_volume = False
        self._options_paused_prev = False

        # Difficulty configuration
        self.difficulty_levels = {
            "Easy": {
                "spawn_interval": 70,
                "spawn_interval_min": 30,
                "max_ammo": 8,
                "shot_cooldown_ms": 300,
                "speed_mul": 0.85,
                "size_mul": 1.10,
                "points_mul": 0.9,
                "weights": [("static", 0.6), ("moving", 0.3), ("small", 0.1)],
            },
            "Normal": {
                "spawn_interval": 60,
                "spawn_interval_min": 20,
                "max_ammo": 6,
                "shot_cooldown_ms": 250,
                "speed_mul": 1.0,
                "size_mul": 1.0,
                "points_mul": 1.0,
                "weights": [("static", 0.5), ("moving", 0.35), ("small", 0.15)],
            },
            "Hard": {
                "spawn_interval": 50,
                "spawn_interval_min": 10,
                "max_ammo": 5,
                "shot_cooldown_ms": 220,
                "speed_mul": 1.25,
                "size_mul": 0.9,
                "points_mul": 1.2,
                "weights": [("static", 0.35), ("moving", 0.45), ("small", 0.20)],
            },
        }
        self.difficulty = "Normal"
        self._apply_difficulty(self.difficulty, initial=True)

    def _weighted_choice(self):
        items = self.spawn_weights
        r = random.random()
        acc = 0.0
        for name, w in items:
            acc += w
            if r <= acc:
                return name
        return items[-1][0]

    def spawn_target(self):
        ttype = self._weighted_choice()
        x = random.randint(50, self.screen_width - 50)
        y = random.randint(50, self.screen_height - 50)
        self.targets.append(
            Target(
                x,
                y,
                ttype,
                bounds=(self.screen_width, self.screen_height),
                speed_mul=self.target_speed_mul,
                size_mul=self.target_size_mul,
                points_mul=self.points_mul,
            )
        )

    def check_hit(self, aim_pos: Optional[Tuple[int, int]]):
        if not aim_pos:
            return
        for t in self.targets[:]:
            if t.check_collision(aim_pos):
                self.score += t.points
                self.targets.remove(t)
                self._spawn_explosion(int(t.x), int(t.y), t.color)
                self._play_sound("hit")
                self._spawn_shockwave(int(t.x), int(t.y), t.color)
                self._spawn_tracer(aim_pos, (int(t.x), int(t.y)))

    def _maybe_increase_difficulty(self):
        elapsed = time.time() - self.start_time
        step = int(elapsed // 20)
        target_interval = max(self.spawn_interval_min, 60 - step * 5)
        if target_interval != self.spawn_interval:
            self.spawn_interval = target_interval

    def _draw_hud(self):
        score_text = self.font.render(f"Score: {self.score}", True, (255, 255, 255))
        ammo_text = self.font.render(f"Ammo: {self.ammo}/{self.max_ammo}", True, (255, 255, 255))
        self.screen.blit(score_text, (20, 20))
        self.screen.blit(ammo_text, (20, 60))
        if self.reloading:
            elapsed = (time.time() * 1000.0) - self.reload_started_at
            pct = max(0.0, min(1.0, elapsed / self.reload_time_ms))
            bar_w = 200
            bar_h = 16
            x = 20
            y = 100
            pygame.draw.rect(self.screen, (80, 80, 80), pygame.Rect(x, y, bar_w, bar_h), border_radius=4)
            pygame.draw.rect(self.screen, (0, 200, 255), pygame.Rect(x, y, int(bar_w * pct), bar_h), border_radius=4)
            txt = self.font.render("Reloading...", True, (0, 200, 255))
            self.screen.blit(txt, (x + bar_w + 10, y - 4))
        if self.paused:
            paused_text = self.font.render("PAUSED", True, (255, 255, 0))
            rect = paused_text.get_rect(center=(self.screen_width // 2, 40))
            self.screen.blit(paused_text, rect)
        # Difficulty label (top-right)
        diff_text = self.font.render(f"Diff: {self.difficulty}", True, (200, 200, 200))
        dr = diff_text.get_rect(topright=(self.screen_width - 20, 20))
        self.screen.blit(diff_text, dr)
        # Audio status (top-right, below difficulty)
        if not self.audio_enabled:
            vol_text = self.font.render("Audio: Off", True, (180, 180, 180))
        elif self.muted:
            vol_text = self.font.render("Audio: Muted", True, (255, 120, 120))
        else:
            vol_text = self.font.render(f"Vol: {int(self.master_volume * 100)}%", True, (200, 200, 200))
        vr = vol_text.get_rect(topright=(self.screen_width - 20, dr.bottom + 8))
        self.screen.blit(vol_text, vr)
        # No ammo hint
        now_ms = int(time.time() * 1000.0)
        if now_ms < self.no_ammo_msg_end_ms:
            na = self.font.render("NO AMMO", True, (255, 80, 80))
            self.screen.blit(na, (20, 140))

    def _init_audio(self):
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.audio_enabled = True
        except Exception:
            self.audio_enabled = False

        def _p(*parts):
            return os.path.join(os.path.dirname(__file__), *parts)

        self.sounds["shot"] = self._load_sound(_p("assets", "sounds", "shot.wav"))
        self.sounds["hit"] = self._load_sound(_p("assets", "sounds", "hit.wav"))
        self.sounds["reload"] = self._load_sound(_p("assets", "sounds", "reload.wav"))
        self.sounds["dry"] = self._load_sound(_p("assets", "sounds", "dry.wav"))
        # Apply initial volume
        self._apply_volume()
        # Generate simple fallback beeps if files are missing
        self._ensure_fallback_sounds()
        self._apply_volume()

    def _load_sound(self, path: str):
        if not self.audio_enabled:
            return None
        try:
            if os.path.exists(path):
                return pygame.mixer.Sound(path)
        except Exception:
            return None
        return None

    def _ensure_fallback_sounds(self):
        if not self.audio_enabled:
            return
        try:
            sr = 44100
            def tone(freq: float, dur_ms: int, vol: float = 0.6, wave: str = "sine"):
                n = max(1, int(sr * dur_ms / 1000.0))
                t = np.linspace(0.0, dur_ms / 1000.0, n, endpoint=False)
                if wave == "square":
                    w = np.sign(np.sin(2 * np.pi * freq * t))
                elif wave == "saw":
                    # simple saw
                    w = 2.0 * (t * freq - np.floor(0.5 + t * freq))
                else:
                    w = np.sin(2 * np.pi * freq * t)
                a = (w * vol).astype(np.float32)
                # stereo
                arr = np.stack([a, a], axis=1)
                return pygame.sndarray.make_sound((arr * 32767).astype(np.int16))

            def noise(dur_ms: int, vol: float = 0.5, decay: bool = True):
                n = max(1, int(sr * dur_ms / 1000.0))
                w = np.random.uniform(-1.0, 1.0, size=n).astype(np.float32)
                if decay:
                    env = np.exp(-np.linspace(0, 5, n)).astype(np.float32)
                    w *= env
                a = (w * vol).astype(np.float32)
                arr = np.stack([a, a], axis=1)
                return pygame.sndarray.make_sound((arr * 32767).astype(np.int16))

            def concat(s1: pygame.mixer.Sound, s2: pygame.mixer.Sound):
                a1 = pygame.sndarray.array(s1).astype(np.int16)
                a2 = pygame.sndarray.array(s2).astype(np.int16)
                cat = np.concatenate([a1, a2], axis=0)
                return pygame.sndarray.make_sound(cat)

            # Shot: short square burst
            if self.sounds.get("shot") is None:
                self.sounds["shot"] = tone(700.0, 90, vol=0.7, wave="square")
            # Hit: noise burst with decay
            if self.sounds.get("hit") is None:
                self.sounds["hit"] = noise(260, vol=0.55, decay=True)
            # Reload: two short beeps separated by a small silence
            if self.sounds.get("reload") is None:
                beep = tone(500.0, 100, vol=0.5, wave="sine")
                silence = pygame.sndarray.make_sound(np.zeros((int(sr * 0.08), 2), dtype=np.int16))
                self.sounds["reload"] = concat(concat(beep, silence), beep)
            # Dry: low short click
            if self.sounds.get("dry") is None:
                self.sounds["dry"] = tone(180.0, 60, vol=0.5, wave="sine")
        except Exception:
            # If synthesis fails, just keep None and remain silent
            pass

    def _play_sound(self, key: str):
        try:
            s = self.sounds.get(key)
            if s is not None and self.audio_enabled:
                s.play()
        except Exception:
            pass

    def _apply_volume(self):
        if not self.audio_enabled:
            return
        try:
            for k, s in self.sounds.items():
                if s is None:
                    continue
                base = self.sound_volumes.get(k, 1.0)
                vol = 0.0 if self.muted else max(0.0, min(1.0, self.master_volume * base))
                s.set_volume(vol)
        except Exception:
            pass

    def _change_volume(self, delta: float):
        self.master_volume = max(0.0, min(1.0, self.master_volume + delta))
        self._apply_volume()

    def _toggle_mute(self):
        self.muted = not self.muted
        self._apply_volume()

    def _options_layout(self):
        # Central panel layout
        panel_w, panel_h = 640, 360
        px = (self.screen_width - panel_w) // 2
        py = (self.screen_height - panel_h) // 2

        # Volume bar
        bar_w, bar_h = 360, 16
        bar_x = px + 140
        bar_y = py + 110

        layout = {
            "panel": pygame.Rect(px, py, panel_w, panel_h),
            "title_pos": (px + 20, py + 20),
            "audio_label_pos": (px + 20, py + 80),
            "mute_btn": pygame.Rect(px + 20, py + 110, 100, 32),
            "vol_bar": pygame.Rect(bar_x, bar_y, bar_w, bar_h),
            "vol_text_pos": (bar_x + bar_w + 12, bar_y - 6),
            "preview_shot": pygame.Rect(px + 20, py + 180, 120, 36),
            "preview_hit": pygame.Rect(px + 170, py + 180, 120, 36),
            "preview_reload": pygame.Rect(px + 320, py + 180, 120, 36),
            "preview_dry": pygame.Rect(px + 470, py + 180, 120, 36),
            "resume_btn": pygame.Rect(px + panel_w - 160, py + panel_h - 56, 140, 40),
        }
        return layout

    def _toggle_options(self):
        if not self.show_options:
            self._options_paused_prev = self.paused
            self.show_options = True
            self.paused = True
            self._options_dragging_volume = False
        else:
            self.show_options = False
            self.paused = self._options_paused_prev
            self._options_dragging_volume = False

    def _handle_options_event(self, event):
        layout = self._options_layout()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_o):
                self._toggle_options()
                return
            if event.key == pygame.K_m:
                self._toggle_mute()
                return
            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self._change_volume(-0.05)
                return
            if event.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                self._change_volume(+0.05)
                return
            if event.key == pygame.K_1:
                self._play_sound("shot")
                return
            if event.key == pygame.K_2:
                self._play_sound("hit")
                return
            if event.key == pygame.K_3:
                self._play_sound("reload")
                return
            if event.key == pygame.K_4:
                self._play_sound("dry")
                return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if layout["resume_btn"].collidepoint(mx, my):
                self._toggle_options()
                return
            if layout["mute_btn"].collidepoint(mx, my):
                self._toggle_mute()
                return
            if layout["preview_shot"].collidepoint(mx, my):
                self._play_sound("shot")
                return
            if layout["preview_hit"].collidepoint(mx, my):
                self._play_sound("hit")
                return
            if layout["preview_reload"].collidepoint(mx, my):
                self._play_sound("reload")
                return
            if layout["preview_dry"].collidepoint(mx, my):
                self._play_sound("dry")
                return
            if layout["vol_bar"].collidepoint(mx, my):
                frac = (mx - layout["vol_bar"].x) / layout["vol_bar"].width
                self.master_volume = max(0.0, min(1.0, frac))
                self._apply_volume()
                self._options_dragging_volume = True
                return
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._options_dragging_volume = False
            return
        elif event.type == pygame.MOUSEMOTION and self._options_dragging_volume:
            mx, my = event.pos
            bar = self._options_layout()["vol_bar"]
            frac = (mx - bar.x) / bar.width
            self.master_volume = max(0.0, min(1.0, frac))
            self._apply_volume()

    def _draw_options_menu(self):
        layout = self._options_layout()
        # Dim background
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Panel
        pygame.draw.rect(self.screen, (30, 30, 34), layout["panel"], border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 200), layout["panel"], 2, border_radius=10)

        # Title
        title = self.font.render("Options", True, (255, 255, 255))
        self.screen.blit(title, layout["title_pos"])

        # Audio label
        audio_lbl = self.font.render("Audio", True, (200, 200, 200))
        self.screen.blit(audio_lbl, layout["audio_label_pos"])

        # Mute button
        pygame.draw.rect(self.screen, (60, 60, 70), layout["mute_btn"], border_radius=6)
        m_text = self.font.render(f"Mute: {'On' if self.muted else 'Off'}", True, (255, 255, 255))
        self.screen.blit(m_text, (layout["mute_btn"].x + 10, layout["mute_btn"].y + 4))

        # Volume bar
        bar = layout["vol_bar"]
        pygame.draw.rect(self.screen, (80, 80, 90), bar, border_radius=6)
        fill_w = int(bar.width * (0.0 if self.muted else self.master_volume))
        if fill_w > 0:
            pygame.draw.rect(self.screen, (0, 200, 255), pygame.Rect(bar.x, bar.y, fill_w, bar.height), border_radius=6)
        vol_txt = self.font.render(f"{int(self.master_volume * 100)}%", True, (200, 200, 200))
        self.screen.blit(vol_txt, layout["vol_text_pos"])

        # Preview buttons
        for key, rect, label in [
            ("shot", layout["preview_shot"], "Shot"),
            ("hit", layout["preview_hit"], "Hit"),
            ("reload", layout["preview_reload"], "Reload"),
            ("dry", layout["preview_dry"], "Dry"),
        ]:
            pygame.draw.rect(self.screen, (60, 60, 70), rect, border_radius=6)
            txt = self.font.render(label, True, (255, 255, 255))
            tr = txt.get_rect(center=rect.center)
            self.screen.blit(txt, tr)

        # Resume button
        pygame.draw.rect(self.screen, (0, 160, 120), layout["resume_btn"], border_radius=6)
        rtxt = self.font.render("Reprendre", True, (255, 255, 255))
        rr = rtxt.get_rect(center=layout["resume_btn"].center)
        self.screen.blit(rtxt, rr)

    def _apply_difficulty(self, level: str, initial: bool = False):
        cfg = self.difficulty_levels.get(level, self.difficulty_levels["Normal"])
        self.spawn_interval = cfg["spawn_interval"]
        self.spawn_interval_min = cfg["spawn_interval_min"]
        self.max_ammo = cfg["max_ammo"]
        self.ammo = self.max_ammo  # refill on difficulty change
        self.shot_cooldown_ms = cfg["shot_cooldown_ms"]
        self.target_speed_mul = cfg["speed_mul"]
        self.target_size_mul = cfg["size_mul"]
        self.points_mul = cfg["points_mul"]
        self.spawn_weights = cfg["weights"]

    def _spawn_explosion(self, x: int, y: int, color: Tuple[int, int, int]):
        n = 18
        parts = []
        for i in range(n):
            ang = random.uniform(0.0, 2.0 * math.pi)
            spd = random.uniform(1.5, 4.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = random.randint(250, 600)  # ms
            parts.append({
                "x": float(x),
                "y": float(y),
                "vx": vx,
                "vy": vy,
                "life": life,
                "max_life": float(life),
                "radius": random.randint(2, 4),
                "color": color,
            })
        self.explosions.append({"particles": parts})

    def _update_explosions(self, dt_ms: int):
        for ex in self.explosions[:]:
            parts = ex["particles"]
            for p in parts:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vx"] *= 0.98
                p["vy"] *= 0.98
                p["life"] -= dt_ms
            ex["particles"] = [p for p in parts if p["life"] > 0]
            if not ex["particles"]:
                self.explosions.remove(ex)

    def _draw_explosions(self):
        for ex in self.explosions:
            for p in ex["particles"]:
                frac = max(0.0, min(1.0, p["life"] / p["max_life"]))
                r = max(1, int(p["radius"] * frac))
                a = int(255 * frac)
                surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                col = (*p["color"], a)
                pygame.draw.circle(surf, col, (r + 1, r + 1), r)
                self.screen.blit(surf, (int(p["x"]) - r - 1, int(p["y"]) - r - 1))

    def _spawn_shockwave(self, x: int, y: int, color: Tuple[int, int, int]):
        self.shockwaves.append({
            "x": x,
            "y": y,
            "r": 8.0,
            "max_r": 90.0,
            "life": 350,  # ms
            "max_life": 350.0,
            "color": color,
        })

    def _update_shockwaves(self, dt_ms: int):
        for s in self.shockwaves[:]:
            s["r"] += 180.0 * (dt_ms / 1000.0)  # px/sec
            s["life"] -= dt_ms
            if s["r"] >= s["max_r"] or s["life"] <= 0:
                self.shockwaves.remove(s)

    def _draw_shockwaves(self):
        for s in self.shockwaves:
            frac = max(0.0, min(1.0, s["life"] / s["max_life"]))
            alpha = int(200 * frac)
            width = max(1, int(6 * frac))
            surf = pygame.Surface((int(s["max_r"]) * 2 + 4, int(s["max_r"]) * 2 + 4), pygame.SRCALPHA)
            col = (*s["color"], alpha)
            center = int(s["max_r"]) + 2
            pygame.draw.circle(surf, col, (center, center), int(s["r"]), width)
            self.screen.blit(surf, (s["x"] - center, s["y"] - center))

    def _spawn_tracer(self, start: Tuple[int, int], end: Tuple[int, int]):
        self.tracers.append({
            "start": start,
            "end": end,
            "life": 120,  # ms
            "max_life": 120.0,
        })

    def _update_tracers(self, dt_ms: int):
        for t in self.tracers[:]:
            t["life"] -= dt_ms
            if t["life"] <= 0:
                self.tracers.remove(t)

    def _draw_tracers(self):
        for t in self.tracers:
            frac = 1.0 - max(0.0, min(1.0, t["life"] / t["max_life"]))
            # draw partial line from start to interpolated point
            sx, sy = t["start"]
            ex, ey = t["end"]
            px = int(sx + (ex - sx) * frac)
            py = int(sy + (ey - sy) * frac)
            pygame.draw.line(self.screen, (255, 255, 180), (sx, sy), (px, py), 2)

    def _spawn_muzzle_flash(self, pos: Optional[Tuple[int, int]]):
        if not pos:
            return
        end = int(time.time() * 1000.0) + 90
        self.muzzle_flashes.append({"pos": pos, "end": end})

    def _update_muzzle_flashes(self):
        now = int(time.time() * 1000.0)
        self.muzzle_flashes = [m for m in self.muzzle_flashes if m["end"] > now]

    def _draw_muzzle_flashes(self):
        now = int(time.time() * 1000.0)
        for m in self.muzzle_flashes:
            frac = max(0.0, min(1.0, (m["end"] - now) / 90.0))
            r = max(6, int(18 * frac))
            x, y = m["pos"]
            # bright center
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 240, 120, 200), (r + 1, r + 1), r)
            pygame.draw.circle(surf, (255, 120, 0, 220), (r + 1, r + 1), max(2, r // 2))
            self.screen.blit(surf, (x - r - 1, y - r - 1))

    def _toggle_pause(self):
        self.paused = not self.paused

    def _start_reload(self):
        if not self.reloading and self.ammo < self.max_ammo:
            self.reloading = True
            self.reload_started_at = time.time() * 1000.0

    def _update_reload(self):
        if self.reloading:
            if (time.time() * 1000.0) - self.reload_started_at >= self.reload_time_ms:
                self.reloading = False
                self.ammo = self.max_ammo
                self._play_sound("reload")

    def _handle_events(self):
        for event in pygame.event.get():
            # Route all input to options menu when it's open
            if self.show_options:
                self._handle_options_event(event)
                continue
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_p:
                    self._toggle_pause()
                elif event.key == pygame.K_o:
                    self._toggle_options()
                elif event.key == pygame.K_r:
                    self._start_reload()
                elif event.key == pygame.K_1:
                    self.difficulty = "Easy"
                    self._apply_difficulty(self.difficulty)
                elif event.key == pygame.K_2:
                    self.difficulty = "Normal"
                    self._apply_difficulty(self.difficulty)
                elif event.key == pygame.K_3:
                    self.difficulty = "Hard"
                    self._apply_difficulty(self.difficulty)
                elif event.key == pygame.K_m:
                    self._toggle_mute()
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self._change_volume(-0.05)
                elif event.key in (pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self._change_volume(+0.05)
                elif event.key == pygame.K_SPACE:
                    self.shoot_key_held = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    self.shoot_key_held = False

    def _can_shoot(self) -> bool:
        if self.paused:
            return False
        if self.reloading:
            return False
        if self.ammo <= 0:
            return False
        now = int(time.time() * 1000.0)
        if now - self.last_shot_time < self.shot_cooldown_ms:
            return False
        return True

    def _shoot(self, aim_pos: Optional[Tuple[int, int]]):
        if not self._can_shoot():
            return
        self.last_shot_time = int(time.time() * 1000.0)
        self.ammo -= 1
        self._spawn_muzzle_flash(aim_pos)
        self._play_sound("shot")
        self.check_hit(aim_pos)

    def _try_shoot(self, aim_pos: Optional[Tuple[int, int]]):
        # Similar to _can_shoot, but provides feedback when out of ammo
        if self.paused or self.reloading:
            return
        now = int(time.time() * 1000.0)
        if self.ammo <= 0:
            self._play_sound("dry")
            self.no_ammo_msg_end_ms = now + 700
            return
        if now - self.last_shot_time < self.shot_cooldown_ms:
            return
        self._shoot(aim_pos)

    def run(self, hand_tracker):
        try:
            while self.running:
                dt_ms = self.clock.tick(60)
                self._handle_events()

                # Update logic
                landmarks = hand_tracker.get_hand_landmarks()
                gestures = hand_tracker.detect_gestures(landmarks) if landmarks else {"shoot": False, "reload": False, "pause": False}
                aim_pos = hand_tracker.get_aim_position(landmarks)

                # Gesture edge handling for pause
                if gestures.get("pause", False):
                    if not self.pause_gesture_active:
                        self._toggle_pause()
                        self.pause_gesture_active = True
                else:
                    self.pause_gesture_active = False

                # Gesture edge handling for reload
                if gestures.get("reload", False):
                    if not self.reload_gesture_active:
                        self._start_reload()
                        self.reload_gesture_active = True
                else:
                    self.reload_gesture_active = False

                # Shooting gesture (continuous with cooldown)
                if gestures.get("shoot", False):
                    self._try_shoot(aim_pos)
                # Keyboard shooting (Space)
                if self.shoot_key_held:
                    self._try_shoot(aim_pos)

                # Update reload progress
                self._update_reload()

                # Spawn targets if not paused
                if not self.paused:
                    self.spawn_timer += 1
                    if self.spawn_timer >= self.spawn_interval:
                        self.spawn_target()
                        self.spawn_timer = 0
                        self._maybe_increase_difficulty()

                    # Update targets
                    for t in self.targets:
                        t.update()

                # Update effects
                self._update_explosions(dt_ms)
                self._update_muzzle_flashes()
                self._update_shockwaves(dt_ms)
                self._update_tracers(dt_ms)

                # Draw
                self.screen.fill((15, 15, 18))

                # Draw crosshair at aim_pos
                if aim_pos:
                    pygame.draw.circle(self.screen, (255, 0, 0), aim_pos, self.crosshair_radius, 2)
                    pygame.draw.line(self.screen, (255, 0, 0), (aim_pos[0] - 20, aim_pos[1]), (aim_pos[0] + 20, aim_pos[1]), 1)
                    pygame.draw.line(self.screen, (255, 0, 0), (aim_pos[0], aim_pos[1] - 20), (aim_pos[0], aim_pos[1] + 20), 1)

                # Draw targets
                for t in self.targets:
                    t.draw(self.screen)

                # HUD & effects
                self._draw_hud()
                self._draw_explosions()
                self._draw_muzzle_flashes()
                self._draw_shockwaves()
                self._draw_tracers()

                # Options menu overlay
                if self.show_options:
                    self._draw_options_menu()

                pygame.display.flip()
                # frame capped earlier via tick
        finally:
            pygame.quit()
