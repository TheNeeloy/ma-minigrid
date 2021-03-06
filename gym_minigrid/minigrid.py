import math
import hashlib
import gym
from enum import IntEnum
import numpy as np
from gym import error, spaces, utils
from gym.utils import seeding
from .rendering import *
from copy import deepcopy

# Size in pixels of a tile in the full-scale human view
TILE_PIXELS = 32

# Map of color names to RGB values
COLORS = {
    'red'   : np.array([255, 0, 0]),
    'green' : np.array([0, 255, 0]),
    'blue'  : np.array([0, 0, 255]),
    'purple': np.array([112, 39, 195]),
    'yellow': np.array([255, 255, 0]),
    'grey'  : np.array([100, 100, 100])
}

COLOR_NAMES = sorted(list(COLORS.keys()))

# Used to map colors to integers
COLOR_TO_IDX = {
    'red'   : 0,
    'green' : 1,
    'blue'  : 2,
    'purple': 3,
    'yellow': 4,
    'grey'  : 5
}

IDX_TO_COLOR = dict(zip(COLOR_TO_IDX.values(), COLOR_TO_IDX.keys()))

# Map of object type to integers
OBJECT_TO_IDX = {
    'unseen'        : 0,
    'empty'         : 1,
    'wall'          : 2,
    'floor'         : 3,
    'door'          : 4,
    'key'           : 5,
    'ball'          : 6,
    'box'           : 7,
    'goal'          : 8,
    'lava'          : 9,
    'agent'         : 10,
}

IDX_TO_OBJECT = dict(zip(OBJECT_TO_IDX.values(), OBJECT_TO_IDX.keys()))

# Map of state names to integers
STATE_TO_IDX = {
    'open'  : 0,
    'closed': 1,
    'locked': 2,
}

# Map of agent direction indices to vectors
DIR_TO_VEC = [
    # Pointing right (positive X)
    np.array((1, 0)),
    # Down (positive Y)
    np.array((0, 1)),
    # Pointing left (negative X)
    np.array((-1, 0)),
    # Up (negative Y)
    np.array((0, -1)),
]

class WorldObj:
    """
    Base class for grid world objects
    """

    def __init__(self, type, color):
        assert type in OBJECT_TO_IDX, type
        assert color in COLOR_TO_IDX, color
        self.type = type
        self.color = color
        self.contains = None

        # Initial position of the object
        self.init_pos = None

        # Current position of the object
        self.cur_pos = None

    def can_overlap(self):
        """Can the agent overlap with this?"""
        return False

    def can_pickup(self):
        """Can the agent pick this up?"""
        return False

    def ma_can_pickup(self, agent_id):
        """Can an agent pick this up in a multi-agent env?"""
        return False

    def can_contain(self):
        """Can this contain another object?"""
        return False

    def see_behind(self):
        """Can the agent see behind this object?"""
        return True

    def toggle(self, env, pos):
        """Method to trigger/toggle an action this object performs"""
        return False
    
    def ma_toggle(self, env, agent_id, pos):
        """Method to trigger/toggle an action this object performs in a multi-agent env"""
        return False

    def ma_check_toggle(self, env, agent_id, pos):
        """Method to check if trigger/toggle action is allowed on this object in a multi-agent env"""
        return False

    def encode(self):
        """Encode the a description of this object as a 3-tuple of integers"""
        return (OBJECT_TO_IDX[self.type], COLOR_TO_IDX[self.color], 0)

    @staticmethod
    def decode(type_idx, color_idx, state):
        """Create an object from a 3-tuple state description"""

        obj_type = IDX_TO_OBJECT[type_idx]
        color = IDX_TO_COLOR[color_idx]

        if obj_type == 'empty' or obj_type == 'unseen':
            return None

        # State, 0: open, 1: closed, 2: locked
        is_open = state == 0
        is_locked = state == 2

        if obj_type == 'wall':
            v = Wall(color)
        elif obj_type == 'floor':
            v = Floor(color)
        elif obj_type == 'ball':
            v = Ball(color)
        elif obj_type == 'key':
            v = Key(color)
        elif obj_type == 'box':
            v = Box(color)
        elif obj_type == 'door':
            v = Door(color, is_open, is_locked)
        elif obj_type == 'goal':
            v = Goal()
        elif obj_type == 'lava':
            v = Lava()
        else:
            assert False, "unknown object type in decode '%s'" % obj_type

        return v

    def render(self, r):
        """Draw this object with the given renderer"""
        raise NotImplementedError

class Goal(WorldObj):
    def __init__(self):
        super().__init__('goal', 'green')

    def can_overlap(self):
        return True

    def render(self, img):
        fill_coords(img, point_in_rect(0, 1, 0, 1), COLORS[self.color])

class Floor(WorldObj):
    """
    Colored floor tile the agent can walk over
    """

    def __init__(self, color='blue'):
        super().__init__('floor', color)

    def can_overlap(self):
        return True

    def render(self, img):
        # Give the floor a pale color
        color = COLORS[self.color] / 2
        fill_coords(img, point_in_rect(0.031, 1, 0.031, 1), color)


class Lava(WorldObj):
    def __init__(self):
        super().__init__('lava', 'red')

    def can_overlap(self):
        return True

    def render(self, img):
        c = (255, 128, 0)

        # Background color
        fill_coords(img, point_in_rect(0, 1, 0, 1), c)

        # Little waves
        for i in range(3):
            ylo = 0.3 + 0.2 * i
            yhi = 0.4 + 0.2 * i
            fill_coords(img, point_in_line(0.1, ylo, 0.3, yhi, r=0.03), (0,0,0))
            fill_coords(img, point_in_line(0.3, yhi, 0.5, ylo, r=0.03), (0,0,0))
            fill_coords(img, point_in_line(0.5, ylo, 0.7, yhi, r=0.03), (0,0,0))
            fill_coords(img, point_in_line(0.7, yhi, 0.9, ylo, r=0.03), (0,0,0))

class Wall(WorldObj):
    def __init__(self, color='grey'):
        super().__init__('wall', color)

    def see_behind(self):
        return False

    def render(self, img):
        fill_coords(img, point_in_rect(0, 1, 0, 1), COLORS[self.color])

class Door(WorldObj):
    def __init__(self, color, is_open=False, is_locked=False):
        super().__init__('door', color)
        self.is_open = is_open
        self.is_locked = is_locked

    def can_overlap(self):
        """The agent can only walk over this cell when the door is open"""
        return self.is_open

    def see_behind(self):
        return self.is_open

    def toggle(self, env, pos):
        # If the player has the right key to open the door
        if self.is_locked:
            if isinstance(env.carrying, Key) and env.carrying.color == self.color:
                self.is_locked = False
                self.is_open = True
                return True
            return False

        self.is_open = not self.is_open
        return True

    def ma_toggle(self, env, agent_id, pos):
        # If the player has the right key to open the door in a multi-agent setting
        if self.is_locked:
            if isinstance(env.carrying_objects[agent_id], Key) and env.carrying_objects[agent_id].color == self.color:
                self.is_locked = False
                self.is_open = True
                return True
            return False

        self.is_open = not self.is_open
        return True

    def ma_check_toggle(self, env, agent_id, pos):
        # If the player has the right key to open the door in a multi-agent setting
        if self.is_locked:
            if isinstance(env.carrying_objects[agent_id], Key) and env.carrying_objects[agent_id].color == self.color:
                return True
            return False

        return True

    def encode(self):
        """Encode the a description of this object as a 3-tuple of integers"""

        # State, 0: open, 1: closed, 2: locked
        if self.is_open:
            state = 0
        elif self.is_locked:
            state = 2
        elif not self.is_open:
            state = 1

        return (OBJECT_TO_IDX[self.type], COLOR_TO_IDX[self.color], state)

    def render(self, img):
        c = COLORS[self.color]

        if self.is_open:
            fill_coords(img, point_in_rect(0.88, 1.00, 0.00, 1.00), c)
            fill_coords(img, point_in_rect(0.92, 0.96, 0.04, 0.96), (0,0,0))
            return

        # Door frame and door
        if self.is_locked:
            fill_coords(img, point_in_rect(0.00, 1.00, 0.00, 1.00), c)
            fill_coords(img, point_in_rect(0.06, 0.94, 0.06, 0.94), 0.45 * np.array(c))

            # Draw key slot
            fill_coords(img, point_in_rect(0.52, 0.75, 0.50, 0.56), c)
        else:
            fill_coords(img, point_in_rect(0.00, 1.00, 0.00, 1.00), c)
            fill_coords(img, point_in_rect(0.04, 0.96, 0.04, 0.96), (0,0,0))
            fill_coords(img, point_in_rect(0.08, 0.92, 0.08, 0.92), c)
            fill_coords(img, point_in_rect(0.12, 0.88, 0.12, 0.88), (0,0,0))

            # Draw door handle
            fill_coords(img, point_in_circle(cx=0.75, cy=0.50, r=0.08), c)

