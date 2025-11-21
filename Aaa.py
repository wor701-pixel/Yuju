"""
Asteroids — Pydroid 3 v2.2
- Fullscreen horizontal con joystick y botones A/B
- Auto-fire con A (mantener presionado)
- Botón B = ESCUDO temporal (3s, recarga 8s)
- Flash local en explosiones (no flash de pantalla completa)
- Reinicio táctil: tocar botón A cuando GAME OVER reinicia el juego
- Música y efectos opcionales: music.ogg/music.mp3, sfx_shot.ogg, sfx_explosion.ogg, shield.ogg
Guardar como: asteroids_pydroid_v2_2.py
Ejecutar en Pydroid 3: python asteroids_pydroid_v2_2.py
"""
import math
import random
import sys
import time
import os
import pygame
from pygame import gfxdraw

# ---------- Config ----------
FPS = 60
MAX_PARTICLES = 350
BULLET_SPEED = 680
BULLET_LIFETIME = 1.1
ASTEROID_MIN_SPEED = 28
ASTEROID_MAX_SPEED = 110
ASTEROID_SIZES = {3: 56, 2: 34, 1: 18}
SHIP_RADIUS = 13

# ---------- Helpers ----------
def clamp(v, a, b):
    return max(a, min(b, v))

def lerp(a, b, t):
    return a + (b - a) * t

def angle_to_vec(a):
    return math.cos(a), math.sin(a)

def wrap(pos, w, h):
    x, y = pos
    return x % w, y % h

