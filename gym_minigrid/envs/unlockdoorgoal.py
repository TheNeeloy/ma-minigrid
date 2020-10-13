from gym_minigrid.roomgrid import RoomGrid, MARoomGrid, CommMARoomGrid
from gym_minigrid.register import register
from gym_minigrid.minigrid import IDX_TO_COLOR, COLOR_NAMES, Door, Goal

class MAUnlockDoorGoal(MARoomGrid):
    """
    Colored goals are placed behind locked doors of the same color.
    Agents need to pick up their colored key and go to their respective
    goal to receive their reward. Episode ends when all agents get to 
    their colored goal.
    """

    def __init__(
        self,
        seed=None,
        num_agents=2
    ):
        self.num_agents = num_agents

        super().__init__(
            room_size=3,
            num_rows=num_agents,
            max_steps=30*3**2,
            seed=seed,
        )

    def _gen_grid(self, width, height):
        super()._gen_grid(width, height)

        potential_colors = [IDX_TO_COLOR[i] for i in range(min(self.num_agents, len(COLOR_NAMES)))]
        key_rows = [i for i in range(self.num_rows)]
        locked_door_rows = [i for i in range(self.num_rows)]

        self.goal_poses = {}

        # Add keys, goals, and locked doors
        for curr_color in potential_colors:
            curr_key_row = self._rand_elem(key_rows)
            key_rows.remove(curr_key_row)
            self.add_object(0, curr_key_row, 'key', curr_color)

            curr_locked_door_row = self._rand_elem(locked_door_rows)
            locked_door_rows.remove(curr_locked_door_row)
            curr_goal, curr_goal_pos = self.add_object(2, curr_locked_door_row, 'goal', None)
            curr_goal.color = curr_color
            self.goal_poses[curr_color] = curr_goal_pos

            self.add_door(2, curr_locked_door_row, 2, color=curr_color, locked=True)

        # Remove walls
        for j in range(1, self.num_rows):
            self.remove_wall(0, j, 3)
            self.remove_wall(1, j, 3)
        for j in range(1, self.grid.height - 1):
            self.grid.set(2, j, None)

        # Place the agents in the middle
        self.agent_poses = []
        self.agent_dirs = []
        for _ in range(self.num_agents):
            self.place_agent(1)
        self.agent_poses = self.agent_poses[ : self.num_agents]
        self.agent_dirs = self.agent_dirs[ : self.num_agents]

        self.mission = "get to your respective colored goal"

    def step(self, action):
        obs, _, done, info = super().step(action)

        rewards = []
        done = True
        for agent_id, agent_pos in enumerate(self.agent_poses):
            if agent_pos[0] == self.goal_poses[IDX_TO_COLOR[agent_id]][0] and agent_pos[1] == self.goal_poses[IDX_TO_COLOR[agent_id]][1]:
                rewards.append(1)
            else:
                rewards.append(0)
                done = False

        return obs, rewards, done, info

class CommMAUnlockDoorGoal(CommMARoomGrid):
    """
    Colored goals are placed behind locked doors of the same color.
    Agents need to pick up their colored key and go to their respective
    goal to receive their reward. Episode ends when all agents get to 
    their colored goal.
    """

    def __init__(
        self,
        seed=None,
        num_agents=2
    ):
        self.num_agents = num_agents

        super().__init__(
            room_size=3,
            num_rows=num_agents,
            max_steps=30*3**2,
            seed=seed,
        )

    def _gen_grid(self, width, height):
        super()._gen_grid(width, height)

        potential_colors = [IDX_TO_COLOR[i] for i in range(min(self.num_agents, len(COLOR_NAMES)))]
        key_rows = [i for i in range(self.num_rows)]
        locked_door_rows = [i for i in range(self.num_rows)]

        self.goal_poses = {}

        # Add keys, goals, and locked doors
        for curr_color in potential_colors:
            curr_key_row = self._rand_elem(key_rows)
            key_rows.remove(curr_key_row)
            self.add_object(0, curr_key_row, 'key', curr_color)

            curr_locked_door_row = self._rand_elem(locked_door_rows)
            locked_door_rows.remove(curr_locked_door_row)
            curr_goal, curr_goal_pos = self.add_object(2, curr_locked_door_row, 'goal', None)
            curr_goal.color = curr_color
            self.goal_poses[curr_color] = curr_goal_pos

            self.add_door(2, curr_locked_door_row, 2, color=curr_color, locked=True)

        # Remove walls
        for j in range(1, self.num_rows):
            self.remove_wall(0, j, 3)
            self.remove_wall(1, j, 3)
        for j in range(1, self.grid.height - 1):
            self.grid.set(2, j, None)

        # Place the agents in the middle
        self.agent_poses = []
        self.agent_dirs = []
        for _ in range(self.num_agents):
            self.place_agent(1)
        self.agent_poses = self.agent_poses[ : self.num_agents]
        self.agent_dirs = self.agent_dirs[ : self.num_agents]

        self.mission = "get to your respective colored goal"

    def step(self, action):
        obs, _, done, info = super().step(action)

        rewards = []
        done = True
        for agent_id, agent_pos in enumerate(self.agent_poses):
            if agent_pos[0] == self.goal_poses[IDX_TO_COLOR[agent_id]][0] and agent_pos[1] == self.goal_poses[IDX_TO_COLOR[agent_id]][1]:
                rewards.append(1)
            else:
                rewards.append(0)
                done = False

        return obs, rewards, done, info

class MAUnlockDoorGoalA1(MAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=1
        )

class MAUnlockDoorGoalA2(MAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=2
        )

class MAUnlockDoorGoalA3(MAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=3
        )

class CommMAUnlockDoorGoalA1(CommMAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=1
        )

class CommMAUnlockDoorGoalA2(CommMAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=2
        )

class CommMAUnlockDoorGoalA3(CommMAUnlockDoorGoal):
    def __init__(self, seed=None):
        super().__init__(
            seed=seed,
            num_agents=3
        )

register(
    id='MiniGrid-MA-UnlockDoorGoalA1-v0',
    entry_point='gym_minigrid.envs:MAUnlockDoorGoalA1'
)

register(
    id='MiniGrid-MA-UnlockDoorGoalA2-v0',
    entry_point='gym_minigrid.envs:MAUnlockDoorGoalA2'
)

register(
    id='MiniGrid-MA-UnlockDoorGoalA3-v0',
    entry_point='gym_minigrid.envs:MAUnlockDoorGoalA3'
)

register(
    id='MiniGrid-Comm-MA-UnlockDoorGoalA1-v0',
    entry_point='gym_minigrid.envs:CommMAUnlockDoorGoalA1'
)

register(
    id='MiniGrid-Comm-MA-UnlockDoorGoalA2-v0',
    entry_point='gym_minigrid.envs:CommMAUnlockDoorGoalA2'
)

register(
    id='MiniGrid-Comm-MA-UnlockDoorGoalA3-v0',
    entry_point='gym_minigrid.envs:CommMAUnlockDoorGoalA3'
)