class Key(WorldObj):
    def __init__(self, color='blue'):
        super(Key, self).__init__('key', color)

    def can_pickup(self):
        return True

    def ma_can_pickup(self, agent_id):
        agent_color = IDX_TO_COLOR[agent_id % len(COLOR_NAMES)]
        return True if agent_color == self.color else False

    def render(self, img):
        c = COLORS[self.color]

        # Vertical quad
        fill_coords(img, point_in_rect(0.50, 0.63, 0.31, 0.88), c)

        # Teeth
        fill_coords(img, point_in_rect(0.38, 0.50, 0.59, 0.66), c)
        fill_coords(img, point_in_rect(0.38, 0.50, 0.81, 0.88), c)

        # Ring
        fill_coords(img, point_in_circle(cx=0.56, cy=0.28, r=0.190), c)
        fill_coords(img, point_in_circle(cx=0.56, cy=0.28, r=0.064), (0,0,0))

class Ball(WorldObj):
    def __init__(self, color='blue'):
        super(Ball, self).__init__('ball', color)

    def can_pickup(self):
        return True

    def ma_can_pickup(self, agent_id):
        agent_color = IDX_TO_COLOR[agent_id % len(COLOR_NAMES)]
        return True if agent_color == self.color else False

    def render(self, img):
        fill_coords(img, point_in_circle(0.5, 0.5, 0.31), COLORS[self.color])

class Box(WorldObj):
    def __init__(self, color, contains=None):
        super(Box, self).__init__('box', color)
        self.contains = contains

    def can_pickup(self):
        return True

    def ma_can_pickup(self, agent_id):
        agent_color = IDX_TO_COLOR[agent_id % len(COLOR_NAMES)]
        return True if agent_color == self.color else False

    def render(self, img):
        c = COLORS[self.color]

        # Outline
        fill_coords(img, point_in_rect(0.12, 0.88, 0.12, 0.88), c)
        fill_coords(img, point_in_rect(0.18, 0.82, 0.18, 0.82), (0,0,0))

        # Horizontal slit
        fill_coords(img, point_in_rect(0.16, 0.84, 0.47, 0.53), c)

    def toggle(self, env, pos):
        # Replace the box by its contents
        env.grid.set(*pos, self.contains)
        return True

class Grid:
    """
    Represent a grid and operations on it
    """

    # Static cache of pre-renderer tiles
    tile_cache = {}

    def __init__(self, width, height):
        # assert width >= 3
        # assert height >= 3

        self.width = width
        self.height = height

        self.grid = [None] * width * height

    def __contains__(self, key):
        if isinstance(key, WorldObj):
            for e in self.grid:
                if e is key:
                    return True
        elif isinstance(key, tuple):
            for e in self.grid:
                if e is None:
                    continue
                if (e.color, e.type) == key:
                    return True
                if key[0] is None and key[1] == e.type:
                    return True
        return False

    def __eq__(self, other):
        grid1  = self.encode()
        grid2 = other.encode()
        return np.array_equal(grid2, grid1)

    def __ne__(self, other):
        return not self == other

    def copy(self):
        from copy import deepcopy
        return deepcopy(self)

    def set(self, i, j, v):
        assert i >= 0 and i < self.width
        assert j >= 0 and j < self.height
        self.grid[j * self.width + i] = v

    def get(self, i, j):
        assert i >= 0 and i < self.width
        assert j >= 0 and j < self.height
        return self.grid[j * self.width + i]

    def horz_wall(self, x, y, length=None, obj_type=Wall):
        if length is None:
            length = self.width - x
        for i in range(0, length):
            self.set(x + i, y, obj_type())

    def vert_wall(self, x, y, length=None, obj_type=Wall):
        if length is None:
            length = self.height - y
        for j in range(0, length):
            self.set(x, y + j, obj_type())

    def wall_rect(self, x, y, w, h):
        self.horz_wall(x, y, w)
        self.horz_wall(x, y+h-1, w)
        self.vert_wall(x, y, h)
        self.vert_wall(x+w-1, y, h)

    def rotate_left(self):
        """
        Rotate the grid to the left (counter-clockwise)
        """

        grid = Grid(self.height, self.width)

        for i in range(self.width):
            for j in range(self.height):
                v = self.get(i, j)
                grid.set(j, grid.height - 1 - i, v)

        return grid

    def slice(self, topX, topY, width, height):
        """
        Get a subset of the grid
        """

        grid = Grid(width, height)

        for j in range(0, height):
            for i in range(0, width):
                x = topX + i
                y = topY + j

                if x >= 0 and x < self.width and \
                   y >= 0 and y < self.height:
                    v = self.get(x, y)
                else:
                    v = Wall()

                grid.set(i, j, v)

        return grid

    @classmethod
    def render_tile(
        cls,
        obj,
        agent_dir=None,
        highlight=False,
        tile_size=TILE_PIXELS,
        subdivs=3
    ):
        """
        Render a tile and cache the result
        """

        # Hash map lookup key for the cache
        key = (agent_dir, highlight, tile_size)
        key = obj.encode() + key if obj else key

        if key in cls.tile_cache:
            return cls.tile_cache[key]

        img = np.zeros(shape=(tile_size * subdivs, tile_size * subdivs, 3), dtype=np.uint8)

        # Draw the grid lines (top and left edges)
        fill_coords(img, point_in_rect(0, 0.031, 0, 1), (100, 100, 100))
        fill_coords(img, point_in_rect(0, 1, 0, 0.031), (100, 100, 100))

        if obj != None:
            obj.render(img)

        # Overlay the agent on top
        if agent_dir is not None:
            tri_fn = point_in_triangle(
                (0.12, 0.19),
                (0.87, 0.50),
                (0.12, 0.81),
            )

            # Rotate the agent based on its direction
            tri_fn = rotate_fn(tri_fn, cx=0.5, cy=0.5, theta=0.5*math.pi*agent_dir)
            fill_coords(img, tri_fn, (255, 0, 0))

        # Highlight the cell if needed
        if highlight:
            highlight_img(img)

        # Downsample the image to perform supersampling/anti-aliasing
        img = downsample(img, subdivs)

        # Cache the rendered tile
        cls.tile_cache[key] = img

        return img

    def render(
        self,
        tile_size,
        agent_pos=None,
        agent_dir=None,
        highlight_mask=None
    ):
        """
        Render this grid at a given scale
        :param r: target renderer object
        :param tile_size: tile size in pixels
        """

        if highlight_mask is None:
            highlight_mask = np.zeros(shape=(self.width, self.height), dtype=np.bool)

        # Compute the total grid size
        width_px = self.width * tile_size
        height_px = self.height * tile_size

        img = np.zeros(shape=(height_px, width_px, 3), dtype=np.uint8)

        # Render the grid
        for j in range(0, self.height):
            for i in range(0, self.width):
                cell = self.get(i, j)

                agent_here = np.array_equal(agent_pos, (i, j))
                tile_img = Grid.render_tile(
                    cell,
                    agent_dir=agent_dir if agent_here else None,
                    highlight=highlight_mask[i, j],
                    tile_size=tile_size
                )

                ymin = j * tile_size
                ymax = (j+1) * tile_size
                xmin = i * tile_size
                xmax = (i+1) * tile_size
                img[ymin:ymax, xmin:xmax, :] = tile_img

        return img

    @classmethod
    def ma_render_tile(
        cls,
        obj,
        agent_id=None,
        agent_dir=None,
        num_agents=None,
        highlight=False,
        tile_size=TILE_PIXELS,
        subdivs=3
    ):
        """
        Render a tile and cache the result for a multi-agent environment
        """

        # Hash map lookup key for the cache
        key = (agent_dir, highlight, tile_size, agent_id)
        key = obj.encode() + key if obj else key

        if key in cls.tile_cache:
            return cls.tile_cache[key]

        img = np.zeros(shape=(tile_size * subdivs, tile_size * subdivs, 3), dtype=np.uint8)

        # Draw the grid lines (top and left edges)
        fill_coords(img, point_in_rect(0, 0.031, 0, 1), (100, 100, 100))
        fill_coords(img, point_in_rect(0, 1, 0, 0.031), (100, 100, 100))

        if obj != None:
            obj.render(img)

        # Overlay an agent on top
        if agent_dir is not None and num_agents is not None and agent_id is not None:
            tri_fn = point_in_triangle(
                (0.12, 0.19),
                (0.87, 0.50),
                (0.12, 0.81),
            )

            # Rotate the agent based on its direction
            tri_fn = rotate_fn(tri_fn, cx=0.5, cy=0.5, theta=0.5*math.pi*agent_dir)
            fill_coords(img, tri_fn, tuple(COLORS[IDX_TO_COLOR[agent_id % len(COLOR_NAMES)]]))

        # Highlight the cell if needed
        if highlight:
            highlight_img(img)

        # Downsample the image to perform supersampling/anti-aliasing
        img = downsample(img, subdivs)

        # Cache the rendered tile
        cls.tile_cache[key] = img

        return img

    def ma_render(
        self,
        tile_size,
        agent_poses=None,
        agent_dirs=None,
        highlight_mask=None
    ):
        """
        Render this grid at a given scale
        :param r: target renderer object
        :param tile_size: tile size in pixels
        """

        if highlight_mask is None:
            highlight_mask = np.zeros(shape=(self.width, self.height), dtype=np.bool)

        # Compute the total grid size
        width_px = self.width * tile_size
        height_px = self.height * tile_size

        img = np.zeros(shape=(height_px, width_px, 3), dtype=np.uint8)

        # Render the grid
        for j in range(0, self.height):
            for i in range(0, self.width):
                cell = self.get(i, j)

                agent_here = False
                agent_index = None
                if agent_poses is not None:
                    for agent_index, p in enumerate(agent_poses):
                        if np.all(np.equal(p, np.array((i, j)))):
                            agent_here = True
                            break 

                tile_img = Grid.ma_render_tile(
                    cell,
                    agent_id=agent_index if agent_here else None,
                    agent_dir=agent_dirs[agent_index] if agent_here else None,
                    num_agents=len(agent_poses) if agent_here else None,
                    highlight=highlight_mask[i, j],
                    tile_size=tile_size
                )

                ymin = j * tile_size
                ymax = (j+1) * tile_size
                xmin = i * tile_size
                xmax = (i+1) * tile_size
                img[ymin:ymax, xmin:xmax, :] = tile_img

        return img

    def encode(self, vis_mask=None):
        """
        Produce a compact numpy encoding of the grid
        """

        if vis_mask is None:
            vis_mask = np.ones((self.width, self.height), dtype=bool)

        array = np.zeros((self.width, self.height, 3), dtype='uint8')

        for i in range(self.width):
            for j in range(self.height):
                if vis_mask[i, j]:
                    v = self.get(i, j)

                    if v is None:
                        array[i, j, 0] = OBJECT_TO_IDX['empty']
                        array[i, j, 1] = 0
                        array[i, j, 2] = 0

                    else:
                        array[i, j, :] = v.encode()

        return array

    def ma_encode(self, vis_mask=None, agent_poses=None):
        """
        Produce a compact numpy encoding of the grid for multiagent setting
        """

        if vis_mask is None:
            vis_mask = np.ones((self.width, self.height), dtype=bool)

        array = np.zeros((self.width, self.height, 3), dtype='uint8')

        for i in range(self.width):
            for j in range(self.height):
                if vis_mask[i, j]:
                    v = self.get(i, j)

                    if v is None:
                        if agent_poses != None and any((np.array((i, j)) == x[0]).all() for x in agent_poses):
                            found = False
                            for agent_id, agent_pos in enumerate(agent_poses):
                                if (np.array((i, j)) == agent_pos[0]).all():
                                    found = True
                                    break
                            if found:
                                array[i, j, 0] = OBJECT_TO_IDX['agent']
                                array[i, j, 1] = agent_poses[agent_id][1] % len(COLOR_NAMES)
                                array[i, j, 2] = agent_poses[agent_id][2]

                        else:
                            array[i, j, 0] = OBJECT_TO_IDX['empty']
                            array[i, j, 1] = 0
                            array[i, j, 2] = 0

                    else:
                        array[i, j, :] = v.encode()

        return array

    @staticmethod
    def decode(array):
        """
        Decode an array grid encoding back into a grid
        """

        width, height, channels = array.shape
        assert channels == 3

        vis_mask = np.ones(shape=(width, height), dtype=np.bool)

        grid = Grid(width, height)
        for i in range(width):
            for j in range(height):
                type_idx, color_idx, state = array[i, j]
                v = WorldObj.decode(type_idx, color_idx, state)
                grid.set(i, j, v)
                vis_mask[i, j] = (type_idx != OBJECT_TO_IDX['unseen'])

        return grid, vis_mask

    def process_vis(grid, agent_pos):
        mask = np.zeros(shape=(grid.width, grid.height), dtype=np.bool)

        mask[agent_pos[0], agent_pos[1]] = True

        for j in reversed(range(0, grid.height)):
            for i in range(0, grid.width-1):
                if not mask[i, j]:
                    continue

                cell = grid.get(i, j)
                if cell and not cell.see_behind():
                    continue

                mask[i+1, j] = True
                if j > 0:
                    mask[i+1, j-1] = True
                    mask[i, j-1] = True

            for i in reversed(range(1, grid.width)):
                if not mask[i, j]:
                    continue

                cell = grid.get(i, j)
                if cell and not cell.see_behind():
                    continue

                mask[i-1, j] = True
                if j > 0:
                    mask[i-1, j-1] = True
                    mask[i, j-1] = True

        for j in range(0, grid.height):
            for i in range(0, grid.width):
                if not mask[i, j]:
                    grid.set(i, j, None)

        return mask

