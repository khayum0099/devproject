Delver's Descent — a single-file Python roguelike dungeon crawler.
Run: python delvers_descent.py
Dependencies: only the Python standard library.
Controls: WASD or HJKL to move, . to wait, i for inventory,
          g to pick up, > to descend stairs, q to quit.
Goal:     Reach the bottom of the dungeon (depth 5) and retrieve the Amulet of Yendor.
"""
import random
import sys
import copy
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

# ============================================================
# Constants & configuration
# ============================================================
DUNGEON_WIDTH = 60
DUNGEON_HEIGHT = 22
MAX_DEPTH = 5
FOV_RADIUS = 6

WALL = "#"
FLOOR = "."
STAIRS_DOWN = ">"
PLAYER = "@"
GOBLIN = "g"
ORC = "o"
TROLL = "T"
SKELETON = "s"
WRAITH = "w"
DRAGON = "D"
AMULET = '"'
POTION = "!"
SWORD = "/"
SHIELD = ")"
ARMOR = "]"
RING = "="
GOLD = "$"
CORPSE = "%"

# Tile colors (ANSI)
COLORS = {
    WALL:      "\033[38;5;240m",
    FLOOR:     "\033[38;5;236m",
    STAIRS_DOWN: "\033[38;5;11m",
    PLAYER:    "\033[38;5;15m",
    GOBLIN:    "\033[38;5;34m",
    ORC:       "\033[38;5;1m",
    TROLL:     "\033[38;5;130m",
    SKELETON:  "\033[38;5;250m",
    WRAITH:    "\033[38;5;99m",
    DRAGON:    "\033[38;5;9m",
    AMULET:    "\033[38;5;226m",
    POTION:    "\033[38;5;91m",
    SWORD:     "\033[38;5;250m",
    SHIELD:    "\033[38;5;250m",
    ARMOR:     "\033[38;5;250m",
    RING:      "\033[38;5;93m",
    GOLD:      "\033[38;5;220m",
    CORPSE:    "\033[38;5;130m",
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# ============================================================
# Data classes
# ============================================================
@dataclass
class Item:
    name: str
    glyph: str
    kind: str  # "weapon", "armor", "shield", "ring", "potion", "misc"
    bonus: int = 0
    value: int = 0
    desc: str = ""
    stackable: bool = False
    qty: int = 1

    def __str__(self):
        return f"{self.name} (+{self.bonus})" if self.bonus else self.name


@dataclass
class Entity:
    name: str
    glyph: str
    x: int
    y: int
    hp: int
    max_hp: int
    attack: int
    defense: int
    xp: int = 0
    level: int = 1
    gold: int = 0
    is_player: bool = False
    inventory: List[Item] = field(default_factory=list)
    equipped: Dict[str, Optional[Item]] = field(
        default_factory=lambda: {"weapon": None, "armor": None, "shield": None, "ring": None}
    )
    sight_radius: int = FOV_RADIUS
    speed: int = 1  # 1 = normal, 2 = moves twice per turn

    def is_alive(self):
        return self.hp > 0

    def power(self):
        atk = self.attack
        if self.equipped.get("weapon"):
            atk += self.equipped["weapon"].bonus
        if self.equipped.get("ring") and "might" in self.equipped["ring"].name.lower():
            atk += 2
        return atk

    def armor_class(self):
        ac = self.defense
        if self.equipped.get("armor"):
            ac += self.equipped["armor"].bonus
        if self.equipped.get("shield"):
            ac += self.equipped["shield"].bonus
        return ac


# ============================================================
# Item factory
# ============================================================
def make_item(kind: str, depth: int = 1) -> Item:
    roll = random.random
    if kind == "weapon":
        table = [("dagger", 1, 3), ("short sword", 2, 6), ("mace", 2, 8),
                 ("long sword", 3, 14), ("war axe", 4, 22), ("great sword", 5, 35)]
        name, bonus, value = random.choice(table[:max(1, depth)])
        return Item(name, SWORD, "weapon", bonus=bonus, value=value,
                    desc=f"A {name} (+{bonus}). Increases attack.")
    if kind == "armor":
        table = [("leather", 1, 5), ("chain mail", 2, 12), ("scale mail", 3, 20),
                 ("plate mail", 4, 35), ("dragon scale", 5, 60)]
        name, bonus, value = random.choice(table[:max(1, depth)])
        return Item(name, ARMOR, "armor", bonus=bonus, value=value,
                    desc=f"{name.title()} (+{bonus}). Increases armor.")
    if kind == "shield":
        bonus = min(depth, 3)
        return Item("wooden shield" if bonus==1 else "iron shield" if bonus==2 else "tower shield",
                    SHIELD, "shield", bonus=bonus, value=bonus*5,
                    desc=f"A shield (+{bonus}). Increases armor.")
    if kind == "ring":
        rings = [("ring of might", "+2 attack"),
                 ("ring of guarding", "+2 armor"),
                 ("ring of sight", "+2 sight radius"),
                 ("ring of swiftness", "moves twice per turn")]
        name, desc = random.choice(rings)
        return Item(name, RING, "ring", bonus=1, value=30, desc=desc)
    if kind == "potion":
        pots = [("healing potion", 15), ("extra healing potion", 30),
                ("greater healing potion", 60)]
        name, heal = random.choice(pots[:max(1, depth-1)] if depth > 1 else pots[:1])
        return Item(name, POTION, "potion", bonus=heal, value=heal,
                    desc=f"Restores {heal} HP.", stackable=True)
    if kind == "gold":
        amount = random.randint(5, 20) * depth
        return Item(f"{amount} gold pieces", GOLD, "misc", value=amount,
                    desc=f"A pile of {amount} gold.", stackable=True, qty=amount)
    if kind == "amulet":
        return Item("Amulet of Yendor", AMULET, "misc", value=1000,
                    desc="The legendary amulet. Bring it to the surface!")
    return Item("rock", "*", "misc", desc="A small rock.")


# ============================================================
# Enemy factory
# ============================================================
def make_enemy(depth: int, x: int, y: int) -> Entity:
    table = []
    if depth == 1: table = [("goblin", GOBLIN, 8, 3, 0, 4)] * 6 + [("skeleton", SKELETON, 10, 3, 1, 6)]
    elif depth == 2: table = [("goblin", GOBLIN, 8, 3, 0, 4)] * 3 + \
                            [("skeleton", SKELETON, 10, 3, 1, 6)] * 3 + \
                            [("orc", ORC, 14, 5, 1, 10)]
    elif depth == 3: table = [("skeleton", SKELETON, 10, 3, 1, 6)] * 2 + \
                            [("orc", ORC, 14, 5, 1, 10)] * 4 + \
                            [("troll", TROLL, 22, 7, 2, 18)]
    elif depth == 4: table = [("orc", ORC, 14, 5, 1, 10)] * 2 + \
                            [("troll", TROLL, 22, 7, 2, 18)] * 3 + \
                            [("wraith", WRAITH, 18, 8, 4, 25)]
    elif depth == 5: table = [("wraith", WRAITH, 18, 8, 4, 25)] * 3 + \
                            [("troll", TROLL, 24, 8, 3, 22)] * 2 + \
                            [("dragon", DRAGON, 40, 12, 6, 80)]
    name, glyph, hp, atk, dfn, xp = random.choice(table)
    return Entity(name=name, glyph=glyph, x=x, y=y,
                  hp=hp, max_hp=hp, attack=atk, defense=dfn, xp=xp)


# ============================================================
# Dungeon generation (rooms + corridors)
# ============================================================
class Dungeon:
    def __init__(self, depth):
        self.depth = depth
        self.w = DUNGEON_WIDTH
        self.h = DUNGEON_HEIGHT
        self.tiles = [[WALL for _ in range(self.w)] for _ in range(self.h)]
        self.rooms = []
        self.items = []
        self.entities = []
        self.stairs = None
        self.amulet_here = False
        self.visible = [[False]*self.w for _ in range(self.h)]
        self.explored = [[False]*self.w for _ in range(self.h)]
        self._generate()

    def _generate(self):
        attempts = 0
        while len(self.rooms) < 8 and attempts < 100:
            attempts += 1
            rw = random.randint(5, 11)
            rh = random.randint(4, 7)
            rx = random.randint(1, self.w - rw - 2)
            ry = random.randint(1, self.h - rh - 2)
            new_room = (rx, ry, rw, rh)
            if any(self._overlap(new_room, r) for r in self.rooms):
                continue
            self._carve_room(new_room)
            if self.rooms:
                self._carve_tunnel(self._center(self.rooms[-1]), self._center(new_room))
            self.rooms.append(new_room)

        # Place stairs in the last room
        sx, sy = self._center(self.rooms[-1])
        self.tiles[sy][sx] = STAIRS_DOWN
        self.stairs = (sx, sy)

        # Place items
        for _ in range(random.randint(3, 6)):
            room = random.choice(self.rooms[:-1])
            x, y = self._random_in_room(room)
            roll = random.random()
            if roll < 0.35: kind = "potion"
            elif roll < 0.55: kind = "gold"
            elif roll < 0.75: kind = "weapon"
            elif roll < 0.88: kind = "armor"
            elif roll < 0.94: kind = "shield"
            else: kind = "ring"
            self.items.append((make_item(kind, self.depth), x, y))

        # Place amulet on depth MAX_DEPTH
        if self.depth == MAX_DEPTH:
            ax, ay = self._center(self.rooms[0])
            self.items.append((make_item("amulet"), ax, ay))
            self.amulet_here = True

        # Place enemies
        n_enemies = 4 + self.depth * 2
        for _ in range(n_enemies):
            room = random.choice(self.rooms[1:])  # don't spawn in the first room (player start)
            x, y = self._random_in_room(room)
            self.entities.append(make_enemy(self.depth, x, y))

    @staticmethod
    def _overlap(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)

    def _carve_room(self, room):
        rx, ry, rw, rh = room
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                self.tiles[y][x] = FLOOR

    def _carve_tunnel(self, a, b):
        ax, ay = a
        bx, by = b
        if random.random() < 0.5:
            self._h_line(ax, bx, ay)
            self._v_line(ay, by, bx)
        else:
            self._v_line(ay, by, ax)
            self._h_line(ax, bx, by)

    def _h_line(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= x < self.w and 0 <= y < self.h:
                self.tiles[y][x] = FLOOR

    def _v_line(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 <= x < self.w and 0 <= y < self.h:
                self.tiles[y][x] = FLOOR

    @staticmethod
    def _center(room):
        rx, ry, rw, rh = room
        return rx + rw // 2, ry + rh // 2

    @staticmethod
    def _random_in_room(room):
        rx, ry, rw, rh = room
        return random.randint(rx, rx + rw - 1), random.randint(ry, ry + rh - 1)

    def tile_at(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.tiles[y][x]
        return WALL

    def is_walkable(self, x, y):
        return self.tile_at(x, y) != WALL

    def compute_fov(self, px, py):
        # Reset visibility
        for y in range(self.h):
            for x in range(self.w):
                self.visible[y][x] = False
        # Simple ray-cast FOV
        for angle_deg in range(0, 360, 3):
            angle = angle_deg * 3.14159265 / 180.0
            dx, dy = (0.0, 0.0)
            step_x, step_y = (0.0, 0.0)
            for step in range(FOV_RADIUS + 1):
                dx = (step + 0.5) * 1.0
                x = int(px + 0.5 + dx * 1.0)
                y = int(py + 0.5 + dx * 0.0)
            # Use Bresenham-style ray cast
            tx, ty = px, py
            for step in range(FOV_RADIUS):
                tx = px + int(round(step * (1.0) * 1.0))
                ty = py + int(round(step * (0.0) * 1.0))
            # Actually use a simpler approach below
        # Simpler & correct: check each tile within radius using line-of-sight
        for y in range(max(0, py - FOV_RADIUS), min(self.h, py + FOV_RADIUS + 1)):
            for x in range(max(0, px - FOV_RADIUS), min(self.w, px + FOV_RADIUS + 1)):
                dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if dist > FOV_RADIUS:
                    continue
                if self._line_of_sight(px, py, x, y):
                    self.visible[y][x] = True
                    self.explored[y][x] = True

    def _line_of_sight(self, x0, y0, x1, y1):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        x, y = x0, y0
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            if (x, y) != (x0, y0) and self.tile_at(x, y) == WALL:
                return False
            if (x, y) == (x1, y1):
                return True
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy


# ============================================================
# Game state
# ============================================================
class Game:
    def __init__(self):
        self.player = Entity(
            name="Hero", glyph=PLAYER, x=0, y=0,
            hp=30, max_hp=30, attack=4, defense=0,
            is_player=True, sight_radius=FOV_RADIUS
        )
        self.depth = 1
        self.dungeon = Dungeon(self.depth)
        self._place_player()
        self.messages = []
        self.log("Welcome to Delver's Descent! Find the Amulet of Yendor on level 5.")
        self.log(f"You enter dungeon level {self.depth}.")
        self.fov_dirty = True
        self.turn = 0
        self.game_over = False
        self.won = False

    def _place_player(self):
        rx, ry, rw, rh = self.dungeon.rooms[0]
        self.player.x = rx + rw // 2
        self.player.y = ry + rh // 2

    def log(self, msg):
        self.messages.append(msg)
        if len(self.messages) > 6:
            self.messages = self.messages[-6:]

    # ---- movement & combat ----
    def move_player(self, dx, dy):
        if self.game_over:
            return
        nx, ny = self.player.x + dx, self.player.y + dy
        if not self.dungeon.is_walkable(nx, ny):
            return
        # Check for enemy
        target = next((e for e in self.dungeon.entities
                       if e.is_alive() and e.x == nx and e.y == ny), None)
        if target:
            self._attack(self.player, target)
        else:
            self.player.x, self.player.y = nx, ny
            self._check_pickup()
            self._check_stairs()
        self.fov_dirty = True
        self._end_player_turn()

    def wait(self):
        if self.game_over:
            return
        self.log("You wait.")
        self._end_player_turn()

    def _attack(self, attacker, defender):
        dmg = max(1, attacker.power() - defender.armor_class() + random.randint(-1, 2))
        defender.hp -= dmg
        verb = "smite" if attacker.is_player else "hits"
        self.log(f"{attacker.name} {verb} {defender.name} for {dmg} dmg.")
        if not defender.is_alive():
            self.log(f"The {defender.name} dies!")
            if attacker.is_player:
                self.player.xp += defender.xp
                self.player.gold += random.randint(0, defender.xp)
                self.log(f"+{defender.xp} XP.")
                self._check_level_up()
                # Maybe drop corpse / gold
                if random.random() < 0.25:
                    self.dungeon.items.append((make_item("gold", self.depth), defender.x, defender.y))

    def _check_pickup(self):
        for item, ix, iy in list(self.dungeon.items):
            if ix == self.player.x and iy == self.player.y:
                if item.kind == "misc" and "gold" in item.name:
                    self.player.gold += item.qty
                    self.log(f"You pick up {item.qty} gold.")
                    self.dungeon.items.remove((item, ix, iy))
                else:
                    self.log(f"You see: {item.name}. Press 'g' to pick up.")

    def pickup(self):
        for item, ix, iy in list(self.dungeon.items):
            if ix == self.player.x and iy == self.player.y:
                if item.kind == "misc" and "gold" in item.name:
                    self.player.gold += item.qty
                    self.log(f"You pick up {item.qty} gold.")
                else:
                    self.player.inventory.append(item)
                    self.log(f"Picked up: {item.name}.")
                self.dungeon.items.remove((item, ix, iy))
                return
        self.log("Nothing here to pick up.")

    def _check_stairs(self):
        if (self.player.x, self.player.y) == self.dungeon.stairs:
            self.log("You see stairs leading down. Press '>' to descend.")

    def descend(self):
        if (self.player.x, self.player.y) != self.dungeon.stairs:
            self.log("You are not standing on stairs.")
            return
        if self.depth >= MAX_DEPTH:
            self.log("The stairs are blocked. You have reached the bottom!")
            return
        self.depth += 1
        self.dungeon = Dungeon(self.depth)
        self._place_player()
        self.log(f"You descend to dungeon level {self.depth}.")
        if self.dungeon.amulet_here:
            self.log("You sense a powerful artifact on this level...")
        self.fov_dirty = True

    # ---- leveling ----
    def _check_level_up(self):
        needed = self.player.level * 20
        while self.player.xp >= needed:
            self.player.xp -= needed
            self.player.level += 1
            self.player.max_hp += 8
            self.player.hp = self.player.max_hp
            self.player.attack += 1
            self.log(f"*** You reach level {self.player.level}! HP and attack increase. ***")
            needed = self.player.level * 20

    # ---- enemy AI ----
    def _end_player_turn(self):
        self.turn += 1
        # Enemy turns
        for e in self.dungeon.entities:
            if not e.is_alive():
                continue
            self._enemy_turn(e)
            if not self.player.is_alive():
                self.game_over = True
                self.log("You die...")
                return

    def _enemy_turn(self, e):
        # Only act if player is in sight
        if not self._can_see(e, self.player):
            # Random walk
            if random.random() < 0.4:
                dx, dy = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
                nx, ny = e.x + dx, e.y + dy
                if self.dungeon.is_walkable(nx, ny) and not any(o.x==nx and o.y==ny for o in self.dungeon.entities if o is not e):
                    e.x, e.y = nx, ny
            return
        # Move toward player (greedy)
        dx = (self.player.x > e.x) - (self.player.x < e.x)
        dy = (self.player.y > e.y) - (self.player.y < e.y)
        if abs(self.player.x - e.x) > abs(self.player.y - e.y):
            step = (dx, 0)
        elif abs(self.player.y - e.y) > 0:
            step = (0, dy)
        else:
            step = (dx, dy)
        nx, ny = e.x + step[0], e.y + step[1]
        if (nx, ny) == (self.player.x, self.player.y):
            self._attack(e, self.player)
        elif self.dungeon.is_walkable(nx, ny) and not any(o.x==nx and o.y==ny for o in self.dungeon.entities if o is not e):
            e.x, e.y = nx, ny

    def _can_see(self, a, b):
        if ((a.x - b.x)**2 + (a.y - b.y)**2) ** 0.5 > a.sight_radius:
            return False
        return self.dungeon._line_of_sight(a.x, a.y, b.x, b.y)

    # ---- inventory ----
    def use_item(self, idx):
        if idx < 0 or idx >= len(self.player.inventory):
            self.log("Invalid item.")
            return
        item = self.player.inventory[idx]
        if item.kind == "potion":
            heal = item.bonus
            self.player.hp = min(self.player.max_hp, self.player.hp + heal)
            self.log(f"You drink {item.name}. +{heal} HP.")
            self.player.inventory.remove(item)
            self._end_player_turn()
        elif item.kind in ("weapon", "armor", "shield", "ring"):
            self.player.equipped[item.kind] = item
            self.log(f"You equip {item.name}.")
            self._end_player_turn()
        else:
            self.log(f"You can't use the {item.name}.")

    def drop_item(self, idx):
        if idx < 0 or idx >= len(self.player.inventory):
            self.log("Invalid item.")
            return
        item = self.player.inventory.pop(idx)
        self.dungeon.items.append((item, self.player.x, self.player.y))
        self.log(f"You drop {item.name}.")

    # ---- victory check ----
    def check_victory(self):
        for item in self.player.inventory:
            if item.name == "Amulet of Yendor":
                self.won = True
                self.game_over = True
                self.log("*** You have the Amulet of Yendor! You win! ***")
                return


# ============================================================
# Rendering
# ============================================================
def render(game):
    if game.fov_dirty:
        game.dungeon.compute_fov(game.player.x, game.player.y)
        game.fov_dirty = False

    out = []
    out.append(f"{BOLD}=== Delver's Descent ==={RESET}  "
               f"Depth: {game.depth}/{MAX_DEPTH}  Turn: {game.turn}")
    out.append("")

    # Build entity & item lookup
    item_map = {(ix, iy): item for item, ix, iy in game.dungeon.items}
    entity_map = {(e.x, e.y): e for e in game.dungeon.entities if e.is_alive()}

    # Render map
    for y in range(game.dungeon.h):
        line = []
        for x in range(game.dungeon.w):
            if not game.dungeon.visible[y][x]:
                if game.dungeon.explored[y][x]:
                    tile = game.dungeon.tiles[y][x]
                    line.append(f"{DIM}{tile}{RESET}")
                else:
                    line.append(" ")
                continue
            if (x, y) == (game.player.x, game.player.y):
                line.append(f"{BOLD}{COLORS[PLAYER]}{PLAYER}{RESET}")
            elif (x, y) in entity_map:
                e = entity_map[(x, y)]
                line.append(f"{COLORS.get(e.glyph, '')}{e.glyph}{RESET}")
            elif (x, y) in item_map:
                it = item_map[(x, y)]
                line.append(f"{COLORS.get(it.glyph, '')}{it.glyph}{RESET}")
            else:
                tile = game.dungeon.tiles[y][x]
                color = COLORS.get(tile, "")
                line.append(f"{color}{tile}{RESET}")
        out.append("".join(line))

    out.append("")
    # HUD
    p = game.player
    wpn = p.equipped["weapon"].name if p.equipped["weapon"] else "bare hands"
    arm = p.equipped["armor"].name if p.equipped["armor"] else "none"
    shd = p.equipped["shield"].name if p.equipped["shield"] else "none"
    rng = p.equipped["ring"].name if p.equipped["ring"] else "none"
    out.append(f"{BOLD}HP:{RESET} {p.hp}/{p.max_hp}  "
               f"{BOLD}Lvl:{RESET} {p.level}  "
               f"{BOLD}XP:{RESET} {p.xp}/{p.level*20}  "
               f"{BOLD}Gold:{RESET} {p.gold}  "
               f"{BOLD}ATK:{RESET} {p.power()}  "
               f"{BOLD}AC:{RESET} {p.armor_class()}")
    out.append(f"{DIM}Weapon: {wpn} | Armor: {arm} | Shield: {shd} | Ring: {rng}{RESET}")
    out.append("")

    # Messages
    for m in game.messages[-5:]:
        out.append(f"  {m}")

    out.append("")
    out.append(f"{DIM}WASD/HJKL: move  .: wait  i: inventory  g: pick up  >: descend  q: quit{RESET}")

    print("\n".join(out))


# ============================================================
# Inventory UI
# ============================================================
def show_inventory(game):
    print(f"\n{BOLD}=== Inventory ==={RESET}")
    p = game.player
    print(f"Gold: {p.gold}")
    print()
    if not p.inventory:
        print("  (empty)")
    for i, item in enumerate(p.inventory):
        eq = ""
        for slot, eq_item in p.equipped.items():
            if eq_item is item:
                eq = f"  {DIM}[equipped: {slot}]{RESET}"
                break
        print(f"  [{i+1}] {item.name}{eq}  {DIM}- {item.desc}{RESET}")
    print()
    print(f"{DIM}Enter: [1-N] use/equip, [d N] drop, [Enter] close{RESET}")
    try:
        choice = input("> ").strip().lower()
    except EOFError:
        return
    if not choice:
        return
    if choice.startswith("d "):
        try:
            idx = int(choice[2:]) - 1
            game.drop_item(idx)
        except ValueError:
            pass
    elif choice.isdigit():
        game.use_item(int(choice) - 1)


# ============================================================
# Main loop
# ============================================================
def main():
    game = Game()
    moves = {
        "w": (0, -1), "k": (0, -1),
        "s": (0,  1), "j": (0,  1),
        "a": (-1, 0), "h": (-1, 0),
        "d": ( 1, 0), "l": ( 1, 0),
        "y": (-1, -1), "u": (1, -1),
        "b": (-1,  1), "n": (1,  1),
    }
    while True:
        render(game)
        if game.game_over:
            if game.won:
                print(f"\n{BOLD}🎉 VICTORY! You retrieved the Amulet of Yendor in {game.turn} turns!{RESET}")
            else:
                print(f"\n{BOLD}💀 You died on dungeon level {game.depth}. Better luck next time.{RESET}")
            print(f"Final stats: Level {game.player.level} | {game.player.gold} gold | {game.turn} turns")
            break
        try:
            key = sys.stdin.readline().strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not key:
            continue
        if key in ("q", "quit"):
            print("Goodbye!")
            break
        elif key in moves:
            dx, dy = moves[key]
            game.move_player(dx, dy)
        elif key == ".":
            game.wait()
        elif key == "g":
            game.pickup()
            game._end_player_turn()
        elif key == ">":
            game.descend()
        elif key == "i":
            show_inventory(game)
        else:
            game.log(f"Unknown command: {key}")
        game.check_victory()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGame interrupted. Goodbye!")
