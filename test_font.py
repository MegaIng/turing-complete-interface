import pygame as pg

pg.init()

FONT_SIZE = 30

W, H = 18*FONT_SIZE, 14*FONT_SIZE
FLAGS = 0


font = pg.font.Font("turing_complete_interface/Px437_IBM_BIOS.ttf", FONT_SIZE)

screen = pg.display.set_mode((W, H), FLAGS)
W, H = screen.get_size()

clock = pg.time.Clock()
running = True
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False
        elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            running = False
        elif event.type == pg.VIDEORESIZE:
            screen = pg.display.set_mode(event.size, FLAGS)
            W, H = screen.get_size()
    # Logic
    dt = clock.tick()

    # Render
    screen.fill((130, 160, 120))
    for y in range(14):
        for x in range(18):
            if (x == y == 0):
                continue
            t = font.render(chr(y * 18 + x), True, (0, 0, 0))
            screen.blit(t, (x * (FONT_SIZE), y * (FONT_SIZE)))

    pg.display.update()
    pg.display.set_caption(f"FPS: {clock.get_fps():.2f}")
