import time
import math

from datetime import datetime

import serpent.utilities

from serpent.enums import InputControlTypes

from serpent.config import config
from serpent.frame_grabber import FrameGrabber
from serpent.game_agent import GameAgent
from serpent.input_controller import KeyboardKey

from serpent.machine_learning.reinforcement_learning.agents.random_agent import RandomAgent
from serpent.machine_learning.reinforcement_learning.agents.rainbow_dqn_agent import RainbowDQNAgent
from serpent.machine_learning.reinforcement_learning.agents.recorder_agent import RecorderAgent


class SerpentAIsaacGameAgent(GameAgent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.frame_handlers["PLAY"] = self.handle_play
        self.frame_handler_setups["PLAY"] = self.setup_play

    def setup_play(self):
        Bosses = self.game.environment_data["BOSSES"]
        DoubleBosses = self.game.environment_data["DOUBLE_BOSSES"]
        MiniBosses = self.game.environment_data["MINI_BOSSES"]
        Items = self.game.environment_data["ITEMS"]

        self.environment = self.game.environments["BOSS_FIGHT"](
            game_api=self.game.api,
            input_controller=self.input_controller,
            bosses=[
                Bosses.MONSTRO
            ]
        )

        self.game_inputs = [
            {
                "name": "CONTROLS",
                "control_type": InputControlTypes.DISCRETE,
                "inputs": self.game.api.combine_game_inputs(["MOVEMENT", "SHOOTING"])
            }
        ]

        self.agent = RandomAgent(
            "AIsaac",
            game_inputs=self.game_inputs,
            callbacks=dict(
                after_observe=self.after_agent_observe
            )
        )

        # self.agent = RecorderAgent(
        #     "AIsaac",
        #     game_inputs=self.game_inputs,
        #     callbacks=dict(
        #         after_observe=self.after_agent_observe
        #     ),
        #     window_geometry=self.game.window_geometry
        # )

        # self.agent = RainbowDQNAgent(
        #     "AIsaac",
        #     game_inputs=self.game_inputs,
        #     callbacks=dict(
        #         after_observe=self.after_agent_observe,
        #         before_update=self.before_agent_update,
        #         after_update=self.after_agent_update
        #     ),
        #     evaluate_every=100,
        #     evaluate_for=10,
        #     rainbow_kwargs=dict(
        #         replay_memory_capacity=200000,
        #         observe_steps=50000,
        #         hidden_size=1024
        #     )
        # )

        self.started_at = datetime.utcnow().isoformat()

        self.analytics_client.track(event_key="GAME_NAME", data={"name": "The Binding of Isaac: Afterbirth+"})

        self.environment.new_episode(maximum_steps=960)

    def handle_play(self, game_frame, game_frame_pipeline):
        valid_game_state = self.environment.update_game_state(game_frame)

        if not valid_game_state:
            return None

        reward = self.reward_aisaac(self.environment.game_state, game_frame)

        terminal = (
            not self.environment.game_state["isaac_alive"] or
            self.environment.game_state["boss_dead"] or
            self.environment.episode_over
        )

        self.agent.observe(reward=reward, terminal=terminal)

        if not terminal:
            frame_buffer = FrameGrabber.get_frames([0, 2, 4, 6], frame_type="PIPELINE")
            agent_actions = self.agent.generate_actions(frame_buffer)

            #self.environment.perform_input(agent_actions)
        else:
            self.environment.clear_input()

            self.agent.reset()

            self.environment.end_episode()
            self.environment.new_episode(maximum_steps=960, reset=self.agent.mode.name != "TRAIN")

    def reward_aisaac(self, game_state, game_frame):
        if game_state["isaac_alive"]:
            if game_state["damage_taken"]:
                damage_taken = game_state["isaac_hps"][1] - game_state["isaac_hps"][0]
                return -(damage_taken * 0.5)
            elif game_state["boss_dead"]:
                return 1

            multiplier = 0.8 + (0.2 - (0.2 * (game_state["boss_hp"] / game_state["boss_hp_total"])))

            reward_damage_dealt = math.exp(-game_state["steps_since_damage_dealt"] / 3.0)
            reward_damage_taken = math.exp(game_state["steps_since_damage_taken"] / 16.0)

            return ((reward_damage_dealt * (reward_damage_taken - 1.0)) / (reward_damage_taken + 1)) * multiplier
        else:
            return -1

    # Callbacks

    def after_agent_observe(self):
        self.environment.episode_step()

    def before_agent_update(self):
        self.input_controller.tap_key(KeyboardKey.KEY_ESCAPE)

    def after_agent_update(self):
        self.input_controller.tap_key(KeyboardKey.KEY_ESCAPE)
        time.sleep(1)
