#!/usr/bin/env python3

import time
import argparse
import numpy as np
import gym
import gym_minigrid
from gym_minigrid.wrappers import *
from gym_minigrid.window import Window

def redraw(img):
    if not args.agent_view:
        img = env.render('rgb_array', tile_size=args.tile_size)

    window.show_img(img)

def reset():
    if args.seed != -1:
        env.seed(args.seed)

    obs = env.reset()

    if hasattr(env, 'mission'):
        print('Mission: %s' % env.mission)
        window.set_caption(env.mission)

    redraw(obs)

def step(actions):
    obs, reward, done, info = env.step(actions)
    print('step=%s, reward=%.2f' % (env.step_count, reward))

    if done:
        print('done!')
        reset()
    else:
        redraw(obs)

current_agent = 0
agent_actions = []

def key_handler(event):
    print('pressed', event.key)

    if event.key == 'escape':
        window.close()
        return

    if event.key == 'backspace':
        reset()
        return

    global current_agent
    global agent_actions

    if event.key == 'left':
        agent_actions.append(env.actions.left)
        # step(env.actions.left)
        # return
    if event.key == 'right':
        agent_actions.append(env.actions.right)
        # step(env.actions.right)
        # return
    if event.key == 'up':
        agent_actions.append(env.actions.forward)
        # step(env.actions.forward)
        # return

    # Spacebar
    if event.key == ' ':
        agent_actions.append(env.actions.toggle)
        # step(env.actions.toggle)
        # return
    if event.key == 'pageup':
        agent_actions.append(env.actions.pickup)
        # step(env.actions.pickup)
        # return
    if event.key == 'pagedown':
        agent_actions.append(env.actions.drop)
        # step(env.actions.drop)
        # return

    if event.key == 'enter':
        agent_actions.append(env.actions.done)
        # step(env.actions.done)
        # return

    # print(current_agent)

    if current_agent:
        step(agent_actions)
        current_agent = 0
        agent_actions = []
    else:
        current_agent = 1

parser = argparse.ArgumentParser()
parser.add_argument(
    "--env",
    help="gym environment to load",
    default='MiniGrid-MA-DoorKey-16x16-v0'
)
parser.add_argument(
    "--seed",
    type=int,
    help="random seed to generate the environment with",
    default=-1
)
parser.add_argument(
    "--tile_size",
    type=int,
    help="size at which to render tiles",
    default=32
)
parser.add_argument(
    '--agent_view',
    default=False,
    help="draw the agent sees (partially observable view)",
    action='store_true'
)

args = parser.parse_args()

env = gym.make(args.env)

if args.agent_view:
    # print('in partial obs view')
    env = RGBImgPartialObsWrapper(env)
    env = ImgObsWrapper(env)

window = Window('gym_minigrid - ' + args.env)
window.reg_key_handler(key_handler)

reset()

# Blocking event loop
window.show(block=True)
