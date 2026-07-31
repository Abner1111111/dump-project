
import math
import os
import random
import sys
import pygame

os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"

pygame.init()
pygame.font.init()


SPEED_MULTIPLIER = 1.0
BASE_FLOAT_SPEED = 1.5


LYRICS = [
    "You ask what I like about you, ooh, I love it all ",
    "When it comes to you, baby, I'm addicted",
    "You're like a drug, no rehab can fix it",
    "I think you're perfect, baby even with your flaws",
    "You ask what I like about you ooh, I love it all",


]

LINE_DELAYS_SECONDS = [
    5.0,
    3.0,
    3.0,
    4.0,
    3.0,

]

TYPE_SPEEDS_MS = [40, 60, 40, 40, 90]
DEFAULT_TYPE_SPEED_MS = 80

CARD_WIDTH = 420
CARD_HEIGHT = 260
CARD_ROUNDING = 20
CARD_BORDER_WIDTH = 3
ACCENT_INSET = 10
ACCENT_BORDER_WIDTH = 1
SHADOW_OFFSET = (7, 9)

FONT_STACK = ["Georgia", "Baskerville Old Face", "Palatino Linotype", "Helvetica"]
BODY_FONT_SIZE = 44

POP_IN_MS = 260
SWAY_AMPLITUDE = 7.0
SWAY_SPEED = 1.1

TRANSPARENT_KEY = (255, 0, 128)

# How slowly the card background/text drift between black and white.
# Lower = slower.
BW_CYCLE_SPEED = 0.15


def pulse_black_white(t, phase=0.0):
    """Smoothly oscillate between black (0,0,0) and white (255,255,255)."""
    blend = (math.sin(t * BW_CYCLE_SPEED + phase) + 1) / 2
    return (int(255 * blend), int(255 * blend), int(255 * blend))


def ease_out_back(t):
    """Small overshoot easing for the card 'pop-in'."""
    c1 = 1.70158
    c3 = c1 + 1
    t = max(0.0, min(1.0, t))
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def first_available_font(names, size, bold=False):
    available = {name.lower(): name for name in pygame.font.get_fonts()}
    for name in names:
        key = name.replace(" ", "").lower()
        for avail_key, avail_name in available.items():
            if avail_key == key.replace(" ", ""):
                return pygame.font.SysFont(avail_name, size, bold=bold)
    return pygame.font.SysFont(None, size, bold=bold)