class MiniGridEnv(gym.Env):
    """
    2D grid world game environment
    """

    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 10
    }

    # Enumeration of possible actions
    class Actions(IntEnum):
        # Turn left, turn right, move forward
        left = 0
        right = 1
        forward = 2

        # Pick up an object
        pickup = 3
        # Drop an object
        drop = 4
        # Toggle/activate an object
        toggle = 5

        # Done completing task
        done = 6

    def __init__(
        self,
        grid_size=None,
        width=None,
        height=None,
        max_steps=100,
        see_through_walls=False,
        seed=1337,
        agent_view_size=7
    ):
        # Can't set both grid_size and width/height
        if grid_size:
            assert width == None and height == None
            width = grid_size
            height = grid_size

        # Action enumeration for this environment
        self.actions = MiniGridEnv.Actions

        # Actions are discrete integer values
        self.action_space = spaces.Discrete(len(self.actions))

        # Number of cells (width and height) in the agent view
        assert agent_view_size % 2 == 1
        assert agent_view_size >= 3
        self.agent_view_size = agent_view_size

        # Observations are dictionaries containing an
        # encoding of the grid and a textual 'mission' string
        self.observation_space = spaces.Box(
            low=0,
            high=255,
            shape=(self.agent_view_size, self.agent_view_size, 3),
            dtype='uint8'
        )
        self.observation_space = spaces.Dict({
            'image': self.observation_space
        })

        # Range of possible rewards
        self.reward_range = (0, 1)

        # Window to use for human rendering mode
        self.window = None

        # Environment configuration
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.see_through_walls = see_through_walls

        # Current position and direction of the agent
        self.agent_pos = None
        self.agent_dir = None

        # Initialize the RNG
        self.seed(seed=seed)

        # Initialize the state
        self.reset()

    def reset(self):
        # Current position and direction of the agent
        self.agent_pos = None
        self.agent_dir = None

        # Generate a new random grid at the start of each episode
        # To keep the same grid for each episode, call env.seed() with
        # the same seed before calling env.reset()
        self._gen_grid(self.width, self.height)

        # These fields should be defined by _gen_grid
        assert self.agent_pos is not None
        assert self.agent_dir is not None

        # Check that the agent doesn't overlap with an object
        start_cell = self.grid.get(*self.agent_pos)
        assert start_cell is None or start_cell.can_overlap()

        # Item picked up, being carried, initially nothing
        self.carrying = None

        # Step count since episode start
        self.step_count = 0

        # Return first observation
        obs = self.gen_obs()
        return obs

    def seed(self, seed=1337):
        # Seed the random number generator
        self.np_random, _ = seeding.np_random(seed)
        return [seed]

    def hash(self, size=16):
        """Compute a hash that uniquely identifies the current state of the environment.
        :param size: Size of the hashing
        """
        sample_hash = hashlib.sha256()

        to_encode = [self.grid.encode(), self.agent_pos, self.agent_dir]
        for item in to_encode:
            sample_hash.update(str(item).encode('utf8'))

        return sample_hash.hexdigest()[:size]

    @property
    def steps_remaining(self):
        return self.max_steps - self.step_count

    def __str__(self):
        """
        Produce a pretty string of the environment's grid along with the agent.
        A grid cell is represented by 2-character string, the first one for
        the object and the second one for the color.
        """

        # Map of object types to short string
        OBJECT_TO_STR = {
            'wall'          : 'W',
            'floor'         : 'F',
            'door'          : 'D',
            'key'           : 'K',
            'ball'          : 'A',
            'box'           : 'B',
            'goal'          : 'G',
            'lava'          : 'V',
        }

        # Short string for opened door
        OPENDED_DOOR_IDS = '_'

        # Map agent's direction to short string
        AGENT_DIR_TO_STR = {
            0: '>',
            1: 'V',
            2: '<',
            3: '^'
        }

        str = ''

        for j in range(self.grid.height):

            for i in range(self.grid.width):
                if i == self.agent_pos[0] and j == self.agent_pos[1]:
                    str += 2 * AGENT_DIR_TO_STR[self.agent_dir]
                    continue

                c = self.grid.get(i, j)

                if c == None:
                    str += '  '
                    continue

                if c.type == 'door':
                    if c.is_open:
                        str += '__'
                    elif c.is_locked:
                        str += 'L' + c.color[0].upper()
                    else:
                        str += 'D' + c.color[0].upper()
                    continue

                str += OBJECT_TO_STR[c.type] + c.color[0].upper()

            if j < self.grid.height - 1:
                str += '\n'

        return str

    def _gen_grid(self, width, height):
        assert False, "_gen_grid needs to be implemented by each environment"

    def _reward(self):
        """
        Compute the reward to be given upon success
        """

        return 1 - 0.9 * (self.step_count / self.max_steps)

    def _rand_int(self, low, high):
        """
        Generate random integer in [low,high[
        """

        return self.np_random.randint(low, high)

    def _rand_float(self, low, high):
        """
        Generate random float in [low,high[
        """

        return self.np_random.uniform(low, high)

    def _rand_bool(self):
        """
        Generate random boolean value
        """

        return (self.np_random.randint(0, 2) == 0)

    def _rand_elem(self, iterable):
        """
        Pick a random element in a list
        """

        lst = list(iterable)
        idx = self._rand_int(0, len(lst))
        return lst[idx]

    def _rand_subset(self, iterable, num_elems):
        """
        Sample a random subset of distinct elements of a list
        """

        lst = list(iterable)
        assert num_elems <= len(lst)

        out = []

        while len(out) < num_elems:
            elem = self._rand_elem(lst)
            lst.remove(elem)
            out.append(elem)

        return out

    def _rand_color(self):
        """
        Generate a random color name (string)
        """

        return self._rand_elem(COLOR_NAMES)

    def _rand_pos(self, xLow, xHigh, yLow, yHigh):
        """
        Generate a random (x,y) position tuple
        """

        return (
            self.np_random.randint(xLow, xHigh),
            self.np_random.randint(yLow, yHigh)
        )

    def place_obj(self,
        obj,
        top=None,
        size=None,
        reject_fn=None,
        max_tries=math.inf
    ):
        """
        Place an object at an empty position in the grid

        :param top: top-left position of the rectangle where to place
        :param size: size of the rectangle where to place
        :param reject_fn: function to filter out potential positions
        """

        if top is None:
            top = (0, 0)
        else:
            top = (max(top[0], 0), max(top[1], 0))

        if size is None:
            size = (self.grid.width, self.grid.height)

        num_tries = 0

        while True:
            # This is to handle with rare cases where rejection sampling
            # gets stuck in an infinite loop
            if num_tries > max_tries:
                raise RecursionError('rejection sampling failed in place_obj')

            num_tries += 1

            pos = np.array((
                self._rand_int(top[0], min(top[0] + size[0], self.grid.width)),
                self._rand_int(top[1], min(top[1] + size[1], self.grid.height))
            ))

            # Don't place the object on top of another object
            if self.grid.get(*pos) != None:
                continue

            # Don't place the object where the agent is
            if np.array_equal(pos, self.agent_pos):
                continue

            # Check if there is a filtering criterion
            if reject_fn and reject_fn(self, pos):
                continue

            break

        self.grid.set(*pos, obj)

        if obj is not None:
            obj.init_pos = pos
            obj.cur_pos = pos

        return pos

    def put_obj(self, obj, i, j):
        """
        Put an object at a specific position in the grid
        """

        self.grid.set(i, j, obj)
        obj.init_pos = (i, j)
        obj.cur_pos = (i, j)

    def place_agent(
        self,
        top=None,
        size=None,
        rand_dir=True,
        max_tries=math.inf
    ):
        """
        Set the agent's starting point at an empty position in the grid
        """

        self.agent_pos = None
        pos = self.place_obj(None, top, size, max_tries=max_tries)
        self.agent_pos = pos

        if rand_dir:
            self.agent_dir = self._rand_int(0, 4)

        return pos

    @property
    def dir_vec(self):
        """
        Get the direction vector for the agent, pointing in the direction
        of forward movement.
        """

        assert self.agent_dir >= 0 and self.agent_dir < 4
        return DIR_TO_VEC[self.agent_dir]

    @property
    def right_vec(self):
        """
        Get the vector pointing to the right of the agent.
        """

        dx, dy = self.dir_vec
        return np.array((-dy, dx))

    @property
    def front_pos(self):
        """
        Get the position of the cell that is right in front of the agent
        """

        return self.agent_pos + self.dir_vec

    def get_view_coords(self, i, j):
        """
        Translate and rotate absolute grid coordinates (i, j) into the
        agent's partially observable view (sub-grid). Note that the resulting
        coordinates may be negative or outside of the agent's view size.
        """

        ax, ay = self.agent_pos
        dx, dy = self.dir_vec
        rx, ry = self.right_vec

        # Compute the absolute coordinates of the top-left view corner
        sz = self.agent_view_size
        hs = self.agent_view_size // 2
        tx = ax + (dx * (sz-1)) - (rx * hs)
        ty = ay + (dy * (sz-1)) - (ry * hs)

        lx = i - tx
        ly = j - ty

        # Project the coordinates of the object relative to the top-left
        # corner onto the agent's own coordinate system
        vx = (rx*lx + ry*ly)
        vy = -(dx*lx + dy*ly)

        return vx, vy

    def get_view_exts(self):
        """
        Get the extents of the square set of tiles visible to the agent
        Note: the bottom extent indices are not included in the set
        """

        # Facing right
        if self.agent_dir == 0:
            topX = self.agent_pos[0]
            topY = self.agent_pos[1] - self.agent_view_size // 2
        # Facing down
        elif self.agent_dir == 1:
            topX = self.agent_pos[0] - self.agent_view_size // 2
            topY = self.agent_pos[1]
        # Facing left
        elif self.agent_dir == 2:
            topX = self.agent_pos[0] - self.agent_view_size + 1
            topY = self.agent_pos[1] - self.agent_view_size // 2
        # Facing up
        elif self.agent_dir == 3:
            topX = self.agent_pos[0] - self.agent_view_size // 2
            topY = self.agent_pos[1] - self.agent_view_size + 1
        else:
            assert False, "invalid agent direction"

        botX = topX + self.agent_view_size
        botY = topY + self.agent_view_size

        return (topX, topY, botX, botY)

    def relative_coords(self, x, y):
        """
        Check if a grid position belongs to the agent's field of view, and returns the corresponding coordinates
        """

        vx, vy = self.get_view_coords(x, y)

        if vx < 0 or vy < 0 or vx >= self.agent_view_size or vy >= self.agent_view_size:
            return None

        return vx, vy

    def in_view(self, x, y):
        """
        check if a grid position is visible to the agent
        """

        return self.relative_coords(x, y) is not None

    def agent_sees(self, x, y):
        """
        Check if a non-empty grid position is visible to the agent
        """

        coordinates = self.relative_coords(x, y)
        if coordinates is None:
            return False
        vx, vy = coordinates

        obs = self.gen_obs()
        obs_grid, _ = Grid.decode(obs['image'])
        obs_cell = obs_grid.get(vx, vy)
        world_cell = self.grid.get(x, y)

        return obs_cell is not None and obs_cell.type == world_cell.type

    def step(self, action):
        self.step_count += 1

        reward = 0
        done = False

        # Get the position in front of the agent
        fwd_pos = self.front_pos

        # Get the contents of the cell in front of the agent
        fwd_cell = self.grid.get(*fwd_pos)

        # Rotate left
        if action == self.actions.left:
            self.agent_dir -= 1
            if self.agent_dir < 0:
                self.agent_dir += 4

        # Rotate right
        elif action == self.actions.right:
            self.agent_dir = (self.agent_dir + 1) % 4

        # Move forward
        elif action == self.actions.forward:
            if fwd_cell == None or fwd_cell.can_overlap():
                self.agent_pos = fwd_pos
            if fwd_cell != None and fwd_cell.type == 'goal':
                done = True
                reward = self._reward()
            if fwd_cell != None and fwd_cell.type == 'lava':
                done = True

        # Pick up an object
        elif action == self.actions.pickup:
            if fwd_cell and fwd_cell.can_pickup():
                if self.carrying is None:
                    self.carrying = fwd_cell
                    self.carrying.cur_pos = np.array([-1, -1])
                    self.grid.set(*fwd_pos, None)

        # Drop an object
        elif action == self.actions.drop:
            if not fwd_cell and self.carrying:
                self.grid.set(*fwd_pos, self.carrying)
                self.carrying.cur_pos = fwd_pos
                self.carrying = None

        # Toggle/activate an object
        elif action == self.actions.toggle:
            if fwd_cell:
                fwd_cell.toggle(self, fwd_pos)

        # Done action (not used by default)
        elif action == self.actions.done:
            pass

        else:
            assert False, "unknown action"

        if self.step_count >= self.max_steps:
            done = True

        obs = self.gen_obs()

        return obs, reward, done, {}

    def gen_obs_grid(self):
        """
        Generate the sub-grid observed by the agent.
        This method also outputs a visibility mask telling us which grid
        cells the agent can actually see.
        """

        topX, topY, botX, botY = self.get_view_exts()

        grid = self.grid.slice(topX, topY, self.agent_view_size, self.agent_view_size)

        for i in range(self.agent_dir + 1):
            grid = grid.rotate_left()

        # Process occluders and visibility
        # Note that this incurs some performance cost
        if not self.see_through_walls:
            vis_mask = grid.process_vis(agent_pos=(self.agent_view_size // 2 , self.agent_view_size - 1))
        else:
            vis_mask = np.ones(shape=(grid.width, grid.height), dtype=np.bool)

        # Make it so the agent sees what it's carrying
        # We do this by placing the carried object at the agent's position
        # in the agent's partially observable view
        agent_pos = grid.width // 2, grid.height - 1
        if self.carrying:
            grid.set(*agent_pos, self.carrying)
        else:
            grid.set(*agent_pos, None)

        return grid, vis_mask

    def gen_obs(self):
        """
        Generate the agent's view (partially observable, low-resolution encoding)
        """

        grid, vis_mask = self.gen_obs_grid()

        # Encode the partially observable view into a numpy array
        image = grid.encode(vis_mask)

        assert hasattr(self, 'mission'), "environments must define a textual mission string"

        # Observations are dictionaries containing:
        # - an image (partially observable view of the environment)
        # - the agent's direction/orientation (acting as a compass)
        # - a textual mission string (instructions for the agent)
        obs = {
            'image': image,
            'direction': self.agent_dir,
            'mission': self.mission
        }

        return obs

    def get_obs_render(self, obs, tile_size=TILE_PIXELS//2):
        """
        Render an agent observation for visualization
        """

        grid, vis_mask = Grid.decode(obs)

        # Render the whole grid
        img = grid.render(
            tile_size,
            agent_pos=(self.agent_view_size // 2, self.agent_view_size - 1),
            agent_dir=3,
            highlight_mask=vis_mask
        )

        return img

    def render(self, mode='human', close=False, highlight=True, tile_size=TILE_PIXELS):
        """
        Render the whole-grid human view
        """

        if close:
            if self.window:
                self.window.close()
            return

        if mode == 'human' and not self.window:
            import gym_minigrid.window
            self.window = gym_minigrid.window.Window('gym_minigrid')
            self.window.show(block=False)

        # Compute which cells are visible to the agent
        _, vis_mask = self.gen_obs_grid()

        # Compute the world coordinates of the bottom-left corner
        # of the agent's view area
        f_vec = self.dir_vec
        r_vec = self.right_vec
        top_left = self.agent_pos + f_vec * (self.agent_view_size-1) - r_vec * (self.agent_view_size // 2)

        # Mask of which cells to highlight
        highlight_mask = np.zeros(shape=(self.width, self.height), dtype=np.bool)

        # For each cell in the visibility mask
        for vis_j in range(0, self.agent_view_size):
            for vis_i in range(0, self.agent_view_size):
                # If this cell is not visible, don't highlight it
                if not vis_mask[vis_i, vis_j]:
                    continue

                # Compute the world coordinates of this cell
                abs_i, abs_j = top_left - (f_vec * vis_j) + (r_vec * vis_i)

                if abs_i < 0 or abs_i >= self.width:
                    continue
                if abs_j < 0 or abs_j >= self.height:
                    continue

                # Mark this cell to be highlighted
                highlight_mask[abs_i, abs_j] = True

        # Render the whole grid
        img = self.grid.render(
            tile_size,
            self.agent_pos,
            self.agent_dir,
            highlight_mask=highlight_mask if highlight else None
        )

        if mode == 'human':
            self.window.show_img(img)
            self.window.set_caption(self.mission)

        return img

    def close(self):
        if self.window:
            self.window.close()
        return

class MultiAgentMiniGridEnv(gym.Env):
    """
    2D grid world game environment with multi-agent support
    """

    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 10
    }

    # Enumeration of possible actions
    class Actions(IntEnum):
        # Turn left, turn right, move forward
        left = 0
        right = 1
        forward = 2

        # Pick up an object
        pickup = 3
        # Drop an object
        drop = 4
        # Toggle/activate an object
        toggle = 5

        # Done completing task
        done = 6

    def __init__(
        self,
        grid_size=None,
        width=None,
        height=None,
        max_steps=100,
        see_through_walls=False,
        seed=1337,
        agent_view_size=7
    ):
        # Can't set both grid_size and width/height
        if grid_size:
            assert width == None and height == None
            width = grid_size
            height = grid_size

        # Action enumeration for this environment
        self.actions = MultiAgentMiniGridEnv.Actions

        # Actions are discrete integer values
        self.action_space = spaces.Discrete(len(self.actions))

        # Number of cells (width and height) in the agent view
        assert agent_view_size % 2 == 1
        assert agent_view_size >= 3
        self.agent_view_size = agent_view_size

        # Observations are dictionaries containing an
        # encoding of the grid and a textual 'mission' string
        self.observation_space = spaces.Box(
            low=0,
            high=255,
            shape=(self.agent_view_size, self.agent_view_size, 3),
            dtype='uint8'
        )
        self.observation_space = spaces.Dict({
            'image': self.observation_space
        })

        # Range of possible rewards
        self.reward_range = (0, 1)

        # Window to use for human rendering mode
        self.window = None

        # Environment configuration
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.see_through_walls = see_through_walls

        # Current positions and directions of the agents
        self.agent_poses = []
        self.agent_dirs = []

        # Initialize the RNG
        self.seed(seed=seed)

        # Initialize the state
        self.reset()

    def reset(self):
        # Current positions and directions of the agents
        self.agent_poses = []
        self.agent_dirs = []

        # Generate a new random grid at the start of each episode
        # To keep the same grid for each episode, call env.seed() with
        # the same seed before calling env.reset()
        self._gen_grid(self.width, self.height)

        # These fields should be defined by _gen_grid
        assert self.agent_poses
        assert self.agent_dirs

        # Check that the agent doesn't overlap with an object
        for pos in self.agent_poses:
            start_cell = self.grid.get(*pos)
            assert start_cell is None or start_cell.can_overlap()

        # Item picked up, being carried, initially nothing for all agents
        self.carrying_objects = [None for i in self.agent_poses]

        # Step count since episode start
        self.step_count = 0

        # Return first observation
        obs = self.gen_obs()
        return obs

    def seed(self, seed=1337):
        # Seed the random number generator
        self.np_random, _ = seeding.np_random(seed)
        return [seed]

    def hash(self, size=16):
        """Compute a hash that uniquely identifies the current state of the environment.
        :param size: Size of the hashing
        """
        sample_hash = hashlib.sha256()

        agent_poses = [(pos, agent_id, self.agent_dirs[agent_id]) for agent_id, pos in enumerate(self.agent_poses)]

        to_encode = [self.grid.ma_encode(agent_poses=agent_poses), self.agent_poses, self.agent_dirs]
        for item in to_encode:
            sample_hash.update(str(item).encode('utf8'))

        return sample_hash.hexdigest()[:size]

    @property
    def steps_remaining(self):
        return self.max_steps - self.step_count

    def __str__(self):
        """
        Produce a pretty string of the environment's grid along with the agent.
        A grid cell is represented by 2-character string, the first one for
        the object and the second one for the color.
        """

        # Map of object types to short string
        OBJECT_TO_STR = {
            'wall'          : 'W',
            'floor'         : 'F',
            'door'          : 'D',
            'key'           : 'K',
            'ball'          : 'A',
            'box'           : 'B',
            'goal'          : 'G',
            'lava'          : 'V',
        }

        # Short string for opened door
        OPENDED_DOOR_IDS = '_'

        # Map agent's direction to short string
        AGENT_DIR_TO_STR = {
            0: '>',
            1: 'V',
            2: '<',
            3: '^'
        }

        str = ''

        for j in range(self.grid.height):

            for i in range(self.grid.width):
                if np.array((i, j)) in self.agent_poses:
                    str += 2 * AGENT_DIR_TO_STR[self.agent_dirs[self.agent_poses.index(np.array((i, j)))]]
                    continue

                c = self.grid.get(i, j)

                if c == None:
                    str += '  '
                    continue

                if c.type == 'door':
                    if c.is_open:
                        str += '__'
                    elif c.is_locked:
                        str += 'L' + c.color[0].upper()
                    else:
                        str += 'D' + c.color[0].upper()
                    continue

                str += OBJECT_TO_STR[c.type] + c.color[0].upper()

            if j < self.grid.height - 1:
                str += '\n'

        return str

    def _gen_grid(self, width, height):
        assert False, "_gen_grid needs to be implemented by each environment"

    def _reward(self):
        """
        Compute the reward to be given upon success
        """

        return 1 - 0.9 * (self.step_count / self.max_steps)

    def _rand_int(self, low, high):
        """
        Generate random integer in [low,high[
        """

        return self.np_random.randint(low, high)

    def _rand_float(self, low, high):
        """
        Generate random float in [low,high[
        """

        return self.np_random.uniform(low, high)

    def _rand_bool(self):
        """
        Generate random boolean value
        """

        return (self.np_random.randint(0, 2) == 0)

    def _rand_elem(self, iterable):
        """
        Pick a random element in a list
        """

        lst = list(iterable)
        idx = self._rand_int(0, len(lst))
        return lst[idx]

    def _rand_subset(self, iterable, num_elems):
        """
        Sample a random subset of distinct elements of a list
        """

        lst = list(iterable)
        assert num_elems <= len(lst)

        out = []

        while len(out) < num_elems:
            elem = self._rand_elem(lst)
            lst.remove(elem)
            out.append(elem)

        return out

    def _rand_color(self):
        """
        Generate a random color name (string)
        """

        return self._rand_elem(COLOR_NAMES)

    def _rand_pos(self, xLow, xHigh, yLow, yHigh):
        """
        Generate a random (x,y) position tuple
        """

        return (
            self.np_random.randint(xLow, xHigh),
            self.np_random.randint(yLow, yHigh)
        )

    def place_obj(self,
        obj,
        top=None,
        size=None,
        reject_fn=None,
        max_tries=math.inf
    ):
        """
        Place an object at an empty position in the grid

        :param top: top-left position of the rectangle where to place
        :param size: size of the rectangle where to place
        :param reject_fn: function to filter out potential positions
        """

        if top is None:
            top = (0, 0)
        else:
            top = (max(top[0], 0), max(top[1], 0))

        if size is None:
            size = (self.grid.width, self.grid.height)

        num_tries = 0

        while True:
            # This is to handle with rare cases where rejection sampling
            # gets stuck in an infinite loop
            if num_tries > max_tries:
                raise RecursionError('rejection sampling failed in place_obj')

            num_tries += 1

            pos = np.array((
                self._rand_int(top[0], min(top[0] + size[0], self.grid.width)),
                self._rand_int(top[1], min(top[1] + size[1], self.grid.height))
            ))

            # Don't place the object on top of another object
            if self.grid.get(*pos) != None:
                continue

            conflict = False
            for p in self.agent_poses:
                if np.all(np.equal(p, pos)):
                    conflict = True
                    break
            if conflict:
                continue

            # Check if there is a filtering criterion
            if reject_fn and reject_fn(self, pos):
                continue

            break

        self.grid.set(*pos, obj)

        if obj is not None:
            obj.init_pos = pos
            obj.cur_pos = pos

        return pos

    def put_obj(self, obj, i, j):
        """
        Put an object at a specific position in the grid
        """

        self.grid.set(i, j, obj)
        obj.init_pos = (i, j)
        obj.cur_pos = (i, j)

    def place_agent(
        self,
        top=None,
        size=None,
        rand_dir=True,
        max_tries=math.inf
    ):
        """
        Set an agent's starting point at an empty position in the grid
        """

        pos = self.place_obj(None, top, size, max_tries=max_tries)
        self.agent_poses.append(pos)

        if rand_dir:
            self.agent_dirs.append(self._rand_int(0, 4))

        return pos

    def dir_vec(self, agent_id):
        """
        Get the direction vector for an agent, pointing in the direction
        of forward movement.
        """

        assert agent_id < len(self.agent_dirs) and self.agent_dirs[agent_id] >= 0 and self.agent_dirs[agent_id] < 4
        return DIR_TO_VEC[self.agent_dirs[agent_id]]

    def right_vec(self, agent_id):
        """
        Get the vector pointing to the right of an agent.
        """

        dx, dy = self.dir_vec(agent_id)
        return np.array((-dy, dx))

    def front_pos(self, agent_id):
        """
        Get the position of the cell that is right in front of an agent
        """

        return self.agent_poses[agent_id] + self.dir_vec(agent_id)

    def get_view_coords(self, agent_id, i, j):
        """
        Translate and rotate absolute grid coordinates (i, j) into an
        agent's partially observable view (sub-grid). Note that the resulting
        coordinates may be negative or outside of the agent's view size.
        """

        ax, ay = self.agent_poses[agent_id]
        dx, dy = self.dir_vec(agent_id)
        rx, ry = self.right_vec(agent_id)

        # Compute the absolute coordinates of the top-left view corner
        sz = self.agent_view_size
        hs = self.agent_view_size // 2
        tx = ax + (dx * (sz-1)) - (rx * hs)
        ty = ay + (dy * (sz-1)) - (ry * hs)

        lx = i - tx
        ly = j - ty

        # Project the coordinates of the object relative to the top-left
        # corner onto the agent's own coordinate system
        vx = (rx*lx + ry*ly)
        vy = -(dx*lx + dy*ly)

        return vx, vy

    def get_view_exts(self, agent_id):
        """
        Get the extents of the square set of tiles visible to an agent
        Note: the bottom extent indices are not included in the set
        """

        # Facing right
        if self.agent_dirs[agent_id] == 0:
            topX = self.agent_poses[agent_id][0]
            topY = self.agent_poses[agent_id][1] - self.agent_view_size // 2
        # Facing down
        elif self.agent_dirs[agent_id] == 1:
            topX = self.agent_poses[agent_id][0] - self.agent_view_size // 2
            topY = self.agent_poses[agent_id][1]
        # Facing left
        elif self.agent_dirs[agent_id] == 2:
            topX = self.agent_poses[agent_id][0] - self.agent_view_size + 1
            topY = self.agent_poses[agent_id][1] - self.agent_view_size // 2
        # Facing up
        elif self.agent_dirs[agent_id] == 3:
            topX = self.agent_poses[agent_id][0] - self.agent_view_size // 2
            topY = self.agent_poses[agent_id][1] - self.agent_view_size + 1
        else:
            assert False, "invalid agent direction"

        botX = topX + self.agent_view_size
        botY = topY + self.agent_view_size

        return (topX, topY, botX, botY)

    def relative_coords(self, agent_id, x, y):
        """
        Check if a grid position belongs to an agent's field of view, and returns the corresponding coordinates
        """

        vx, vy = self.get_view_coords(agent_id, x, y)

        if vx < 0 or vy < 0 or vx >= self.agent_view_size or vy >= self.agent_view_size:
            return None

        return vx, vy

    def in_view(self, agent_id, x, y):
        """
        check if a grid position is visible to an agent
        """

        return self.relative_coords(agent_id, x, y) is not None

    def agent_sees(self, agent_id, x, y):
        """
        Check if a non-empty grid position is visible to an agent
        """

        coordinates = self.relative_coords(agent_id, x, y)
        if coordinates is None:
            return False
        vx, vy = coordinates

        obs = self.gen_obs()
        obs_grid, _ = Grid.decode(obs['image'])
        obs_cell = obs_grid.get(vx, vy)
        world_cell = self.grid.get(x, y)

        return obs_cell is not None and obs_cell.type == world_cell.type

    def collision_checker(self, curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, actions, agent_id):
        """
        Check if action will be valid in current position
        """

        # Unintruding action is always valid
        if actions[agent_id] in [self.actions.left, self.actions.right, self.actions.done]:
            return True

        # Forward action
        elif actions[agent_id] == self.actions.forward:

            # World allows agent to move forward
            if fwd_cells[agent_id] == None or fwd_cells[agent_id].can_overlap() or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1 or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in open_door_locations and len(open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:

                # Other agents trying to access same location, so fail
                if len(next_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) > 1 or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in drop_locations or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in close_door_locations:
                    return False

                # Other agent currently in spot, so have to recursively check if they will move
                elif (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in curr_poses:

                    # Agents can't move forward when another agent is moving forward toward them in opposite directions
                    if (self.agent_poses[agent_id][0], self.agent_poses[agent_id][1]) in next_poses and curr_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] in next_poses[(self.agent_poses[agent_id][0], self.agent_poses[agent_id][1])]:
                        return False

                    # Recursively check validity of move at new position
                    return self.collision_checker(curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, actions, curr_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])])

                # Completely valid move forward
                else:
                    return True

            # Invalid attempt to move forward according to world
            else:
                return False

        # Drop action
        elif actions[agent_id] == self.actions.drop:

            # World allows agent to drop item
            if (not fwd_cells[agent_id] or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1) and self.carrying_objects[agent_id]:

                # Other agents trying to access same location, so fail
                if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in next_poses or len(drop_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) > 1:
                    return False

                # Other agent currently in spot, so have to recursively check if they will move
                elif (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in curr_poses:
                    return self.collision_checker(curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, actions, curr_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])])

                # Completely valid move to drop item
                else:
                    return True

            # Invalid attempt to drop item according to world
            else:
                return False

        # Pickup action
        elif actions[agent_id] == self.actions.pickup:

            # Only one agent able to pickup item in world makes action valid
            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and agent_id in pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                return True

            # Invalid attempt to pickup item from world
            else:
                return False

        # Toggle action
        elif actions[agent_id] == self.actions.toggle:

            # Only one agent able to close door in world makes action valid
            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in close_door_locations and agent_id in close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] and len(close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:

                # Other agents trying to access same location, so fail
                if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in next_poses:
                    return False

                # Other agent currently in spot, so have to recursively check if they will move
                elif (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in curr_poses:
                    return self.collision_checker(curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, actions, curr_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])])

                # Completely valid move to close door
                else:
                    return True

            # Only one agent able to open door in world makes action valid
            elif (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in open_door_locations and agent_id in open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] and len(open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                return True

        # Invalid action
        return False

    def step(self, actions):
        self.step_count += 1

        reward = 0
        done = False

        # Get the positions in front of the agents
        fwd_poses = [self.front_pos(agent_id) for agent_id in range(len(self.agent_poses))]

        # Get the contents of the cell in front of the agents
        fwd_cells = [self.grid.get(*fwd_pos) for fwd_pos in fwd_poses]

        # Get attempted next positions of all agents & dropped items
        curr_poses = {}
        next_poses = {}
        drop_locations = {}
        pickup_locations = {}
        open_door_locations = {}
        close_door_locations = {}

        for agent_id, pos in enumerate(self.agent_poses):

            # Store current positions in easily accessible dict
            curr_poses[(pos[0], pos[1])] = agent_id

            # Agent staying in its current location
            if actions[agent_id] != self.actions.forward:
                if (pos[0], pos[1]) not in next_poses:
                    next_poses[(pos[0], pos[1])] = []
                next_poses[(pos[0], pos[1])].append(agent_id)

                # Agent is attempting to drop item into env
                if actions[agent_id] == self.actions.drop:
                    if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in drop_locations:
                        drop_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                    drop_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

                # Agent is attempting to pick up item from env
                elif actions[agent_id] == self.actions.pickup:
                    if fwd_cells[agent_id] and fwd_cells[agent_id].ma_can_pickup(agent_id):
                        if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in pickup_locations:
                            pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                        pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

                # Agent is attempting to toggle object in front of it
                elif actions[agent_id] == self.actions.toggle:
                    if fwd_cells[agent_id] and fwd_cells[agent_id].ma_check_toggle(self, agent_id, fwd_poses[agent_id]):
                        if fwd_cells[agent_id].is_open:
                            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in close_door_locations:
                                close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                            close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)
                        else:
                            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in open_door_locations:
                                open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                            open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

            # Agent is attempting to move forward
            else:
                if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in next_poses:
                    next_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                next_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

        for agent_id, action in enumerate(actions):

            if self.collision_checker(curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, actions, agent_id):

                # Rotate left
                if action == self.actions.left:
                    self.agent_dirs[agent_id] -= 1
                    if self.agent_dirs[agent_id] < 0:
                        self.agent_dirs[agent_id] += 4

                # Rotate right
                elif action == self.actions.right:
                    self.agent_dirs[agent_id] = (self.agent_dirs[agent_id] + 1) % 4

                # Move forward
                elif action == self.actions.forward:
                    if fwd_cells[agent_id] == None or fwd_cells[agent_id].can_overlap() or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        self.agent_poses[agent_id] = fwd_poses[agent_id]
                    if fwd_cells[agent_id] != None and fwd_cells[agent_id].type == 'goal':
                        done = True
                        reward = self._reward()
                    if fwd_cells[agent_id] != None and fwd_cells[agent_id].type == 'lava':
                        done = True

                # Pick up an object
                elif action == self.actions.pickup:
                    if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and agent_id in pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        if self.carrying_objects[agent_id] is None:
                            self.carrying_objects[agent_id] = fwd_cells[agent_id]
                            self.carrying_objects[agent_id].cur_pos = np.array([-1, -1])
                            self.grid.set(*fwd_poses[agent_id], None)

                # Drop an object
                elif action == self.actions.drop:
                    if not fwd_cells[agent_id] and self.carrying_objects[agent_id] or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        self.grid.set(*fwd_poses[agent_id], self.carrying_objects[agent_id])
                        self.carrying_objects[agent_id].cur_pos = fwd_poses[agent_id]
                        self.carrying_objects[agent_id] = None

                # Toggle/activate an object
                elif action == self.actions.toggle:
                    if fwd_cells[agent_id]:
                        fwd_cells[agent_id].ma_toggle(self, agent_id, fwd_poses[agent_id])

                # Done action (not used by default)
                elif action == self.actions.done:
                    pass

                else:
                    assert False, "unknown action"

        if self.step_count >= self.max_steps:
            done = True

        obs = self.gen_obs()

        return obs, reward, done, {}

    def gen_obs_grid(self, agent_id):
        """
        Generate the sub-grid observed by an agent.
        This method also outputs a visibility mask telling us which grid
        cells the agent can actually see.
        """

        topX, topY, botX, botY = self.get_view_exts(agent_id)

        grid = self.grid.slice(topX, topY, self.agent_view_size, self.agent_view_size)

        for i in range(self.agent_dirs[agent_id] + 1):
            grid = grid.rotate_left()

        # Process occluders and visibility
        # Note that this incurs some performance cost
        if not self.see_through_walls:
            vis_mask = grid.process_vis(agent_pos=(self.agent_view_size // 2 , self.agent_view_size - 1))
        else:
            vis_mask = np.ones(shape=(grid.width, grid.height), dtype=np.bool)

        # Make it so the agent sees what it's carrying
        # We do this by placing the carried object at the agent's position
        # in the agent's partially observable view
        agent_pos = grid.width // 2, grid.height - 1
        if self.carrying_objects[agent_id]:
            grid.set(*agent_pos, self.carrying_objects[agent_id])
        else:
            grid.set(*agent_pos, None)

        return grid, vis_mask

    def gen_obs(self):
        """
        Generate the viewable observations of all agents (partially observable, low-resolution encoding)
        """

        combined_obs = []

        for agent_id in range(len(self.agent_poses)):

            grid, vis_mask = self.gen_obs_grid(agent_id)
            relative_agent_poses = [(self.get_view_coords(agent_id, pos[0], pos[1]), other_agent_id, self.agent_dirs[other_agent_id]) for other_agent_id, pos in enumerate(self.agent_poses) if agent_id != other_agent_id]

            # Encode the partially observable view into a numpy array
            image = grid.ma_encode(vis_mask=vis_mask, agent_poses=relative_agent_poses)

            assert hasattr(self, 'mission'), "environments must define a textual mission string"

            # Observations are dictionaries containing:
            # - an image (partially observable view of the environment)
            # - the agent's direction/orientation (acting as a compass)
            # - a textual mission string (instructions for the agent)
            obs = {
                'image': image,
                'direction': self.agent_dirs[agent_id],
                'mission': self.mission
            }

            combined_obs.append(obs)

        return combined_obs

    def get_obs_render(self, obs, tile_size=TILE_PIXELS//2):
        """
        Render an agent observation for visualization
        """

        grid, vis_mask = Grid.decode(obs)

        # Render the whole grid
        img = grid.render(
            tile_size,
            agent_pos=(self.agent_view_size // 2, self.agent_view_size - 1),
            agent_dir=3,
            highlight_mask=vis_mask
        )

        return img

    def render(self, mode='human', close=False, highlight=True, tile_size=TILE_PIXELS):
        """
        Render the whole-grid human view
        """

        if close:
            if self.window:
                self.window.close()
            return

        if mode == 'human' and not self.window:
            import gym_minigrid.window
            self.window = gym_minigrid.window.Window('gym_minigrid')
            self.window.show(block=False)

        # Mask of which cells to highlight
        highlight_mask = np.zeros(shape=(self.width, self.height), dtype=np.bool)

        for agent_id in range(len(self.agent_poses)):
            # Compute which cells are visible to the agent
            _, vis_mask = self.gen_obs_grid(agent_id)

            # Compute the world coordinates of the bottom-left corner
            # of the agent's view area
            f_vec = self.dir_vec(agent_id)
            r_vec = self.right_vec(agent_id)
            top_left = self.agent_poses[agent_id] + f_vec * (self.agent_view_size-1) - r_vec * (self.agent_view_size // 2)

            # For each cell in the visibility mask
            for vis_j in range(0, self.agent_view_size):
                for vis_i in range(0, self.agent_view_size):
                    # If this cell is not visible, don't highlight it
                    if not vis_mask[vis_i, vis_j]:
                        continue

                    # Compute the world coordinates of this cell
                    abs_i, abs_j = top_left - (f_vec * vis_j) + (r_vec * vis_i)

                    if abs_i < 0 or abs_i >= self.width:
                        continue
                    if abs_j < 0 or abs_j >= self.height:
                        continue

                    # Mark this cell to be highlighted
                    highlight_mask[abs_i, abs_j] = True

        # Render the whole grid
        img = self.grid.ma_render(
            tile_size,
            self.agent_poses,
            self.agent_dirs,
            highlight_mask=highlight_mask if highlight else None
        )

        if mode == 'human':
            self.window.show_img(img)
            self.window.set_caption(self.mission)

        return img

    def close(self):
        if self.window:
            self.window.close()
        return

class CommunicativeMultiAgentMiniGridEnv(MultiAgentMiniGridEnv):
    """
    2D grid world game environment with multi-agent support and communication between agents
    """

    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 10
    }

    def __init__(
        self,
        grid_size=None,
        width=None,
        height=None,
        max_steps=100,
        see_through_walls=False,
        seed=1337,
        agent_view_size=7
    ):
        # Can't set both grid_size and width/height
        if grid_size:
            assert width == None and height == None
            width = grid_size
            height = grid_size

        # Action enumeration for this environment
        self.actions = MultiAgentMiniGridEnv.Actions

        # Actions are discrete integer values
        self.action_space = spaces.Discrete(len(self.actions))

        # Number of cells (width and height) in the agent view
        assert agent_view_size % 2 == 1
        assert agent_view_size >= 3
        self.agent_view_size = agent_view_size

        # Observations are dictionaries containing an
        # encoding of the grid and a textual 'mission' string
        self.observation_space = spaces.Box(
            low=0,
            high=255,
            # shape=(self.agent_view_size, self.agent_view_size, 3),
            shape=(width, height, 3),
            dtype='uint8'
        )
        self.observation_space = spaces.Dict({
            'image': self.observation_space
        })

        # Range of possible rewards
        self.reward_range = (0, 1)

        # Window to use for human rendering mode
        self.window = None

        # Environment configuration
        self.width = width
        self.height = height
        self.max_steps = max_steps
        self.see_through_walls = see_through_walls

        # Current positions and directions of the agents
        self.agent_poses = []
        self.agent_dirs = []

        # Initialize the RNG
        self.seed(seed=seed)

        # Initialize the state
        self.reset()

    def reset(self):
        # Current positions and directions of the agents
        self.agent_poses = []
        self.agent_dirs = []

        # Generate a new random grid at the start of each episode
        # To keep the same grid for each episode, call env.seed() with
        # the same seed before calling env.reset()
        self._gen_grid(self.width, self.height)

        # These fields should be defined by _gen_grid
        assert self.agent_poses
        assert self.agent_dirs

        # Check that the agent doesn't overlap with an object
        for pos in self.agent_poses:
            start_cell = self.grid.get(*pos)
            assert start_cell is None or start_cell.can_overlap()

        # Item picked up, being carried, initially nothing for all agents
        self.carrying_objects = [None for i in self.agent_poses]

        # Step count since episode start
        self.step_count = 0

        # Return first observation
        obs, _ = self.gen_obs_comm()

        # Store this obs in case communication occurs in next episode
        self.orig_agent_poses = deepcopy(self.agent_poses)
        self.past_obs = deepcopy(obs)

        return obs

    def step(self, actions):
        self.step_count += 1

        reward = 0
        done = False

        # Get the positions in front of the agents
        fwd_poses = [self.front_pos(agent_id) for agent_id in range(len(self.agent_poses))]

        # Get the contents of the cell in front of the agents
        fwd_cells = [self.grid.get(*fwd_pos) for fwd_pos in fwd_poses]

        # Get attempted next positions of all agents & dropped items
        curr_poses = {}
        next_poses = {}
        drop_locations = {}
        pickup_locations = {}
        open_door_locations = {}
        close_door_locations = {}

        # Get physical actions from actions list
        phys_actions = [action[0] for action in actions]

        for agent_id, pos in enumerate(self.agent_poses):

            # Store current positions in easily accessible dict
            curr_poses[(pos[0], pos[1])] = agent_id

            # Agent staying in its current location
            if phys_actions[agent_id] != self.actions.forward:
                if (pos[0], pos[1]) not in next_poses:
                    next_poses[(pos[0], pos[1])] = []
                next_poses[(pos[0], pos[1])].append(agent_id)

                # Agent is attempting to drop item into env
                if phys_actions[agent_id] == self.actions.drop:
                    if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in drop_locations:
                        drop_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                    drop_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

                # Agent is attempting to pick up item from env
                elif phys_actions[agent_id] == self.actions.pickup:
                    if fwd_cells[agent_id] and fwd_cells[agent_id].ma_can_pickup(agent_id):
                        if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in pickup_locations:
                            pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                        pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

                # Agent is attempting to toggle object in front of it
                elif phys_actions[agent_id] == self.actions.toggle:
                    if fwd_cells[agent_id] and fwd_cells[agent_id].ma_check_toggle(self, agent_id, fwd_poses[agent_id]):
                        if fwd_cells[agent_id].is_open:
                            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in close_door_locations:
                                close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                            close_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)
                        else:
                            if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in open_door_locations:
                                open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                            open_door_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

            # Agent is attempting to move forward
            else:
                if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) not in next_poses:
                    next_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] = []
                next_poses[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])].append(agent_id)

        for agent_id, action in enumerate(phys_actions):

            if self.collision_checker(curr_poses, fwd_poses, fwd_cells, next_poses, drop_locations, pickup_locations, open_door_locations, close_door_locations, phys_actions, agent_id):

                # Rotate left
                if action == self.actions.left:
                    self.agent_dirs[agent_id] -= 1
                    if self.agent_dirs[agent_id] < 0:
                        self.agent_dirs[agent_id] += 4

                # Rotate right
                elif action == self.actions.right:
                    self.agent_dirs[agent_id] = (self.agent_dirs[agent_id] + 1) % 4

                # Move forward
                elif action == self.actions.forward:
                    if fwd_cells[agent_id] == None or fwd_cells[agent_id].can_overlap() or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        self.agent_poses[agent_id] = fwd_poses[agent_id]
                    if fwd_cells[agent_id] != None and fwd_cells[agent_id].type == 'goal':
                        done = True
                        reward = self._reward()
                    if fwd_cells[agent_id] != None and fwd_cells[agent_id].type == 'lava':
                        done = True

                # Pick up an object
                elif action == self.actions.pickup:
                    if (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and agent_id in pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])] and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        if self.carrying_objects[agent_id] is None:
                            self.carrying_objects[agent_id] = fwd_cells[agent_id]
                            self.carrying_objects[agent_id].cur_pos = np.array([-1, -1])
                            self.grid.set(*fwd_poses[agent_id], None)

                # Drop an object
                elif action == self.actions.drop:
                    if not fwd_cells[agent_id] and self.carrying_objects[agent_id] or (fwd_poses[agent_id][0], fwd_poses[agent_id][1]) in pickup_locations and len(pickup_locations[(fwd_poses[agent_id][0], fwd_poses[agent_id][1])]) == 1:
                        self.grid.set(*fwd_poses[agent_id], self.carrying_objects[agent_id])
                        self.carrying_objects[agent_id].cur_pos = fwd_poses[agent_id]
                        self.carrying_objects[agent_id] = None

                # Toggle/activate an object
                elif action == self.actions.toggle:
                    if fwd_cells[agent_id]:
                        fwd_cells[agent_id].ma_toggle(self, agent_id, fwd_poses[agent_id])

                # Done action (not used by default)
                elif action == self.actions.done:
                    pass

                else:
                    assert False, "unknown action"

        if self.step_count >= self.max_steps:
            done = True

        # Get communication actions from actions list
        comm_actions = [action[1] for action in actions]
        obs, shared_obs = self.gen_obs_comm(comm_actions)
        self.orig_agent_poses = deepcopy(self.agent_poses)
        self.past_obs = deepcopy(obs)

        return shared_obs, reward, done, {}

    def gen_obs_grid_comm(self, agent_id):
        """
        Generate the sub-grid observed by an agent.
        This method also outputs a visibility mask telling us which grid
        cells the agent can actually see.
        """

        topX, topY, botX, botY = self.get_view_exts(agent_id)
        if topX < 0:
            topX = 0
        if topY < 0:
            topY = 0
        if botX > self.grid.width:
            botX = self.grid.width
        if botY > self.grid.height:
            botY = self.grid.height

        grid = self.grid.slice(topX, topY, botX - topX, botY - topY)

        for i in range(self.agent_dirs[agent_id] + 1):
            grid = grid.rotate_left()

        # Facing right
        if self.agent_dirs[agent_id] == 0:
            agent_rel_x = self.agent_poses[agent_id][1] - topY
        # Facing down
        elif self.agent_dirs[agent_id] == 1:
            agent_rel_x = botX - 1 - self.agent_poses[agent_id][0]
        # Facing left
        elif self.agent_dirs[agent_id] == 2:
            agent_rel_x = botY - 1 - self.agent_poses[agent_id][1]
        # Facing up
        elif self.agent_dirs[agent_id] == 3:
            agent_rel_x = self.agent_poses[agent_id][0] - topX
        else:
            assert False, "invalid agent direction"

        # Process occluders and visibility
        # Note that this incurs some performance cost
        if not self.see_through_walls:
            vis_mask = grid.process_vis(agent_pos=(agent_rel_x , grid.height - 1))
        else:
            vis_mask = np.ones(shape=(grid.width, grid.height), dtype=np.bool)

        # Rotate grid & mask back to original pose
        for i in range(3 - self.agent_dirs[agent_id]):
            grid = grid.rotate_left()

        vis_mask = np.rot90(vis_mask, self.agent_dirs[agent_id] + 1)

        # Fill in partial obs grid & mask into complete obs space grid & mask
        final_grid = self.grid.copy()
        final_vis_mask = np.zeros(shape=(self.grid.width, self.grid.height), dtype=np.bool)

        for x in range(grid.width):
            for y in range(grid.height):
                final_grid.set(x + topX, y + topY, grid.get(x, y))
                final_vis_mask[x + topX][y + topY] = vis_mask[x][y]

        # Make it so the agent sees what it's carrying
        # We do this by placing the carried object at the agent's position
        if self.carrying_objects[agent_id]:
            final_grid.set(*(self.agent_poses[agent_id]), self.carrying_objects[agent_id])
        else:
            final_grid.set(*(self.agent_poses[agent_id]), None)

        return final_grid, final_vis_mask

    def gen_obs_comm(self, comm_actions=None):
        """
        Generate the viewable observations of all agents (partially observable, low-resolution encoding)
        """

        combined_obs = []
        shared_obs = []

        for agent_id in range(len(self.agent_poses)):

            grid, vis_mask = self.gen_obs_grid_comm(agent_id)

            # Encode the partially observable view into a numpy array
            image = grid.ma_encode(vis_mask=vis_mask, agent_poses=[(pos, other_agent_id, self.agent_dirs[other_agent_id]) for other_agent_id, pos in enumerate(self.agent_poses) if agent_id != other_agent_id])

            assert hasattr(self, 'mission'), "environments must define a textual mission string"

            # Observations are dictionaries containing:
            # - an image (partially observable view of the environment)
            # - the agent's direction/orientation (acting as a compass)
            # - a textual mission string (instructions for the agent)
            obs = {
                'image': image,
                'direction': self.agent_dirs[agent_id],
                'mission': self.mission
            }

            combined_obs.append(deepcopy(obs))
            shared_obs.append(deepcopy(obs))

            if comm_actions:
                for other_agent_id, communicate in enumerate(comm_actions):
                    if agent_id != other_agent_id and communicate:
                        if np.sqrt(                                                                                     \
                                (self.orig_agent_poses[agent_id][0] - self.orig_agent_poses[other_agent_id][0])**2 +    \
                                (self.orig_agent_poses[agent_id][1] - self.orig_agent_poses[other_agent_id][1])**2      \
                                ) < 3:

                            for i in range(grid.width):
                                for j in range(grid.height):
                                    if not vis_mask[i][j]:
                                        if self.past_obs[other_agent_id]['image'][i][j][0] not in [0, OBJECT_TO_IDX['agent']]:
                                            shared_obs[agent_id]['image'][i][j][0] = self.past_obs[other_agent_id]['image'][i][j][0]
                                            shared_obs[agent_id]['image'][i][j][1] = self.past_obs[other_agent_id]['image'][i][j][1]
                                            shared_obs[agent_id]['image'][i][j][2] = self.past_obs[other_agent_id]['image'][i][j][2]

        return combined_obs, shared_obs
