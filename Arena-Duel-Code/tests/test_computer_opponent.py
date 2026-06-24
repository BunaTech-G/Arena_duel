import importlib
import os
import unittest

import pygame


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


computer_opponent = importlib.import_module("game.computer_opponent")
BotController = computer_opponent.BotController


class _DummyPlayer:
    def __init__(self, x: float, y: float, team_code: str = "A"):
        self.x = float(x)
        self.y = float(y)
        self.team_code = team_code
        self.speed = 5
        self.radius = 20

    def get_rect(self, x=None, y=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        return pygame.Rect(
            int(px - self.radius),
            int(py - self.radius),
            self.radius * 2,
            self.radius * 2,
        )


class _DummyOrb:
    def __init__(self, x: float, y: float, value: int = 1):
        self.x = float(x)
        self.y = float(y)
        self.value = value


class BotDifficultyTests(unittest.TestCase):
    def test_difficulty_changes_reaction_speed(self):
        cadet = BotController(difficulty="cadet", seed=1)
        standard = BotController(difficulty="standard", seed=1)
        champion = BotController(difficulty="champion", seed=1)
        cadet_player = _DummyPlayer(0, 0)
        standard_player = _DummyPlayer(0, 0)
        champion_player = _DummyPlayer(0, 0)
        orb = _DummyOrb(100, 0)

        self.assertTrue(
            cadet.get_movement_intent(
                player=cadet_player,
                players=[cadet_player],
                orbs=[orb],
                obstacles=(),
                elapsed_ms=0,
            ).right
        )
        self.assertTrue(
            standard.get_movement_intent(
                player=standard_player,
                players=[standard_player],
                orbs=[orb],
                obstacles=(),
                elapsed_ms=0,
            ).right
        )
        self.assertTrue(
            champion.get_movement_intent(
                player=champion_player,
                players=[champion_player],
                orbs=[orb],
                obstacles=(),
                elapsed_ms=0,
            ).right
        )

        cadet_player.x = 110
        standard_player.x = 110
        champion_player.x = 110

        cadet_early = cadet.get_movement_intent(
            player=cadet_player,
            players=[cadet_player],
            orbs=[orb],
            obstacles=(),
            elapsed_ms=60,
        )
        standard_early = standard.get_movement_intent(
            player=standard_player,
            players=[standard_player],
            orbs=[orb],
            obstacles=(),
            elapsed_ms=60,
        )
        champion_early = champion.get_movement_intent(
            player=champion_player,
            players=[champion_player],
            orbs=[orb],
            obstacles=(),
            elapsed_ms=60,
        )
        standard_late = standard.get_movement_intent(
            player=standard_player,
            players=[standard_player],
            orbs=[orb],
            obstacles=(),
            elapsed_ms=120,
        )

        self.assertTrue(cadet_early.right)
        self.assertFalse(cadet_early.left)
        self.assertTrue(standard_early.right)
        self.assertFalse(standard_early.left)
        self.assertTrue(champion_early.left)
        self.assertFalse(champion_early.right)
        self.assertTrue(standard_late.left)
        self.assertFalse(standard_late.right)

    def test_difficulty_changes_target_priority(self):
        cadet = BotController(difficulty="cadet", seed=1)
        standard = BotController(difficulty="standard", seed=1)
        champion = BotController(difficulty="champion", seed=1)
        player = _DummyPlayer(0, 0)
        common_orb = _DummyOrb(60, 0, value=1)
        rare_orb = _DummyOrb(105, 0, value=3)
        orbs = [common_orb, rare_orb]

        cadet.get_movement_intent(
            player=player,
            players=[player],
            orbs=orbs,
            obstacles=(),
            elapsed_ms=0,
        )
        standard.get_movement_intent(
            player=player,
            players=[player],
            orbs=orbs,
            obstacles=(),
            elapsed_ms=0,
        )
        champion.get_movement_intent(
            player=player,
            players=[player],
            orbs=orbs,
            obstacles=(),
            elapsed_ms=0,
        )

        self.assertIs(cadet.target_orb, common_orb)
        self.assertIs(standard.target_orb, rare_orb)
        self.assertIs(champion.target_orb, rare_orb)

    def test_obstacle_avoidance_prefers_shorter_detour_when_gap_is_clearer(self):
        controller = BotController(difficulty="standard", seed=1)
        player = _DummyPlayer(60, 120)
        orb = _DummyOrb(140, 80)
        obstacle = pygame.Rect(90, 40, 60, 60)

        controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=0,
        )
        player.x = 65
        controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=100,
        )
        player.x = 70

        intent = controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=200,
        )

        self.assertTrue(intent.down)
        self.assertFalse(intent.up)
        self.assertEqual(controller.avoidance_axis, "vertical")
        self.assertEqual(controller.avoidance_direction, 1)

    def test_obstacle_avoidance_also_prefers_shorter_horizontal_detour(self):
        controller = BotController(difficulty="standard", seed=1)
        player = _DummyPlayer(120, 60)
        orb = _DummyOrb(160, 140)
        obstacle = pygame.Rect(100, 90, 60, 60)

        controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=0,
        )
        player.y = 65
        controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=100,
        )
        player.y = 70

        intent = controller.get_movement_intent(
            player=player,
            players=[player],
            orbs=[orb],
            obstacles=(obstacle,),
            elapsed_ms=200,
        )

        self.assertTrue(intent.left)
        self.assertFalse(intent.right)
        self.assertEqual(controller.avoidance_axis, "horizontal")
        self.assertEqual(controller.avoidance_direction, -1)


if __name__ == "__main__":
    unittest.main()
