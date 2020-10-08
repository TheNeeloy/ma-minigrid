from gym_minigrid.roomgrid import RoomGrid
from gym_minigrid.roomgrid import MARoomGrid
from gym_minigrid.register import register
from gym_minigrid.minigrid import IDX_TO_COLOR, COLOR_NAMES, Door, Goal

class KeyCorridor(RoomGrid):
    """
    A ball is behind a locked door, the key is placed in a
    random room.
    """

    def __init__(
        self,
        num_rows=3,
        obj_type="ball",
        room_size=6,
        seed=None
    ):
        self.obj_type = obj_type

        super().__init__(
            room_size=room_size,
            num_rows=num_rows,
            max_steps=30*room_size**2,
            seed=seed,
        )

    def _gen_grid(self, width, height):
        super()._gen_grid(width, height)

        # Connect the middle column rooms into a hallway
        for j in range(1, self.num_rows):
            self.remove_wall(1, j, 3)

        # Add a locked door on the bottom right
        # Add an object behind the locked door
        room_idx = self._rand_int(0, self.num_rows)
        door, _ = self.add_door(2, room_idx, 2, locked=True)
        obj, _ = self.add_object(2, room_idx, kind=self.obj_type)

        # Add a key in a random room on the left side
        self.add_object(0, self._rand_int(0, self.num_rows), 'key', door.color)

        # Place the agent in the middle
        self.place_agent(1, self.num_rows // 2)

        # Make sure all rooms are accessible
        self.connect_all()

        self.obj = obj
        self.mission = "pick up the %s %s" % (obj.color, obj.type)

    def step(self, action):
        obs, reward, done, info = super().step(action)

        if action == self.actions.pickup:
            if self.carrying and self.carrying == self.obj:
                reward = self._reward()
                done = True

        return obs, reward, done, info

class MAKeyCorridor(MARoomGrid):
    """
    A ball is behind a locked door, the key is placed in a
    random room. Any agent needs to pick up the ball to end the episode.
    """

    def __init__(
        self,
        num_rows=2,
        obj_type="goal",
        room_size=4,
        seed=None,
        num_agents=3
    ):
        self.obj_type = obj_type
        self.num_agents = num_agents

        super().__init__(
            room_size=room_size,
            num_rows=num_rows,
            max_steps=30*room_size**2,
            seed=seed,
        )

    def _gen_grid(self, width, height):
        super()._gen_grid(width, height)

        # Connect the middle column rooms into a hallway
        for j in range(1, self.num_rows):
            self.remove_wall(1, j, 3)

        # Add a locked door on the bottom right
        # Add an object behind the locked door
        room_idx = self._rand_int(0, self.num_rows)

        potential_colors = [IDX_TO_COLOR[i] for i in range(min(self.num_agents, len(COLOR_NAMES)))]
        first_door_color = self._rand_elem(potential_colors)
        first_door, _ = self.add_door(2, room_idx, 2, color=first_door_color, locked=True)

        if len(potential_colors) > 2:
            self.grid.horz_wall(first_door.cur_pos[0] + 1, first_door.cur_pos[1] + 1, len(potential_colors) - 2)
            self.grid.horz_wall(first_door.cur_pos[0] + 1, first_door.cur_pos[1] - 1, len(potential_colors) - 2)

        potential_colors.remove(first_door_color)
        
        door_num = 1
        while potential_colors:
            curr_door_color = self._rand_elem(potential_colors)
            potential_colors.remove(curr_door_color)
            door = Door(curr_door_color, is_locked=True)
            pos = (first_door.cur_pos[0] + door_num, first_door.cur_pos[1])
            self.grid.set(*pos, door)
            door.cur_pos = pos
            door_num = door_num + 1

        potential_colors = [IDX_TO_COLOR[i] for i in range(min(self.num_agents, len(COLOR_NAMES)))]

        # Add object to be picked up at end of episode behind locked doors
        if self.obj_type == 'goal':
            obj, _ = self.add_object(2, room_idx, kind=self.obj_type)
        else:
            obj, _ = self.add_object(2, room_idx, kind=self.obj_type, color=self._rand_elem(potential_colors))

        # Add keys randomly in rooms
        possible_key_locations = [(0, i) for i in range(self.num_rows)]
        for row in range(self.num_rows):
            if row != room_idx:
                possible_key_locations.append((2, row))

        for color in potential_colors:
            curr_room = self._rand_elem(possible_key_locations)
            possible_key_locations.remove(curr_room)
            self.add_object(curr_room[0], curr_room[1], 'key', color)

        # Place the agents in the middle
        self.agent_poses = []
        self.agent_dirs = []
        for _ in range(self.num_agents):
            self.place_agent(1, self.num_rows // 2)
        self.agent_poses = self.agent_poses[ : self.num_agents]
        self.agent_dirs = self.agent_dirs[ : self.num_agents]

        # Make sure all rooms are accessible
        self.connect_all()

        self.obj = obj
        if self.obj_type != 'goal':
            self.mission = "pick up the %s %s" % (obj.color, obj.type)
        else:
            self.mission = "get to the green goal square"

    def step(self, action):
        obs, reward, done, info = super().step(action)

        if self.obj_type != 'goal':
            if self.actions.pickup in action:
                if self.obj in self.carrying_objects:
                    reward = self._reward()
                    done = True

        return obs, reward, done, info

class KeyCorridorS3R1(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=1,
            seed=seed
        )

class KeyCorridorS3R2(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=2,
            seed=seed
        )

class KeyCorridorS3R3(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=3,
            seed=seed
        )

class KeyCorridorS4R3(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=4,
            num_rows=3,
            seed=seed
        )

class KeyCorridorS5R3(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=5,
            num_rows=3,
            seed=seed
        )

class KeyCorridorS6R3(KeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=6,
            num_rows=3,
            seed=seed
        )

class MAKeyCorridorS3R1(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=1,
            seed=seed
        )

class MAKeyCorridorS3R2(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=2,
            seed=seed
        )

class MAKeyCorridorS3R3(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=3,
            num_rows=3,
            seed=seed
        )

class MAKeyCorridorS4R3(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=4,
            num_rows=3,
            seed=seed
        )

class MAKeyCorridorS5R3(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=5,
            num_rows=3,
            seed=seed
        )

class MAKeyCorridorS6R3(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=6,
            num_rows=3,
            seed=seed
        )

class MAKeyCorridorS4R2A2(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=4,
            num_rows=2,
            seed=seed,
            num_agents=2
        )

class MAKeyCorridorS4R2A3(MAKeyCorridor):
    def __init__(self, seed=None):
        super().__init__(
            room_size=4,
            num_rows=2,
            seed=seed,
            num_agents=3
        )

register(
    id='MiniGrid-KeyCorridorS3R1-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS3R1'
)

register(
    id='MiniGrid-KeyCorridorS3R2-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS3R2'
)

register(
    id='MiniGrid-KeyCorridorS3R3-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS3R3'
)

register(
    id='MiniGrid-KeyCorridorS4R3-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS4R3'
)

register(
    id='MiniGrid-KeyCorridorS5R3-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS5R3'
)

register(
    id='MiniGrid-KeyCorridorS6R3-v0',
    entry_point='gym_minigrid.envs:KeyCorridorS6R3'
)

register(
    id='MiniGrid-MA-KeyCorridorS3R1-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS3R1'
)

register(
    id='MiniGrid-MA-KeyCorridorS3R2-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS3R2'
)

register(
    id='MiniGrid-MA-KeyCorridorS3R3-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS3R3'
)

register(
    id='MiniGrid-MA-KeyCorridorS4R3-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS4R3'
)

register(
    id='MiniGrid-MA-KeyCorridorS5R3-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS5R3'
)

register(
    id='MiniGrid-MA-KeyCorridorS6R3-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS6R3'
)

register(
    id='MiniGrid-MA-KeyCorridorS4R2A2-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS4R2A2'
)

register(
    id='MiniGrid-MA-KeyCorridorS4R2A3-v0',
    entry_point='gym_minigrid.envs:MAKeyCorridorS4R2A3'
)