# ---------- Virtual joystick (touch) ----------
class VirtualJoystick:
    def __init__(self, rect, outer_radius=None, knob_radius=None):
        self.rect = pygame.Rect(rect)
        self.outer_radius = outer_radius if outer_radius else min(self.rect.w, self.rect.h)//2
        self.knob_radius = knob_radius if knob_radius else self.outer_radius//2
        self.center = (self.rect.x + self.rect.w//2, self.rect.y + self.rect.h//2)
        self.active = False
        self.pointer_id = None
        self.knob_pos = self.center
        self.value = (0.0, 0.0)  # x,y normalized (-1..1)
        self.deadzone = 0.12
        self.screen_size = (self.rect.w, self.rect.h)

    def handle_fingerdown_norm(self, fid, x, y, screen_w, screen_h):
        px, py = int(x * screen_w), int(y * screen_h)
        if self.rect.collidepoint(px, py):
            self.active = True
            self.pointer_id = fid
            self.knob_pos = (px, py)
            self._update_value()
            return True
        return False

    def handle_fingerup(self, fid):
        if self.pointer_id == fid:
            self.active = False
            self.pointer_id = None
            self.knob_pos = self.center
            self.value = (0.0, 0.0)
            return True
        return False

    def handle_fingermotion_norm(self, fid, x, y, screen_w, screen_h):
        if self.pointer_id != fid:
            return False
        px, py = int(x * screen_w), int(y * screen_h)
        dx = px - self.center[0]
        dy = py - self.center[1]
        d = math.hypot(dx, dy)
        if d > self.outer_radius:
            dx = dx / d * self.outer_radius
            dy = dy / d * self.outer_radius
        self.knob_pos = (self.center[0] + dx, self.center[1] + dy)
        self._update_value()
        return True

    def handle_mouse_down(self, mx, my):
        if self.rect.collidepoint(mx, my):
            self.active = True
            self.pointer_id = 'mouse'
            self.knob_pos = (mx, my)
            self._update_value()
            return True
        return False

    def handle_mouse_up(self):
        if self.pointer_id == 'mouse':
            self.active = False
            self.pointer_id = None
            self.knob_pos = self.center
            self.value = (0.0, 0.0)
            return True
        return False

    def handle_mouse_motion(self, mx, my):
        if self.pointer_id != 'mouse':
            return False
        dx = mx - self.center[0]
        dy = my - self.center[1]
        d = math.hypot(dx, dy)
        if d > self.outer_radius:
            dx = dx / d * self.outer_radius
            dy = dy / d * self.outer_radius
        self.knob_pos = (self.center[0] + dx, self.center[1] + dy)
        self._update_value()
        return True

    def _update_value(self):
        dx = self.knob_pos[0] - self.center[0]
        dy = self.knob_pos[1] - self.center[1]
        nx = dx / self.outer_radius
        ny = dy / self.outer_radius
        # invert Y so up = negative
        ny = -ny
        # deadzone
        if math.hypot(nx, ny) < self.deadzone:
            self.value = (0.0, 0.0)
        else:
            self.value = (clamp(nx, -1, 1), clamp(ny, -1, 1))

    def draw(self, surf):
        ox, oy = self.center
        surf_r = pygame.Surface((self.outer_radius*2+4, self.outer_radius*2+4), pygame.SRCALPHA)
        pygame.gfxdraw.filled_circle(surf_r, self.outer_radius+2, self.outer_radius+2, self.outer_radius, (30,30,40,120))
        pygame.gfxdraw.aacircle(surf_r, self.outer_radius+2, self.outer_radius+2, self.outer_radius, (180,180,200,120))
        surf.blit(surf_r, (ox - self.outer_radius - 2, oy - self.outer_radius - 2))
        kx, ky = int(self.knob_pos[0]), int(self.knob_pos[1])
        kr = self.knob_radius
        base_col = (230,230,255) if self.active else (210,210,230)
        pygame.gfxdraw.filled_circle(surf, kx, ky, kr, (*base_col,220))
        pygame.gfxdraw.aacircle(surf, kx, ky, kr, (255,255,255,200))

    def set_screen_size(self, size):
        self.screen_size = size
        self.center = (self.rect.x + self.rect.w//2, self.rect.y + self.rect.h//2)
        self.knob_pos = self.center

# ---------- Simple button ----------
class Button:
    def __init__(self, rect, label, color=(255,200,80), small=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.active = False
        self.small = small
        self.color = color

    def contains_point(self, x, y):
        return self.rect.collidepoint(x, y)

    def draw(self, surf, font):
        r = self.rect
        surf_r = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        base_alpha = 220 if self.active else 160
        pygame.gfxdraw.filled_circle(surf_r, r.w//2, r.h//2, r.w//2, (*self.color, base_alpha))
        pygame.gfxdraw.aacircle(surf_r, r.w//2, r.h//2, r.w//2, (255,255,255,180))
        surf.blit(surf_r, (r.x, r.y))
        txt = font.render(self.label, True, (20,20,30))
        surf.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))

# ---------- Particles (lightweight pool) ----------
class Particle:
    __slots__ = ('x','y','vx','vy','life','ttl','size','col')
    def __init__(self,x,y,vx,vy,ttl,size,col=(255,200,120)):
        self.x=x;self.y=y;self.vx=vx;self.vy=vy;self.life=0;self.ttl=ttl;self.size=size;self.col=col
    def update(self,dt):
        self.life+=dt
        self.x+=self.vx*dt; self.y+=self.vy*dt
        return self.life<self.ttl

# ---------- Game objects (lightweight) ----------
class Ship:
    def __init__(self,w,h):
        self.pos = [w*0.5, h*0.5]
        self.vel = [0.0,0.0]
        self.angle = -math.pi/2
        self.dead = False
        self.invul = 0.0

    def respawn(self,w,h):
        self.pos=[w*0.5,h*0.5];self.vel=[0,0];self.angle=-math.pi/2;self.dead=False;self.invul=2.0

    def update(self,dt,joy,particles,w,h):
        jx, jy = joy.value
        mag = math.hypot(jx,jy)
        if mag>0.12:
            target_angle = math.atan2(jy, jx) + math.pi/2
            diff = (target_angle - self.angle)
            while diff > math.pi: diff -= 2*math.pi
            while diff < -math.pi: diff += 2*math.pi
            self.angle += diff * clamp(12*dt, 0, 1)
            ax, ay = angle_to_vec(self.angle)
            t = clamp(mag,0,1)
            self.vel[0] += ax * 200 * t * dt
            self.vel[1] += ay * 200 * t * dt
            # flames
            bx = self.pos[0] - ax*14
            by = self.pos[1] - ay*14
            for _ in range(3):
                self._emit_flame(particles, bx, by, ax, ay)
        # small brake when joystick pushed backwards for feeling
        if mag>0.12 and jx*math.cos(self.angle) + jy*math.sin(self.angle) < -0.25:
            self.vel[0] *= 0.995
            self.vel[1] *= 0.995
        # friction
        self.vel[0]*=0.997
        self.vel[1]*=0.997
        speed = math.hypot(self.vel[0],self.vel[1])
        if speed>480:
            s = 480/speed
            self.vel[0]*=s;self.vel[1]*=s
        self.pos[0]+=self.vel[0]*dt; self.pos[1]+=self.vel[1]*dt
        self.pos = list(wrap(self.pos,w,h))
        if self.invul>0:
            self.invul-=dt

    def _emit_flame(self, particles, bx, by, ax, ay):
        vx = -ax*random.uniform(40,160) + random.uniform(-30,30)
        vy = -ay*random.uniform(40,160) + random.uniform(-30,30)
        col = (255, 160 + random.randint(0,80), 60)
        particles.append(Particle(bx, by, vx, vy, 0.32, random.uniform(1,3), col))

    def draw(self,surf):
        visible = True
        if self.invul>0:
            visible = (int(self.invul * 6) % 2 == 0)
        if not visible:
            return
        x,y = int(self.pos[0]), int(self.pos[1])
        ax,ay = angle_to_vec(self.angle)
        left = angle_to_vec(self.angle - 2.6)
        right = angle_to_vec(self.angle + 2.6)
        pts = [(x + ax*14, y + ay*14),(x+left[0]*10,y+left[1]*10),(x+right[0]*10,y+right[1]*10)]
        pygame.gfxdraw.filled_trigon(surf, int(pts[0][0]),int(pts[0][1]),int(pts[1][0]),int(pts[1][1]),int(pts[2][0]),int(pts[2][1]), (120,210,255))
        pygame.gfxdraw.aatrigon(surf, int(pts[0][0]),int(pts[0][1]),int(pts[1][0]),int(pts[1][1]),int(pts[2][0]),int(pts[2][1]), (255,255,255))

class Bullet:
    __slots__=('x','y','vx','vy','life')
    def __init__(self,x,y,vx,vy):
        self.x=x;self.y=y;self.vx=vx;self.vy=vy;self.life=0
    def update(self,dt,w,h):
        self.life+=dt; self.x+=self.vx*dt; self.y+=self.vy*dt
        self.x,self.y = wrap((self.x,self.y),w,h)
        return self.life < BULLET_LIFETIME
    def draw(self,surf):
        pygame.gfxdraw.filled_circle(surf,int(self.x),int(self.y),2,(255,255,255))
        pygame.gfxdraw.filled_circle(surf,int(self.x),int(self.y),5,(255,255,255,30))
        pygame.gfxdraw.aacircle(surf,int(self.x),int(self.y),5,(255,255,255,60))

class Asteroid:
    def __init__(self,w,h,size=3,pos=None):
        if pos is None:
            side = random.choice(['left','right','top','bottom'])
            if side=='left': pos=( -10, random.uniform(0,h))
            elif side=='right': pos=(w+10, random.uniform(0,h))
            elif side=='top': pos=(random.uniform(0,w), -10)
            else: pos=(random.uniform(0,w), h+10)
        self.x, self.y = pos
        self.size = size
        self.radius = ASTEROID_SIZES[size]
        ang = random.random()*math.tau
        speed = random.uniform(ASTEROID_MIN_SPEED, ASTEROID_MAX_SPEED) * (1.0 + (3-size)*0.15)
        self.vx = math.cos(ang)*speed; self.vy = math.sin(ang)*speed
        self.rot = random.uniform(-1,1)
        self.angle = random.uniform(0,math.tau)
        self.shape = self._gen_shape()
    def _gen_shape(self):
        pts=[]
        steps = max(6, int(self.radius/4)+3)
        for i in range(steps):
            a = (i/steps)*math.tau
            r = self.radius * random.uniform(0.7,1.12)
            pts.append((math.cos(a)*r, math.sin(a)*r))
        return pts
    def update(self,dt,w,h):
        self.angle += self.rot*dt
        self.x += self.vx*dt; self.y += self.vy*dt
        self.x,self.y = wrap((self.x,self.y),w,h)
    def draw(self,surf):
        pts = []
        for px,py in self.shape:
            ang = math.atan2(py,px) + self.angle
            r = math.hypot(px,py)
            pts.append((int(self.x + math.cos(ang)*r), int(self.y + math.sin(ang)*r)))
        pygame.gfxdraw.filled_polygon(surf, pts, (150,150,160))
        pygame.gfxdraw.aapolygon(surf, pts, (255,255,255))

# ---------- Main Game ----------
class Game:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except Exception:
            pass
        info = pygame.display.Info()
        self.W, self.H = info.current_w, info.current_h
        self.screen = pygame.display.set_mode((self.W,self.H), pygame.FULLSCREEN)
        pygame.display.set_caption('Asteroids - Pydroid v2.2')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)
        self.bigfont = pygame.font.SysFont(None, 56)

        pad = int(min(self.W, self.H)*0.26)
        margin = int(min(self.W, self.H)*0.035)
        offset_y = int(self.H * 0.08)
        joy_rect = (margin, self.H - pad - margin - offset_y, pad, pad)
        self.joystick = VirtualJoystick(joy_rect, outer_radius=int(pad*0.48), knob_radius=int(pad*0.18))
        self.joystick.set_screen_size((self.W,self.H))

        btn_size = int(pad*0.42)
        right_x = self.W - margin - btn_size
        center_y = self.H - pad//2 - margin - offset_y
        self.btn_b = Button((right_x - btn_size - 18, center_y - btn_size - 6, btn_size, btn_size), 'B', color=(120,160,255))
        self.btn_a = Button((right_x, center_y, btn_size, btn_size), 'A', color=(120,255,140))
        self.btn_pause = Button((right_x - btn_size - 18 - 10, center_y + btn_size//2 - 18, int(btn_size*0.6), int(btn_size*0.6)), 'II', color=(200,200,255), small=True)

        # state
        self.ship = Ship(self.W, self.H)
        self.particles = []
        self.bullets = []
        self.asteroids = []
        self.local_flashes = []   # (x,y,ttl,max_ttl,radius)
        self.score = 0
        self.lives = 3
        self.level = 1
        self.last_shot = 0
        self.pause = False
        self.music_on = True
        self.spawn_level()

        # combo / streak
        self.combo = 0
        self.combo_timer = 0.0
        self.combo_timeout = 2.2

        # extra life thresholds
        self.next_extra_life_score = 10000

        # shield (B)
        self.shield_active = False
        self.shield_timer = 0.0
        self.shield_duration = 3.0
        self.shield_cooldown = 8.0
        self.shield_cd_timer = 0.0   # cooldown remaining (0 = ready)

        # start screen
        self.started = False

        # sounds
        self.snd_shot = None
        self.snd_explosion = None
        self.snd_shield = None
        self._load_audio()
        
    def _load_audio(self):
        # 🔊 Nueva ruta personalizada para sonidos en Pydroid 3
        sound_path = '/storage/emulated/0/2025/asteroid/sounds/'

        # --- Música de fondo ---
        possible_music = [sound_path + f for f in ['music.ogg', 'music.mp3', 'music-mc.mp3', 'bg_loop.ogg']]
        for p in possible_music:
            if os.path.exists(p):
                try:
                    pygame.mixer.music.load(p)
                    pygame.mixer.music.set_volume(0.8)
                    pygame.mixer.music.play(-1)
                    print('🎵 Reproduciendo música:', p)
                    break
                except Exception as e:
                    print('⚠️ No se pudo reproducir', p, e)

        # --- Efectos de sonido ---
        if pygame.mixer.get_init():
            try:
                if os.path.exists(sound_path + 'sfx_shot.ogg'):
                    self.snd_shot = pygame.mixer.Sound(sound_path + 'sfx_shot.ogg')
                if os.path.exists(sound_path + 'sfx_explosion.ogg'):
                    self.snd_explosion = pygame.mixer.Sound(sound_path + 'sfx_explosion.ogg')
                if os.path.exists(sound_path + 'shield.ogg'):
                    self.snd_shield = pygame.mixer.Sound(sound_path + 'shield.ogg')
            except Exception as e:
                print('Error cargando efectos de sonido:', e)

    def spawn_level(self):
        self.asteroids = []
        count = 2 + self.level
        for _ in range(count):
            a = Asteroid(self.W, self.H, size=3)
            if math.hypot(a.x - self.ship.pos[0], a.y - self.ship.pos[1]) < 120:
                a = Asteroid(self.W, self.H, size=3)
            self.asteroids.append(a)

    def _make_local_flash(self, x, y, max_ttl=0.18, radius=60):
        self.local_flashes.append([x, y, max_ttl, max_ttl, radius])

    def split_asteroid(self,a):
        # small local flash near asteroid
        self._make_local_flash(a.x, a.y, max_ttl=0.16, radius=max(36, a.radius*1.2))
        if a.size>1:
            for _ in range(2):
                na = Asteroid(self.W,self.H,size=a.size-1,pos=(a.x,a.y))
                self.asteroids.append(na)
        base = 10*(4-a.size)
        bonus = int(base * (0.1 * (self.combo)))
        self.score += base + bonus
        self.combo += 1
        self.combo_timer = self.combo_timeout
        for _ in range(18):
            self.particles.append(Particle(a.x,a.y,random.uniform(-160,160),random.uniform(-160,160),0.9,2,(255,180,80)))
        if self.snd_explosion:
            try: self.snd_explosion.play()
            except: pass
        if self.score >= self.next_extra_life_score:
            self.lives += 1
            self.next_extra_life_score += 10000

    def fire(self):
        now = time.time()
        if now - self.last_shot < 0.12:
            return
        self.last_shot = now
        ax,ay = angle_to_vec(self.ship.angle)
        bx = self.ship.pos[0] + ax*14
        by = self.ship.pos[1] + ay*14
        vx = self.ship.vel[0] + ax*BULLET_SPEED
        vy = self.ship.vel[1] + ay*BULLET_SPEED
        self.bullets.append(Bullet(bx,by,vx,vy))
        for _ in range(4):
            self.particles.append(Particle(bx,by,-ax*random.uniform(60,220)+random.uniform(-20,20),-ay*random.uniform(60,220)+random.uniform(-20,20),0.25,1,(255,255,200)))
        if self.snd_shot:
            try: self.snd_shot.play()
            except: pass

    def activate_shield(self):
        if self.shield_active or self.shield_cd_timer>0:
            return
        self.shield_active = True
        self.shield_timer = self.shield_duration
        self.shield_cd_timer = self.shield_cooldown
        if self.snd_shield:
            try: self.snd_shield.play()
            except: pass

    def update(self,dt):
        if not self.started:
            if self.shield_cd_timer > 0:
                self.shield_cd_timer = max(0.0, self.shield_cd_timer - dt)
            return
        if self.pause: return
        # auto-fire if A held
        if self.btn_a.active and not self.ship.dead and self.lives>0:
            self.fire()

        # update shield timers
        if self.shield_active:
            self.shield_timer -= dt
            if self.shield_timer <= 0:
                self.shield_active = False
                self.shield_timer = 0.0
        else:
            if self.shield_cd_timer > 0:
                self.shield_cd_timer = max(0.0, self.shield_cd_timer - dt)

        self.ship.update(dt,self.joystick,self.particles,self.W,self.H)
        self.bullets = [b for b in self.bullets if b.update(dt,self.W,self.H)]
        for a in self.asteroids: a.update(dt,self.W,self.H)

        # update local flashes
        lf_new = []
        for f in self.local_flashes:
            f[2] -= dt
            if f[2] > 0:
                lf_new.append(f)
        self.local_flashes = lf_new

        alive=[]
        for p in self.particles:
            if p.update(dt): alive.append(p)
        self.particles = alive[:MAX_PARTICLES]

        # bullet collisions
        for b in self.bullets[:]:
            for a in self.asteroids[:]:
                if math.hypot(b.x - a.x, b.y - a.y) < a.radius:
                    try: self.bullets.remove(b)
                    except: pass
                    try: self.asteroids.remove(a)
                    except: pass
                    self.split_asteroid(a)
                    break

        # ship collisions (respect shield)
        if not self.ship.dead and self.ship.invul<=0 and not self.shield_active:
            for a in self.asteroids:
                if math.hypot(self.ship.pos[0]-a.x, self.ship.pos[1]-a.y) < (a.radius + SHIP_RADIUS - 5):
                    for _ in range(26): self.particles.append(Particle(self.ship.pos[0],self.ship.pos[1],random.uniform(-140,140),random.uniform(-140,140),1.1,3,(255,160,60)))
                    self.lives-=1
                    self.ship.dead = True
                    self.ship.invul = 2.0
                    self.ship.pos = [-999,-999]
                    pygame.time.set_timer(pygame.USEREVENT, 800)
                    self.combo = 0
                    self.combo_timer = 0.0
                    break
        else:
            if self.shield_active:
                for a in self.asteroids[:]:
                    if math.hypot(self.ship.pos[0]-a.x, self.ship.pos[1]-a.y) < (a.radius + SHIP_RADIUS):
                        try: self.asteroids.remove(a)
                        except: pass
                        self.split_asteroid(a)

        # level complete
        if not self.asteroids:
            self.level += 1
            global ASTEROID_MIN_SPEED, ASTEROID_MAX_SPEED
            ASTEROID_MIN_SPEED = min(120, ASTEROID_MIN_SPEED * (1.0 + 0.02 * self.level))
            ASTEROID_MAX_SPEED = min(220, ASTEROID_MAX_SPEED * (1.0 + 0.02 * self.level))
            self.spawn_level()

        # combo timer
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

    def _draw_text_shadow(self, surf, text, x, y, font, color=(255,255,255)):
        sh = font.render(text, True, (0,0,0))
        surf.blit(sh, (x+2, y+2))
        tx = font.render(text, True, color)
        surf.blit(tx, (x, y))

    def draw(self):
        surf = pygame.Surface((self.W,self.H))
        # background gradient
        for i in range(self.H):
            t = i/self.H
            r = int(6 + 18*t)
            g = int(10 + 8*t)
            b = int(20 + 40*t)
            pygame.gfxdraw.hline(surf, 0, self.W, i, (r,g,b))
        # stars
        t = pygame.time.get_ticks()*0.00008
        for i in range(140):
            x = (i*73 + math.sin(t*(0.2+i*0.01))*40) % self.W
            y = (i*47 + math.cos(t*(0.3+i*0.01))*22) % self.H
            pygame.gfxdraw.pixel(surf, int(x), int(y), (140,140,160))
        # draw asteroids, bullets, ship, particles
        for a in self.asteroids: a.draw(surf)
        for b in self.bullets: b.draw(surf)
        if not self.ship.dead: self.ship.draw(surf)
        for p in self.particles:
            alpha = int(255 * (1 - p.life/p.ttl))
            col = (p.col[0], p.col[1], p.col[2], alpha)
            pygame.gfxdraw.filled_circle(surf, int(p.x), int(p.y), max(1,int(p.size)), col)

        # draw local flashes (soft)
        for fx, fy, ttl, max_ttl, radius in self.local_flashes:
            k = ttl / max_ttl
            a = int(180 * k)
            r = int(radius * (1.0 + (1.0 - k)*0.5))
            temp = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
            pygame.gfxdraw.filled_circle(temp, r+2, r+2, r, (255,255,255,a))
            surf.blit(temp, (int(fx - r - 2), int(fy - r - 2)), special_flags=pygame.BLEND_RGBA_ADD)

        # if shield active draw halo
        if self.shield_active and not self.ship.dead:
            x,y = int(self.ship.pos[0]), int(self.ship.pos[1])
            r = int(SHIP_RADIUS * 2.6)
            temp = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
            pygame.gfxdraw.filled_circle(temp, r+2, r+2, r, (80,160,255,80))
            pygame.gfxdraw.aacircle(temp, r+2, r+2, r, (180,220,255,160))
            surf.blit(temp, (x - r - 2, y - r - 2))

        # HUD
        self._draw_text_shadow(surf, f"Score: {self.score}", 12, 12, self.font)
        self._draw_text_shadow(surf, f"Lives: {self.lives}", 12, 36, self.font)
        self._draw_text_shadow(surf, f"Lvl: {self.level}", 12, 60, self.font)
        if self.combo > 1:
            self._draw_text_shadow(surf, f"Combo x{self.combo}!", self.W//2 - 80, 24, self.font, color=(255,220,120))

        # shield HUD (right top)
        shield_status = "LISTO" if (not self.shield_active and self.shield_cd_timer<=0) else ("ACTIVO" if self.shield_active else f"CARGANDO {int(self.shield_cd_timer)+1}s")
        self._draw_text_shadow(surf, f"ESCUDO: {shield_status}", self.W - 220, 12, self.font, color=(180,220,255))

        # controls UI
        self.joystick.draw(surf)
        self.btn_b.draw(surf,self.font)
        self.btn_a.draw(surf,self.font)
        self.btn_pause.draw(surf,self.font)

        # start/pause/game over overlays
        if not self.started:
            t = self.bigfont.render("Toca A para empezar", True, (255,255,255))
            surf.blit(t, (self.W//2 - t.get_width()//2, self.H//2 - t.get_height()//2))
        if self.pause and self.started:
            overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            overlay.fill((10,10,12,160))
            surf.blit(overlay, (0,0))
            t = self.bigfont.render("PAUSA", True, (255,255,255))
            surf.blit(t, (self.W//2 - t.get_width()//2, self.H//2 - t.get_height()//2))
        if self.lives<=0 and self.started:
            go = self.bigfont.render("GAME OVER", True, (255,80,80))
            surf.blit(go, (self.W//2 - go.get_width()//2, self.H//2 - 40))
            sc = self.font.render("Toca A para reiniciar", True, (255,255,255))
            surf.blit(sc, (self.W//2 - sc.get_width()//2, self.H//2 + 24))

        self.screen.blit(surf, (0,0))
        pygame.display.flip()

    def run(self):
        running = True
        last = time.time()
        while running:
            dt = clamp(time.time() - last, 0, 1/20)
            last = time.time()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q): running = False
                    if event.key == pygame.K_SPACE:
                        self.fire()
                        self.started = True
                    if event.key == pygame.K_p:
                        if self.started:
                            self.pause = not self.pause
                    if event.key == pygame.K_r:
                        # keep keyboard restart for completeness but primary is touch A
                        self.__init__()
                    if event.key == pygame.K_b:
                        if not self.shield_active and self.shield_cd_timer<=0:
                            self.activate_shield()
                elif event.type == pygame.FINGERDOWN:
                    fid = event.finger_id
                    mx, my = int(event.x * self.W), int(event.y * self.H)
                    if self.joystick.rect.collidepoint(mx, my):
                        self.joystick.pointer_id = fid
                        self.joystick.active = True
                        self.joystick.knob_pos = (mx, my)
                        self.joystick._update_value()
                    else:
                        if self.btn_a.contains_point(mx, my):
                            self.btn_a.active = True
                            # START or FIRE or RESTART depending on state
                            if self.lives <= 0:
                                # Restart the game when touching A after GAME OVER
                                self.__init__()
                            else:
                                self.started = True
                                self.fire()
                        if self.btn_b.contains_point(mx, my):
                            self.btn_b.active = True
                            if not self.shield_active and self.shield_cd_timer <= 0:
                                self.activate_shield()
                        if self.btn_pause.contains_point(mx, my):
                            self.btn_pause.active = True
                            if self.started:
                                self.pause = not self.pause
                elif event.type == pygame.FINGERUP:
                    fid = event.finger_id
                    if self.joystick.pointer_id == fid:
                        self.joystick.handle_fingerup(fid)
                    mx, my = int(event.x * self.W), int(event.y * self.H)
                    if self.btn_a.contains_point(mx, my): self.btn_a.active = False
                    if self.btn_b.contains_point(mx, my): self.btn_b.active = False
                    if self.btn_pause.contains_point(mx, my): self.btn_pause.active = False
                elif event.type == pygame.FINGERMOTION:
                    fid = event.finger_id
                    mx, my = int(event.x * self.W), int(event.y * self.H)
                    if self.joystick.pointer_id == fid:
                        self.joystick.knob_pos = (mx, my)
                        self.joystick._update_value()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx,my = event.pos
                    if self.joystick.handle_mouse_down(mx,my): pass
                    else:
                        if self.btn_a.contains_point(mx,my):
                            self.btn_a.active=True
                            if self.lives <= 0:
                                self.__init__()   # restart by mouse click on A
                            else:
                                self.started = True
                                self.fire()
                        if self.btn_b.contains_point(mx,my):
                            self.btn_b.active=True
                            if not self.shield_active and self.shield_cd_timer <= 0:
                                self.activate_shield()
                        if self.btn_pause.contains_point(mx,my):
                            self.btn_pause.active=True
                            if self.started:
                                self.pause = not self.pause
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.joystick.handle_mouse_up()
                    mx,my = event.pos
                    if self.btn_a.contains_point(mx,my): self.btn_a.active=False
                    if self.btn_b.contains_point(mx,my): self.btn_b.active=False
                    if self.btn_pause.contains_point(mx,my): self.btn_pause.active=False
                elif event.type == pygame.MOUSEMOTION:
                    mx,my = event.pos
                    self.joystick.handle_mouse_motion(mx,my)
                elif event.type == pygame.USEREVENT:
                    pygame.time.set_timer(pygame.USEREVENT, 0)
                    if self.lives>0:
                        self.ship.respawn(self.W,self.H)
                        self.ship.dead=False

            keys = pygame.key.get_pressed()
            if keys[pygame.K_z] or keys[pygame.K_SPACE]:
                if not self.btn_a.active:
                    self.fire()
                    self.started = True

            self.update(dt)
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()

if __name__=='__main__':
    Game().run()
