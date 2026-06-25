import math
import sys
import pygame

pygame.init()

WIN_TITLE = "raycasting in pygame"
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
WALL_COLOR = (61, 16, 18)
TEXT_COLOR = (0, 255, 0)
FPS = 30

class Textures:
    DEF_COLORS = {
        1: (61, 16, 18),
        2: (0, 0, 0),
        3: (255, 255, 255)
    }
    DEF_COLOR = (80, 80, 80)

    def __init__(self, texture_width: int = 64, texture_height: int = 64):
        self.texture_width = texture_width
        self.texture_height = texture_height
        self._textures: dict[int, pygame.Surface] = {}

    def register(self, wall_id: int, image_path: str) -> bool:
        try:
            raw = pygame.image.load(image_path).convert()
            scaled = pygame.transform.scale(raw, (self.texture_width, self.texture_height))
            self._textures[wall_id] = scaled
            return True
        except (pygame.error, FileNotFoundError) as exc:
            print(f"[TextureManager] Could not load '{image_path}': {exc}. "
                  f"Using default color for wall_id={wall_id}")
            self._textures[wall_id] = self._make_fallback(wall_id)
            return False

    def get_column(self, wall_id: int, hit_offset: float, col_width: int, wall_height: int, draw_y: int, shade: float) -> pygame.Surface:
        texture = self._textures.get(wall_id)
        if texture is None:
            texture = self._make_fallback(wall_id)
            self._textures[wall_id] = texture

        tex_x = int(hit_offset * self.texture_width) % self.texture_width
        tex_strip = texture.subsurface(pygame.Rect(tex_x, 0, 1, self.texture_height))

        if wall_height > SCREEN_HEIGHT:
            crop_ratio = (wall_height - SCREEN_HEIGHT) / (2 * wall_height)
            tex_top = int(crop_ratio * self.texture_height)
            tex_bottom = self.texture_height - tex_top
            tex_top = max(0, min(tex_top, self.texture_height - 1))
            tex_bottom = max(tex_top + 1, min(tex_bottom, self.texture_height))
            tex_strip = tex_strip.subsurface(pygame.Rect(0, tex_top, 1, tex_bottom - tex_top))


        column = pygame.transform.scale(tex_strip, (col_width, draw_y))
        shade_byte = max(0, min(255, int(shade * 255)))
        column.fill((shade_byte, shade_byte, shade_byte), special_flags=pygame.BLEND_RGBA_MULT)

        return column

    def _make_fallback(self, wall_id: int) -> pygame.Surface:
        color = self.DEF_COLORS.get(wall_id, self.DEF_COLOR)
        surf = pygame.Surface((self.texture_width, self.texture_height))
        surf.fill(color)

        return surf



