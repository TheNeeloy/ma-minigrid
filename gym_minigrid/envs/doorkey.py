from gym_minigrid.minigrid import *
from gym_minigrid.register import register

class DoorKeyEnv(MiniGridEnv):
    """
    Environment with a door and key, sparse reward
    """

    def __init__(self, size=8):
        super().__init__(
            grid_size=size,
            max_steps=10*size*size
        )

    def _gen_grid(self, width, height):
        # Create an empty grid
        self.grid = Grid(width, height)

        # Generate the surrounding walls
        self.grid.wall_rect(0, 0, width, height)

        # Place a goal in the bottom-right corner
        self.put_obj(Goal(), width - 2, height - 2)

        # Create a vertical splitting wall
        splitIdx = self._rand_int(2, width-2)
        self.grid.vert_wall(splitIdx, 0)

        # Place the agent at a random position and orientation
        # on the left side of the splitting wall
        self.place_agent(size=(splitIdx, height))

        # Place a door in the wall
        doorIdx = self._rand_int(1, width-2)
        self.put_obj(Door('yellow', is_locked=True), splitIdx, doorIdx)

        # Place a yellow key on the left side
        self.place_obj(
            obj=Key('yellow'),
            top=(0, 0),
            size=(splitIdx, height)
        )

        self.mission = "use the key to open the door and then get to the goal"

class MADoorKeyEnv(MultiAgentMiniGridEnv):
    """
    Multi-Agent environment with a door and key, sparse reward
    """

    def __init__(self, size=8):
        super().__init__(
            grid_size=size,
            max_steps=10*size*size
        )

    def _gen_grid(self, width, height):
        # Create an empty grid
        self.grid = Grid(width, height)

        # Generate the surrounding walls
        self.grid.wall_rect(0, 0, width, height)

        # Place a goal in the bottom-right corner
        self.put_obj(Goal(), width - 2, height - 2)

        # Create a vertical splitting wall
        splitIdx = self._rand_int(2, width-2)
        self.grid.vert_wall(splitIdx, 0)

        # Place the agent at a random position and orientation
        # on the left side of the splitting wall
        self.place_agent(size=(splitIdx, height))
        self.place_agent(size=(splitIdx, height))
        self.place_agent(size=(splitIdx, height))
        
        # Place a door in the wall
        doorIdx = self._rand_int(1, width-2)
        self.put_obj(Door('green', is_locked=True), splitIdx, doorIdx)

        # Place a green key on the left side
        self.place_obj(
            obj=Key('green'),
            top=(0, 0),
            size=(splitIdx, height)
        )

        # Place a blue key on the left side
        self.place_obj(
            obj=Key('blue'),
            top=(0, 0),
            size=(splitIdx, height)
        )

        self.mission = "use the key to open the door and then get to the goal"

class DoorKeyEnv5x5(DoorKeyEnv):
    def __init__(self):
        super().__init__(size=5)

class DoorKeyEnv6x6(DoorKeyEnv):
    def __init__(self):
        super().__init__(size=6)

class DoorKeyEnv16x16(DoorKeyEnv):
    def __init__(self):
        super().__init__(size=16)

class MADoorKeyEnv5x5(MADoorKeyEnv):
    def __init__(self):
        super().__init__(size=5)

class MADoorKeyEnv6x6(MADoorKeyEnv):
    def __init__(self):
        super().__init__(size=6)

class MADoorKeyEnv16x16(MADoorKeyEnv):
    def __init__(self):
        super().__init__(size=16)

register(
    id='MiniGrid-DoorKey-5x5-v0',
    entry_point='gym_minigrid.envs:DoorKeyEnv5x5'
)

register(
    id='MiniGrid-DoorKey-6x6-v0',
    entry_point='gym_minigrid.envs:DoorKeyEnv6x6'
)

register(
    id='MiniGrid-DoorKey-8x8-v0',
    entry_point='gym_minigrid.envs:DoorKeyEnv'
)

register(
    id='MiniGrid-DoorKey-16x16-v0',
    entry_point='gym_minigrid.envs:DoorKeyEnv16x16'
)

register(
    id='MiniGrid-MA-DoorKey-5x5-v0',
    entry_point='gym_minigrid.envs:MADoorKeyEnv5x5'
)

register(
    id='MiniGrid-MA-DoorKey-6x6-v0',
    entry_point='gym_minigrid.envs:MADoorKeyEnv6x6'
)

register(
    id='MiniGrid-MA-DoorKey-8x8-v0',
    entry_point='gym_minigrid.envs:MADoorKeyEnv'
)

register(
    id='MiniGrid-MA-DoorKey-16x16-v0',
    entry_point='gym_minigrid.envs:MADoorKeyEnv16x16'
)