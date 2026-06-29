import math
import sys
import pygame
import numpy as np

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
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 1],
            [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 2],
            [2, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1],
            [1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            [3, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1],
        ]

        self.map_rows = len(self.gamemap)
        self.map_cols = len(self.gamemap[0]) if self.map_rows > 0 else 0

    def collision(self, x, y, sprites=None, sprite_buffer=16):
        grid_x = int(x // self.maptile_size)
        grid_y = int(y // self.maptile_size)

        if 0 <= grid_x < self.map_cols and 0 <= grid_y < self.map_rows:
            if self.gamemap[grid_y][grid_x] != 0:
                return True
        else:
            return True

        if sprites:
            for sprite in sprites:
                dx = x - sprite.x
                dy = y - sprite.y
                if dx*dx + dy*dy < sprite_buffer**2:
                    return True

        return False

    def wall_id_at(self, grid_x, grid_y):
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

    def draw_sprites(self, screen, sprites, player, z_buffer):
        col_width = SCREEN_WIDTH // player.rays
        player_angle_rad = math.radians(player.angle)

        for sprite in sorted(sprites, key=lambda s: (s.x - player.pos_x) ** 2 + (s.y - player.pos_y) ** 2, reverse=True):
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
            falloff = 0.99
            sprite_height = max(sprite.min_height, int((self.maptile_size * SCREEN_HEIGHT / cam_depth ** falloff) * sprite.scale))
            sprite_width = int(sprite_height * aspect_ratio)
            floor_offset = 48
            draw_top = int((SCREEN_HEIGHT // 2) + (self.maptile_size * SCREEN_HEIGHT / (2 * cam_depth)) - sprite_height + floor_offset + sprite.vert_offset)
            col_start = screen_x - sprite_width // 2

            render_h = max(1, min(sprite_height, SCREEN_HEIGHT * 3))
            render_w = max(1, min(sprite_width, SCREEN_WIDTH * 3))

            scaled = pygame.transform.scale(sprite.texture, (render_w, render_h)).convert_alpha()
            scaled.fill((shade_byte, shade_byte, shade_byte, 255), special_flags=pygame.BLEND_RGBA_MULT)

            for col in range(max(0, col_start), min(SCREEN_WIDTH, col_start + sprite_width)):
                z_index = col // col_width
                if z_index < 0 or z_index >= len(z_buffer) or z_buffer[z_index] < cam_depth:
                    continue

                src_x = max(0, min(int((col - col_start) / max(1, sprite_width) * render_w), render_w - 1))
                screen.blit(scaled, (col, draw_top), area=pygame.Rect(src_x, 0, 1, render_h))


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
        self.max_distance = self.gamemap.map_cols + self.gamemap.map_rows // 3
        self.rays = 200

    def move(self, keys, dt, sprites=None):
        speed = self.speed * dt * FPS
        angle_rad = math.radians(self.angle)
        dx = math.cos(angle_rad) * speed
        dy = math.sin(angle_rad) * speed

        if keys[pygame.K_w]:
            new_x = self.pos_x + dx
            new_y = self.pos_y + dy
            if not self.gamemap.collision(new_x, new_y, sprites):
                self.pos_x = new_x
                self.pos_y = new_y

        if keys[pygame.K_s]:
            new_x = self.pos_x - dx
            new_y = self.pos_y - dy
            if not self.gamemap.collision(new_x, new_y, sprites):
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
    def __init__(self, x: float, y: float, texture: pygame.Surface, scale: float = 1.0, vert_offset: float = 0.0, min_height: int = 0, interactable: bool=False):
        self.x = x
        self.y = y
        self.texture = texture
        self.scale = scale
        self.vert_offset = vert_offset
        self.min_height = min_height
        self.interactable = interactable


class Game:
    def __init__(self):
        pygame.mixer.init(48000, size=16, channels=2, buffer=1024)
        bg_music = pygame.mixer.Sound("assets/How to Disappear into Strings - Radiohead (128k).wav")
        bg_music.set_volume(0.03)
        self.item_collect_sfx = pygame.mixer.Sound("assets/chime.wav")
        self.item_collect_sfx.set_volume(0.1)

        music_channel = pygame.mixer.Channel(0)
        self.sfx_channel = pygame.mixer.Channel(1)

        music_channel.play(bg_music, loops=-1)

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
        pygame.display.set_caption(WIN_TITLE)
        self.clock = pygame.time.Clock()

        self.text_fps = pygame.font.SysFont('EASVHS Regular', 18)
        self.text_pos = pygame.font.SysFont('EASVHS Regular', 18)
        self.text_bones_collected = pygame.font.SysFont('EASVHS Regular', 20)
        self.text_itemcollect = pygame.font.SysFont('EASVHS Regular', 32)
        self.collect_msg_timer = 0

        self.running = True
        self.gamemap = Gamemap()

        raw_floor = pygame.image.load("assets/floor.jpg").convert()
        raw_floor = pygame.transform.scale(raw_floor, (64, 64))
        self.floor_tex_array = pygame.surfarray.array3d(raw_floor)
        self.floor_buf = np.zeros((SCREEN_WIDTH, SCREEN_HEIGHT // 2, 3), dtype=np.uint8)

        self.texture_manager = Textures(texture_width=128, texture_height=128)
        self.texture_manager.register(1, "assets/wall1.jpg")
        self.texture_manager.register(2, "assets/wall2.jpg")
        self.texture_manager.register(3, "assets/wall3.jpg")
        self.world = World(self.texture_manager)
        self.player = Player(self.gamemap, self.world)

        sprite_tex = pygame.image.load("assets/sprite.png").convert_alpha()
        sprite_tex_bone = pygame.image.load("assets/bone.png").convert_alpha()

        self.sprites = [
            Sprite(80, 80, sprite_tex, scale=1, vert_offset=-40, min_height=0),
            Sprite(144, 80, sprite_tex, scale=1, vert_offset=-40, min_height=0),
            Sprite(188, 120, sprite_tex_bone, scale=0.6, vert_offset=-50, min_height=0, interactable=True),
        ]

        self.bones_collected = 0
        self.interact_pressed = False

    def event(self):
        self.interact_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self.interact_pressed = True

    def interact(self, interact_range=32):
        if not self.interact_pressed:
            return
        for sprite in self.sprites[:]:
            if not sprite.interactable:
                continue
            dx = self.player.pos_x - sprite.x
            dy = self.player.pos_y - sprite.y
            if dx*dx + dy*dy < interact_range**2:
                self.sprites.remove(sprite)
                self.bones_collected += 1
                self.sfx_channel.play(self.item_collect_sfx)
                self.collect_msg_timer = 2.0

    def update(self, keys, dt):
        self.player.rotate(keys, dt)
        self.player.move(keys, dt, self.sprites)
        self.interact()
        if self.collect_msg_timer > 0:
            self.collect_msg_timer -= dt

    def draw_floor_cast(self, screen, player):
        half_h = SCREEN_HEIGHT // 2
        tile = self.gamemap.maptile_size
        fov_rad = math.radians(player.fov)
        start_angle_rad = math.radians(player.angle - player.fov / 2)
        angle_step_rad = fov_rad / (SCREEN_WIDTH - 1)

        col_angles = start_angle_rad + np.arange(SCREEN_WIDTH, dtype=np.float32) * angle_step_rad
        ray_dirs_x = np.cos(col_angles)
        ray_dirs_y = np.sin(col_angles)

        camera_angles = col_angles - math.radians(player.angle)
        cos_camera = np.cos(camera_angles).reshape(1, -1)

        pos_x = player.pos_x / tile
        pos_y = player.pos_y / tile
        tex_w = self.floor_tex_array.shape[0]
        tex_h = self.floor_tex_array.shape[1]

        rows = np.arange(1, half_h + 1, dtype=np.float32).reshape(-1, 1)
        row_dist = half_h / rows

        actual_dist = row_dist / cos_camera

        fx = pos_x + actual_dist * ray_dirs_x
        fy = pos_y + actual_dist * ray_dirs_y

        tx = (fx * tex_w).astype(np.int32) % tex_w
        ty = (fy * tex_h).astype(np.int32) % tex_h

        shade = np.clip(1.0 - (row_dist * tile) / 150.0, 0.01, 1.0)
        colors = self.floor_tex_array[tx,ty]
        lit = (colors * shade[:, :, np.newaxis]).astype(np.uint8)

        np.copyto(self.floor_buf, lit.transpose(1, 0, 2))
        pygame.surfarray.blit_array(self.world.floor_surf, self.floor_buf)
        screen.blit(self.world.floor_surf, (0, half_h))

    def draw(self):
        self.screen.fill((0, 0, 0))

        self.draw_floor_cast(self.screen, self.player)

        self.player.cast_rays(self.screen)

        self.world.draw_sprites(self.screen, self.sprites, self.player, self.player.z_buffer)

        bone_text = self.text_bones_collected.render(f'BONES COLLECTED {self.bones_collected}', True, "red")
        fps_text = self.text_fps.render(f'{int(self.clock.get_fps())} FPS', True, TEXT_COLOR)
        pos_text = self.text_pos.render(f'X {int(self.player.pos_x)}  Y {int(self.player.pos_y)}', True, TEXT_COLOR)
        self.screen.blit(fps_text, (710, 30))
        self.screen.blit(pos_text, (690, 55))
        self.screen.blit(bone_text, (600, 80))

        if self.collect_msg_timer > 0:
            text_itemcollect = self.text_itemcollect.render(f"YOU PICKED UP A BONE!", True, "white")
            rect = text_itemcollect.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(text_itemcollect, rect)

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