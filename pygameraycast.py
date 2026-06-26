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
            [1, 1, 1, 2, 1, 1, 1, 1, 1],
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
    def __init__(self, texture_manager: Textures):
        self.maptile_size = 32
        self.textures = texture_manager

        half_h = SCREEN_HEIGHT // 2
        self.ceil_gradient = pygame.Surface((1, half_h)).convert()
        self.floor_gradient = pygame.Surface((1, half_h)).convert()

        for y in range(half_h):
            floor_dist = (self.maptile_size * half_h) / max(1, (half_h - y))
            ceiling_dist = ((self.maptile_size * 1.5) * half_h) / max(1, (half_h - y))
            floor_shade = max(0.001, min(1.0, 1.0 - (floor_dist / 150.0)))
            ceiling_shade = max(0.001, min(1.0, 1.0 - (ceiling_dist / 150.0)))

            self.ceil_gradient.set_at((0, y), (int(5 * ceiling_shade), int(5 * ceiling_shade), int(5 * ceiling_shade)))
            self.floor_gradient.set_at((0, y), (int(5 * floor_shade), int(5 * floor_shade), int(5 * floor_shade)))

        self.ceil_surf = pygame.transform.scale(self.ceil_gradient, (SCREEN_WIDTH, SCREEN_HEIGHT // 2))
        self.floor_surf = pygame.transform.scale(self.floor_gradient, (SCREEN_WIDTH, SCREEN_HEIGHT // 2))
        self.floor_surf = pygame.transform.flip(self.floor_surf, False, True)

    def draw_walls(self, screen, col_index: int, corrected_dist: int, total_rays: int, wall_id: int, hit_offset: float,  hit_side: int):
        corrected_dist = max(0.1, corrected_dist)

        line_height = int((self.maptile_size * SCREEN_HEIGHT) / corrected_dist)

        start_y = (SCREEN_HEIGHT // 2) - (line_height // 2)
        draw_start = max(0, start_y)
        draw_end = min(SCREEN_HEIGHT, start_y + line_height)
        draw_height = max(1, draw_end - draw_start)
        col_width = SCREEN_WIDTH // total_rays

        shade = max(0.01, min(1.0, 1.0 - (corrected_dist / 150)))
        if hit_side == 1:
            shade *= 0.60

        col_surf = self.textures.get_column(wall_id, hit_offset, col_width + 1, line_height, draw_height, shade)
        screen.blit(col_surf, (col_index * col_width, draw_start))

    def draw_sprites(self, screen, sprites: list, player, z_buffer: list):
        col_width = SCREEN_WIDTH // player.rays

        def dist(s):
            return (s.x - player.pos_x) ** 2 + (s.y - player.pos_y) ** 2
        sorted_sprites = sorted(sprites, key=dist, reverse=True)
        player_angle_rad = math.radians(player.angle)

        for sprite in sorted_sprites:
            dx = sprite.x - player.pos_x
            dy = sprite.y - player.pos_y

            cos_a = math.cos(player_angle_rad)
            sin_a = math.sin(player_angle_rad)
            cam_depth = dx * cos_a + dy * sin_a
            cam_x = -dx * sin_a + dy * cos_a


            if cam_depth <= 0.1:
                continue

            shade = max(0.01, min(1.0, 1.0 - (cam_depth / 150)))
            shade_byte = int(shade * 255)

            fov_rad = math.radians(player.fov)
            proj_plane = (SCREEN_WIDTH / 2) / math.tan(fov_rad / 2)
            screen_x = int((SCREEN_WIDTH / 2) + (cam_x / cam_depth) * proj_plane)
            aspect_ratio = sprite.texture.get_width() / sprite.texture.get_height()
            sprite_height = int((self.maptile_size * SCREEN_HEIGHT / cam_depth) * sprite.scale)
            sprite_width = int(sprite_height * aspect_ratio)
            floor_offset = 48
            draw_top = (SCREEN_HEIGHT // 2) + (self.maptile_size * SCREEN_HEIGHT / (2 * cam_depth)) - sprite_height + floor_offset
            col_start = screen_x - sprite_width // 2
            col_end = screen_x + sprite_width // 2

            for col in range(col_start, col_end):
                if col <0 or col >= SCREEN_WIDTH:
                    continue

                z_index = col // col_width
                if z_index < 0 or z_index >= len(z_buffer) or z_buffer[z_index] < cam_depth:
                    continue

                tex_x = int((col - col_start) / sprite_width * sprite.texture.get_width())
                tex_strip = sprite.texture.subsurface(pygame.Rect(tex_x, 0, 1, sprite.texture.get_height()))
                scaled_strip = pygame.transform.scale(tex_strip, (1, max(1, sprite_height))).convert_alpha()
                scaled_strip.fill((shade_byte, shade_byte, shade_byte), special_flags=pygame.BLEND_RGBA_MULT)
                screen.blit(scaled_strip, (col, draw_top))

class Player:
    def __init__(self, gamemap: Gamemap, world: World):
        self.z_buffer = None
        self.world = world
        self.pos_x = 48
        self.pos_y = 48
        self.angle = 45
        self.fov = 70
        self.speed = 1
        self.rot_speed = 8
        self.gamemap = gamemap
        self.max_distance = self.gamemap.map_cols + self.gamemap.map_rows // 2
        self.rays = 200

    def move(self, keys, dt):
        speed = self.speed * dt * FPS
        angle_rad = math.radians(self.angle)
        dx = math.cos(angle_rad) * speed
        dy = math.sin(angle_rad) * speed

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

    def rotate(self, keys, dt):
        rot_speed = self.rot_speed * dt * FPS
        if keys[pygame.K_a]:
            self.angle = (self.angle - rot_speed) % 360
        if keys[pygame.K_d]:
            self.angle = (self.angle + rot_speed) % 360

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

    def cast_rays(self, screen):
        start_angle = self.angle - (self.fov / 2)
        angle_step = self.fov / (self.rays - 1) if self.rays > 1 else 0

        screen.blit(self.world.ceil_surf, (0, 0))
        screen.blit(self.world.floor_surf, (0, SCREEN_HEIGHT // 2))

        self.z_buffer = []

        for i in range(self.rays):
            ray_angle = math.radians(start_angle + i * angle_step)
            perp_dist, wall_id, hit_offset, hit_side = self._cast_single_ray_dda(ray_angle)
            camera_angle = ray_angle - math.radians(self.angle)
            perp_dist *= math.cos(camera_angle)

            self.z_buffer.append(perp_dist)

            self.world.draw_walls(screen, i, perp_dist, self.rays, wall_id, hit_offset, hit_side)

    def draw(self, screen):
        pass

class Sprite:
    def __init__(self, x: float, y: float, texture: pygame.Surface, scale: float = 1.0, vert_offset: float = 0.0):
        self.x = x
        self.y = y
        self.texture = texture
        self.scale = scale
        self.vert_offset = vert_offset


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
        self.texture_manager.register(1, "assets/wall1.jpg") #texture 1
        self.texture_manager.register(2, "assets/yapdollar.png") #texture 2
        self.world = World(self.texture_manager)
        self.player = Player(self.gamemap, self.world)

        sprite_tex = pygame.image.load("assets/sprite.png").convert_alpha()
        self.sprites = [
            Sprite(80, 80, sprite_tex),
            Sprite(144, 80, sprite_tex),
        ]

    def event(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def update(self, keys, dt):
        self.player.rotate(keys, dt)
        self.player.move(keys, dt)

    def draw(self):
        self.screen.fill((0, 0, 0))

        self.player.cast_rays(self.screen)

        self.world.draw_sprites(self.screen, self.sprites, self.player, self.player.z_buffer)

        fps_text = self.text_fps.render(f'{int(self.clock.get_fps())} FPS', True, TEXT_COLOR)
        pos_text = self.text_pos.render(f'X {int(self.player.pos_x)}  Y {int(self.player.pos_y)}', True, TEXT_COLOR)
        self.screen.blit(fps_text, (700, 30))
        self.screen.blit(pos_text, (700, 55))

        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            keys = pygame.key.get_pressed()
            self.event()
            self.update(keys, dt)
            self.draw()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()