class Gamemap:
    def __init__(self):
        self.maptile_size = 32
        self.wall_color = WALL_COLOR
        self.gamemap = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 1, 0, 0, 0, 0, 1],
            [1, 0, 0, 1, 0, 0, 0, 0, 1],
            [1, 0, 1, 1, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 1, 1, 1, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]

        self.map_rows = len(self.gamemap)
        self.map_cols = len(self.gamemap[0]) if self.map_rows > 0 else 0

    def collision(self, x, y):
        grid_x = int(x // self.maptile_size)
        grid_y = int(y // self.maptile_size)
        if 0 <= grid_x < self.map_cols and 0 <= grid_y < self.map_rows:
            return self.gamemap[grid_y][grid_x] != 0
        return True  # out of bounds is a wall

    def wall_id_at(self, grid_x, grid_y) -> int:
        if 0 <= grid_x < self.map_cols and 0 <= grid_y < self.map_rows:
            return self.gamemap[grid_y][grid_x]
        return 1

class World:
    def __init__(self, texture_mangager: Textures):
        self.maptile_size = 32
        self.textures = texture_mangager

        half_h = SCREEN_HEIGHT // 2
        self.ceil_gradient = pygame.Surface((1, half_h)).convert()
        self.floor_gradient = pygame.Surface((1, half_h)).convert()

        for y in range(half_h):
            floor_dist = (self.maptile_size * half_h) / max(1, (half_h - y))
            ceiling_dist = ((self.maptile_size * 1.5) * half_h) / max(1, (half_h - y))
            floor_shade = max(0.01, min(1.0, 1.0 - (floor_dist / 100.0)))
            ceiling_shade = max(0.01, min(1.0, 1.0 - (ceiling_dist / 100.0)))

            self.ceil_gradient.set_at((0, y), (int(150 * ceiling_shade), int(149 * ceiling_shade), int(141 * ceiling_shade)))
            self.floor_gradient.set_at((0, y), (int(47 * floor_shade), int(45 * floor_shade), int(28 * floor_shade)))



    def draw_walls(self, screen, col_index: int, corrected_dist: int, total_rays: int, wall_id: int, hit_offset: float,  hit_side: int):
        corrected_dist = max(0.1, corrected_dist)

        line_height = int((self.maptile_size * SCREEN_HEIGHT) / corrected_dist)

        start_y = (SCREEN_HEIGHT // 2) - (line_height // 2)
        draw_start = max(0, start_y)
        draw_end = min(SCREEN_HEIGHT, start_y + line_height)
        draw_height = max(1, draw_end - draw_start)
        col_width = SCREEN_WIDTH // total_rays

        if draw_start > 0:
            # Ceiling
            ceil_slice = self.ceil_gradient.subsurface(pygame.Rect(0, 0, 1, draw_start))
            ceil_scaled = pygame.transform.scale(ceil_slice, (col_width + 1, draw_start))
            screen.blit(ceil_scaled, (col_index * col_width, 0))

            # Floor
            floor_slice = self.floor_gradient.subsurface(pygame.Rect(0, 0, 1, draw_start))
            floor_scaled = pygame.transform.scale(floor_slice, (col_width + 1, draw_start))
            floor_scaled = pygame.transform.flip(floor_scaled, False, True)
            screen.blit(floor_scaled, (col_index * col_width, draw_end))

        shade = max(0.01, min(1.0, 1.0 - (corrected_dist / 100.0)))
        if hit_side == 1:
            shade *= 0.60

        col_surf = self.textures.get_column(wall_id, hit_offset, col_width + 1, line_height, draw_height, shade)
        screen.blit(col_surf, (col_index * col_width, draw_start))



class Player:
    def __init__(self, gamemap: Gamemap, world: World):
        self.world = world
        self.pos_x = 48
        self.pos_y = 48
        self.angle = 45
        self.fov = 70
        self.speed = 1
        self.rot_speed = 8
        self.gamemap = gamemap
        self.max_distance = 400
        self.step_size = 0.5
        self.rays = 200

    def move(self, keys):
        angle_rad = math.radians(self.angle)
        dx = math.cos(angle_rad) * self.speed
        dy = math.sin(angle_rad) * self.speed

        if keys[pygame.K_w]:
            new_x = self.pos_x + dx
            new_y = self.pos_y + dy
            if not self.gamemap.collision(new_x, new_y):
                self.pos_x = new_x
                self.pos_y = new_y

        if keys[pygame.K_s]:
            new_x = self.pos_x - dx
            new_y = self.pos_y - dy
            if not self.gamemap.collision(new_x, new_y):
                self.pos_x = new_x
                self.pos_y = new_y

    def rotate(self, keys):
        if keys[pygame.K_a]:
            self.angle = (self.angle - self.rot_speed) % 360
        if keys[pygame.K_d]:
            self.angle = (self.angle + self.rot_speed) % 360

    def _cast_single_ray_dda(self, ray_angle: float):
       tile = self.gamemap.maptile_size
       px = self.pos_x / tile
       py = self.pos_y / tile
       cos_a = math.cos(ray_angle)
       sin_a = math.sin(ray_angle)

       map_x = int(px)
       map_y = int(py)

       step_x = 1 if cos_a >= 0 else -1
       step_y = 1 if sin_a >= 0 else -1

       delta_x = abs(1.0 / cos_a) if cos_a != 0 else math.inf
       delta_y = abs(1.0 / sin_a) if sin_a != 0 else math.inf


       if cos_a >= 0:
           side_dist_x = (map_x + 1.0 - px) * delta_x
       else:
           side_dist_x = (px - map_x) * delta_x

       if sin_a >= 0:
           side_dist_y = (map_y + 1.0 - py) * delta_y
       else:
           side_dist_y = (py - map_y) * delta_y

       for _ in range(self.max_distance):
           if side_dist_x < side_dist_y:
               side_dist_x += delta_x
               map_x += step_x
               hit_side = 0
           else:
               side_dist_y += delta_y
               map_y += step_y
               hit_side = 1

           wall_id = self.gamemap.wall_id_at(map_x, map_y)
           if wall_id != 0:
               break
       else:
           return self.max_distance, 1, 0.0, 0

       if hit_side == 0:
           perp_dist = (side_dist_x - delta_x) * tile
       else:
           perp_dist = (side_dist_y - delta_y) * tile

       if hit_side == 0:
           true_dist = side_dist_x - delta_x
           hit_y_tile = py + true_dist * sin_a
           hit_offset = hit_y_tile - math.floor(hit_y_tile)
       else:
           true_dist = side_dist_y - delta_y
           hit_x_tile = px + true_dist * cos_a
           hit_offset = hit_x_tile - math.floor(hit_x_tile)

       if hit_side == 0 and cos_a > 0:
           hit_offset = 1.0 - hit_offset
       if hit_side == 1 and sin_a < 0:
           hit_offset = 1.0 - hit_offset

       hit_offset = max(0.0, min(hit_offset, 0.9999))

       return perp_dist, wall_id, hit_offset, hit_side


    def _compute_hit_offset(self, hit_x: float, hit_y: float, ray_angle: float) -> float:
        tile_size = self.gamemap.maptile_size
        frac_x = (hit_x % tile_size) / tile_size
        frac_y = (hit_y % tile_size) / tile_size
        cos_a = math.cos(ray_angle)
        sin_a = math.sin(ray_angle)

        if cos_a != 0:
            dist_v = abs(((round(hit_x / tile_size) * tile_size) - hit_x) / cos_a)
        else:
            dist_v = float('inf')

        if sin_a != 0:
            dist_h = abs(((round(hit_y / tile_size) * tile_size) - hit_y) / sin_a)
        else:
            dist_h = float('inf')

        if dist_h < dist_v:
            return frac_x
        else:
            return frac_y

    def cast_rays(self, screen):
        start_angle = self.angle - (self.fov / 2)
        angle_step = self.fov / (self.rays - 1) if self.rays > 1 else 0

        for i in range(self.rays):
            ray_angle = math.radians(start_angle + i * angle_step)
            perp_dist, wall_id, hit_offset, hit_side = self._cast_single_ray_dda(ray_angle)
            camera_angle = ray_angle - math.radians(self.angle)
            perp_dist *= math.cos(camera_angle)

            self.world.draw_walls(screen, i, perp_dist, self.rays, wall_id, hit_offset, hit_side)

    def draw(self, screen):
        pass


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
        pygame.display.set_caption(WIN_TITLE)
        self.clock = pygame.time.Clock()
        self.text_fps = pygame.font.SysFont('EASVHS Regular', 18)
        self.text_pos = pygame.font.SysFont('EASVHS Regular', 18)
        self.running = True
        self.gamemap = Gamemap()
        self.texture_manager = Textures(texture_width=64, texture_height=64)
        self.texture_manager.register(1, "assets/yapdollar.png") #texture 1
        self.texture_manager.register(2, "assets/image2.png") #texture 2
        self.world = World(self.texture_manager)
        self.player = Player(self.gamemap, self.world)

        self.floor_ceiling_shade = pygame.surface.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        half_h = SCREEN_HEIGHT // 2

        for y in range (half_h):
            distance = half_h / max(0.001, (half_h - y))
            shade = max(0.1, min(1.0, 1.0 - (distance / 12.0)))
            shade_alpha = 255 - int(shade * 255)
            pygame.draw.line(self.floor_ceiling_shade, (0, 0, 0, shade_alpha), (0, y), (SCREEN_WIDTH, y))
            pygame.draw.line(self.floor_ceiling_shade, (0, 0, 0, shade_alpha), (0, SCREEN_HEIGHT - 1 - y), (SCREEN_WIDTH, SCREEN_HEIGHT - 1 - y))

    def event(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, keys):
        self.player.rotate(keys)
        self.player.move(keys)

    def draw(self):
        self.screen.fill((0, 0, 0))

        self.player.cast_rays(self.screen)
        self.player.draw(self.screen)

        fps_text = self.text_fps.render(f'{int(self.clock.get_fps())} FPS', True, TEXT_COLOR)
        pos_text = self.text_pos.render(f'X {int(self.player.pos_x)}  Y {int(self.player.pos_y)}', True, TEXT_COLOR)
        self.screen.blit(fps_text, (700, 30))
        self.screen.blit(pos_text, (700, 55))

        pygame.display.flip()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            keys = pygame.key.get_pressed()
            self.event()
            self.update(keys)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()