class FloatingCard:

    def __init__(self, text, current_step, total_steps, screen_w, screen_h, active_cards):
        self.text = text
        self.current_step = current_step
        self.total_steps = total_steps
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Background and text now slowly drift between black and white
        # over time instead of being fixed per-card. Each card gets its
        # own phase offset so they don't all flip in perfect unison.
        self.color_phase = random.uniform(0, math.tau)
        self.accent_color = (232, 178, 92)
        self.shadow_color = (0, 0, 0)
        self.bg_color = (0, 0, 0)
        self.text_color = (255, 255, 255)

        speed_index = self.current_step - 1
        if speed_index < len(TYPE_SPEEDS_MS):
            base_type_speed = TYPE_SPEEDS_MS[speed_index]
        else:
            base_type_speed = DEFAULT_TYPE_SPEED_MS

        self.type_speed_ms = max(1, int(base_type_speed / SPEED_MULTIPLIER))

        self.y = float(self.screen_h)
        self.x = float(self.calculate_random_non_overlapping_x(active_cards))

        self.sway_phase = random.uniform(0, math.tau)

        self.type_index = 0
        self.last_type_time = 0

        self.spawn_time = pygame.time.get_ticks()
        self.next_triggered = False
        self.has_spawned_next = False

        self.font_body = first_available_font(FONT_STACK, BODY_FONT_SIZE, bold=True)

    def calculate_random_non_overlapping_x(self, active_cards):
        margin = 30
        min_x = margin
        max_x = max(min_x, self.screen_w - CARD_WIDTH - margin)

        if not active_cards or max_x <= min_x:
            return random.randint(min_x, max_x)

        padding_x = 25
        padding_y = 30

        valid_candidates = []
        best_candidate = None
        max_min_distance = -1

        for _ in range(100):
            candidate_x = random.randint(min_x, max_x)
            candidate_rect = pygame.Rect(
                candidate_x - padding_x,
                int(self.y) - padding_y,
                CARD_WIDTH + (padding_x * 2),
                CARD_HEIGHT + (padding_y * 2)
            )

            has_collision = False
            current_min_dist = float('inf')

            for card in active_cards:
                other_rect = pygame.Rect(
                    int(card.x), int(card.y), CARD_WIDTH, CARD_HEIGHT
                )
                if candidate_rect.colliderect(other_rect):
                    has_collision = True

                dist = abs(candidate_x - card.x)
                if dist < current_min_dist:
                    current_min_dist = dist

            if not has_collision:
                valid_candidates.append(candidate_x)

            if current_min_dist > max_min_distance:
                max_min_distance = current_min_dist
                best_candidate = candidate_x

        if valid_candidates:
            return random.choice(valid_candidates)

        return best_candidate if best_candidate is not None else random.randint(min_x, max_x)

    def update(self, current_time):
        self.y -= (BASE_FLOAT_SPEED * SPEED_MULTIPLIER)

        is_visible_on_screen = (self.y + CARD_HEIGHT) <= self.screen_h

        if is_visible_on_screen:
            if self.last_type_time == 0:
                self.last_type_time = current_time

            if self.type_index <= len(self.text):
                if current_time - self.last_type_time >= self.type_speed_ms:
                    self.type_index += 1
                    self.last_type_time = current_time

        delay_index = self.current_step - 1
        if delay_index < len(LINE_DELAYS_SECONDS):
            base_delay_ms = LINE_DELAYS_SECONDS[delay_index] * 1000
        else:
            base_delay_ms = 2000

        adjusted_delay_ms = base_delay_ms / SPEED_MULTIPLIER

        if current_time - self.spawn_time >= adjusted_delay_ms:
            self.next_triggered = True

    def get_pop_scale(self, current_time):
        elapsed = current_time - self.spawn_time
        t = elapsed / POP_IN_MS
        if t >= 1.0:
            return 1.0
        return ease_out_back(t)

    def get_sway_offset(self, current_time):
        t = current_time / 1000.0
        return math.sin(t * SWAY_SPEED + self.sway_phase) * SWAY_AMPLITUDE

    def get_card_rect(self, current_time):
        """Rect with the pop-in scale applied, anchored to the card's
        horizontal+vertical center so it grows outward rather than
        sliding around."""
        scale = self.get_pop_scale(current_time)
        w = CARD_WIDTH * scale
        h = CARD_HEIGHT * scale
        cx = self.x + self.get_sway_offset(current_time) + CARD_WIDTH / 2
        cy = self.y + CARD_HEIGHT / 2
        return pygame.Rect(int(cx - w / 2), int(cy - h / 2), int(w), int(h))

    def draw(self, surface):
        current_time = pygame.time.get_ticks()
        t = current_time / 1000.0

        # Slowly cycle bg between black and white; text stays the
        # opposite shade (offset phase by pi) so it's always readable.
        self.bg_color = pulse_black_white(t, self.color_phase)
        self.text_color = pulse_black_white(t, self.color_phase + math.pi)

        rect = self.get_card_rect(current_time)

        shadow_rect = rect.move(*SHADOW_OFFSET)
        pygame.draw.rect(surface, self.shadow_color, shadow_rect, border_radius=CARD_ROUNDING)

        pygame.draw.rect(surface, self.bg_color, rect, border_radius=CARD_ROUNDING)

        inset_rect = rect.inflate(-ACCENT_INSET * 2, -ACCENT_INSET * 2)
        if inset_rect.width > 0 and inset_rect.height > 0:
            pygame.draw.rect(
                surface, self.accent_color, inset_rect,
                width=ACCENT_BORDER_WIDTH, border_radius=max(2, CARD_ROUNDING - ACCENT_INSET)
            )

        pygame.draw.rect(
            surface, self.text_color, rect,
            width=CARD_BORDER_WIDTH, border_radius=CARD_ROUNDING,
        )

        tab_w, tab_h = 46, 6
        tab_rect = pygame.Rect(rect.centerx - tab_w // 2, rect.top - 1, tab_w, tab_h)
        pygame.draw.rect(surface, self.accent_color, tab_rect, border_radius=3)

        typed_text = self.text[: self.type_index]
        cursor_visible = self.type_index < len(self.text) and (current_time // 420) % 2 == 0
        cursor = "▍" if cursor_visible else " "
        if self.type_index >= len(self.text):
            cursor = ""
        body_str = f"\u201c{typed_text}\u201d{cursor}"

        self.render_centered_wrapped_text(surface, body_str, self.text_color, rect)

    def render_centered_wrapped_text(self, surface, text, color, rect):
        max_width = rect.width - 48
        if max_width <= 0:
            return
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if self.font_body.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

        line_height = self.font_body.get_linesize()
        total_text_height = len(lines) * line_height

        start_y = rect.centery - total_text_height / 2

        for i, line in enumerate(lines):
            line_surf = self.font_body.render(line, True, color)
            line_x = rect.centerx - line_surf.get_width() / 2
            line_y = start_y + (i * line_height)
            surface.blit(line_surf, (line_x, line_y))

    def is_off_screen(self):
        return self.y + CARD_HEIGHT < 0


class BinaryDinoCard(FloatingCard):

    GLOW_LOW = (0, 190, 90)
    GLOW_HIGH = (110, 255, 170)

    def __init__(self, screen_w, screen_h, active_cards):
        super().__init__("DINO", len(LYRICS) + 1, len(LYRICS) + 1, screen_w, screen_h, active_cards)
        self.bg_color = (8, 10, 9)
        self.text_color = (0, 255, 70)
        self.accent_color = (0, 255, 70)
        self.shadow_color = (0, 0, 0)
        self.font_pixel = pygame.font.SysFont("Courier", 10, bold=True)

        self.chars_0 = {
            "green": self.font_pixel.render("0", True, (255, 105, 180)),   # Hot Pink petals
            "dark": self.font_pixel.render("0", True, (34, 139, 34)),      # Forest Green stem
            "eye": self.font_pixel.render("0", True, (255, 215, 0)),       # Gold center
            "white": self.font_pixel.render("0", True, (255, 255, 255)),
        }

        self.chars_1 = {
            "green": self.font_pixel.render("1", True, (255, 182, 193)),   # Light Pink petals
            "dark": self.font_pixel.render("1", True, (50, 205, 50)),      # Lime Green stem
            "eye": self.font_pixel.render("1", True, (255, 255, 102)),     # Bright Yellow center
            "white": self.font_pixel.render("1", True, (255, 255, 255)),
        }

        self.DINO_HEAD = [
            "..........XXX...........",
            "..........XXX...........",
            "........XXXXXXX.........",
            "........XXXXXXX.........",
            "......XXXXXEXXXXX.......",
            "......XXXXEEEXXXX.......",
            "......XXXXXEXXXXX.......",
            "........XXXXXXX.........",
            "........XXXXXXX.........",
            "..........XXX...........",
            "..........XXX...........",
        ]

        self.DINO_BODY = [
            "...........XX...........",
            "...........XX...........",
            "...........XX...........",
            ".........11XXXX.........",
            ".......1111XXXXXX.......",
            "......11111XXXXXXX......",
            ".......1111XXXXXX.......",
            ".........11XXXX.........",
            "...........XX...........",
            "...........XX...........",
            "...........X............",
            "...........X............",
            "...........X............",
        ]


    def _pulse_color(self, t):
        blend = (math.sin(t * 3.0) + 1) / 2
        return tuple(
            int(self.GLOW_LOW[i] + (self.GLOW_HIGH[i] - self.GLOW_LOW[i]) * blend)
            for i in range(3)
        )

    def draw(self, surface):
        current_time = pygame.time.get_ticks()
        t = current_time / 1000.0
        rect = self.get_card_rect(current_time)

        shadow_rect = rect.move(*SHADOW_OFFSET)
        pygame.draw.rect(surface, self.shadow_color, shadow_rect, border_radius=CARD_ROUNDING)

        pygame.draw.rect(surface, self.bg_color, rect, border_radius=CARD_ROUNDING)

        glow = self._pulse_color(t)
        pygame.draw.rect(
            surface, glow, rect,
            width=CARD_BORDER_WIDTH, border_radius=CARD_ROUNDING,
        )
        inset_rect = rect.inflate(-ACCENT_INSET * 2, -ACCENT_INSET * 2)
        if inset_rect.width > 0 and inset_rect.height > 0:
            pygame.draw.rect(
                surface, glow, inset_rect,
                width=ACCENT_BORDER_WIDTH, border_radius=max(2, CARD_ROUNDING - ACCENT_INSET)
            )

        head_bob = math.sin(t * 12.0) * 8.0
        body_bounce = math.sin(t * 12.0 - 0.4) * 2.0

        cell_size = 9
        base_x = rect.x + 50
        base_y = rect.y + 90

        bin_shift = current_time // 70

        for r, row in enumerate(self.DINO_HEAD):
            for c, char in enumerate(row):
                if char == ".":
                    continue

                type_key = "green"
                if char == "E":
                    type_key = "eye"
                elif char == "T":
                    type_key = "white"

                use_one = ((r * 5 + c + bin_shift) % 2) == 0
                font_surf = self.chars_1[type_key] if use_one else self.chars_0[type_key]

                pos_x = base_x + (c * cell_size)
                pos_y = base_y + (r * cell_size) + head_bob

                if (
                    rect.left + 10 < pos_x < rect.right - 15
                    and rect.top + 10 < pos_y < rect.bottom - 15
                ):
                    surface.blit(font_surf, (pos_x, pos_y))

        head_height_offset = len(self.DINO_HEAD) * cell_size

        for r, row in enumerate(self.DINO_BODY):
            for c, char in enumerate(row):
                if char == ".":
                    continue

                type_key = "green" if char == "X" else "dark"

                use_one = ((r * 5 + c + bin_shift) % 2) == 0
                font_surf = self.chars_1[type_key] if use_one else self.chars_0[type_key]

                pos_x = base_x + (c * cell_size)
                pos_y = base_y + head_height_offset + (r * cell_size) + body_bounce

                if (
                    rect.left + 10 < pos_x < rect.right - 15
                    and rect.top + 10 < pos_y < rect.bottom - 15
                ):
                    surface.blit(font_surf, (pos_x, pos_y))

        scan_color = (0, max(0, self.bg_color[1] - 4), 0)
        for scan_y in range(rect.top + 4, rect.bottom - 4, 4):
            pygame.draw.line(surface, scan_color, (rect.left + 4, scan_y), (rect.right - 4, scan_y), 1)


def main():
    info = pygame.display.Info()
    screen_w = info.current_w
    screen_h = info.current_h

    flags = pygame.NOFRAME
    screen = pygame.display.set_mode((screen_w, screen_h), flags)

    try:
        from ctypes import windll

        hwnd = pygame.display.get_wm_info()["window"]
        windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)

        extended_style = windll.user32.GetWindowLongW(hwnd, -20)
        windll.user32.SetWindowLongW(hwnd, -20, extended_style | 0x80000)

        r, g, b = TRANSPARENT_KEY
        color_key = r | (g << 8) | (b << 16)
        windll.user32.SetLayeredWindowAttributes(
            hwnd, color_key, 0, 0x00000001
        )
    except Exception as e:
        print(f"Transparency Initialization Notice: {e}")

    clock = pygame.time.Clock()
    cards = []
    current_index = 0

    def spawn_next():
        nonlocal current_index
        if current_index < len(LYRICS):
            new_card = FloatingCard(
                text=LYRICS[current_index],
                current_step=current_index + 1,
                total_steps=len(LYRICS) + 1,
                screen_w=screen_w,
                screen_h=screen_h,
                active_cards=cards,
            )
            cards.append(new_card)
            current_index += 1
        elif current_index == len(LYRICS):
            dino_card = BinaryDinoCard(
                screen_w=screen_w,
                screen_h=screen_h,
                active_cards=cards,
            )
            cards.append(dino_card)
            current_index += 1

    spawn_next()

    running = True
    while running:
        current_time = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                running = False

        screen.fill(TRANSPARENT_KEY)

        for card in list(cards):
            card.update(current_time)

            if card.next_triggered and not card.has_spawned_next:
                card.has_spawned_next = True
                spawn_next()

            card.draw(screen)

            if card.is_off_screen():
                cards.remove(card)

        pygame.display.flip()
        clock.tick(60)

        if not cards and current_index > len(LYRICS):
            running = False

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
