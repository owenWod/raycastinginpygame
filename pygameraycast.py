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


class Gamemap:
    def __init__(self):
        self.maptile_size = 32
        self.map_size = 6
        self.wall_color = WALL_COLOR
        self.gamemap = [
            [1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 0, 1],
            [1, 0, 0, 1, 0, 1],
            [1, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1],
        ]

    def draw_tiles(self, screen):
        pygame.draw.rect(screen, (0, 0, 0), (0, 0, self.maptile_size * self.map_size, self.maptile_size * self.map_size))
        for row_idx, row in enumerate(self.gamemap):
            for col_idx, cell in enumerate(row):
                x = col_idx * self.maptile_size
                y = row_idx * self.maptile_size
                color = self.wall_color if cell == 1 else (255, 255, 255)

                pygame.draw.rect(screen, color, (x, y, self.maptile_size - 0.5, self.maptile_size - 0.5))

    def collision(self, x, y):
        grid_x = int(x // self.maptile_size)
        grid_y = int(y // self.maptile_size)
        if 0 <= grid_x < self.map_size and 0 <= grid_y < self.map_size:
            return self.gamemap[grid_y][grid_x] == 1
        return True  # out of bounds is a wall

class World:
    def __init__(self):
        self.maptile_size = 32
        self.map_size = 5
        self.wall_color = WALL_COLOR
        self.shadow_color = (175, 175, 175)
    def draw_walls(self, screen, i, distance, ray_angle, player_angle, total_rays):
        relative_angle = ray_angle - math.radians(player_angle)
        corrected_dist = distance * math.cos(relative_angle)

        if corrected_dist <= 0.1:
            corrected_dist = 0.1
        line_height = int((self.maptile_size * SCREEN_HEIGHT) / corrected_dist)

        if line_height > SCREEN_HEIGHT:
            line_height = SCREEN_HEIGHT

        start_y = (SCREEN_HEIGHT // 2) - (line_height // 2)
        col_width = SCREEN_WIDTH // total_rays
        col_x = i * col_width
        shade_amt = max(0.1, min(1.0, 1.0 - (corrected_dist / 400)))
        shaded_color = (
            int(self.wall_color[0] * shade_amt),
            int(self.wall_color[1] * shade_amt),
            int(self.wall_color[2] * shade_amt)
        )

        pygame.draw.rect(screen, shaded_color, (int(col_x), int(start_y), int(col_width) + 1, int(line_height)))

class Player:
    def __init__(self, gamemap):
        self.world = World()
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

    def cast_rays(self, screen):
        start_angle = self.angle - (self.fov / 2)
        angle_step = self.fov / (self.rays - 1) if self.rays > 1 else 0

        pygame.draw.rect(screen, (150, 149, 141), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT // 2)) #ceiling
        pygame.draw.rect(screen, (47, 45, 28), (0, SCREEN_HEIGHT // 2, SCREEN_WIDTH, SCREEN_HEIGHT // 2)) #floor

        ray_endpoints = []

        for i in range(self.rays):
            ray_angle = math.radians(start_angle + (i * angle_step))
            line_length = 0
            end_x, end_y = self.pos_x, self.pos_y

            while line_length < self.max_distance:
                end_x = self.pos_x + line_length * math.cos(ray_angle)
                end_y = self.pos_y + line_length * math.sin(ray_angle)
                if self.gamemap.collision(end_x, end_y):
                    break
                line_length += self.step_size

            ray_endpoints.append((end_x, end_y))
            self.world.draw_walls(screen, i, line_length, ray_angle, self.angle, self.rays)

        self.gamemap.draw_tiles(screen)

        for rx, ry in ray_endpoints:
            pygame.draw.line(screen, "red", (int(self.pos_x), int(self.pos_y)), (int(rx), int(ry)), 1) #draws rays on minimap for visualization

    def draw(self, screen):
        pygame.draw.circle(screen, 'green', (self.pos_x, self.pos_y), 4) #draws player circle


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
        pygame.display.set_caption(WIN_TITLE)
        self.clock = pygame.time.Clock()
        self.text_fps = pygame.font.Font(None, 30)
        self.text_pos = pygame.font.Font(None, 30)
        self.running = True
        self.gamemap = Gamemap()
        self.player = Player(self.gamemap)

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
        pos_text = self.text_pos.render(f'X: {int(self.player.pos_x)}  Y: {int(self.player.pos_y)}', True, TEXT_COLOR)
        self.screen.blit(fps_text, (700, 30))
        self.screen.blit(pos_text, (670, 55))

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