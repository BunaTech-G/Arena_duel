import importlib
import os
import unittest
from types import SimpleNamespace
from unittest import mock


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


game_window = importlib.import_module("game.game_window")
control_models = importlib.import_module("game.control_models")
HUMAN_CONTROL_MODE = control_models.HUMAN_CONTROL_MODE
AI_CONTROL_MODE = control_models.AI_CONTROL_MODE
build_local_pickup_feedback = getattr(game_window, "_build_local_pickup_feedback")
build_local_trap_feedback = getattr(game_window, "_build_local_trap_feedback")
handle_local_orb_pickup = getattr(game_window, "_handle_local_orb_pickup")
handle_local_trap_trigger = getattr(game_window, "_handle_local_trap_trigger")
select_local_event_banner = getattr(game_window, "_select_local_event_banner")


class LocalFeedbackHelpersTests(unittest.TestCase):
    def test_build_local_pickup_feedback_returns_banner_for_human_player(self):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            combo_count=2,
            control_mode=HUMAN_CONTROL_MODE,
        )
        orb = SimpleNamespace(variant="rare")

        feedback = build_local_pickup_feedback(
            player,
            awarded_value=3,
            combo_bonus=1,
            orb=orb,
            elapsed_ms=1000,
        )

        self.assertIsNotNone(feedback)
        self.assertEqual(
            feedback["message"],
            "Braise · Alpha capte orbe rare +3 · combo x2 (+1)",
        )
        self.assertEqual(feedback["accent_color"], (242, 209, 118))
        self.assertEqual(feedback["until_ms"], 2650)
        self.assertEqual(feedback["priority"], 4)
        self.assertEqual(
            feedback["audio"],
            {"combo_bonus": 1, "variant": "rare"},
        )

    def test_build_local_pickup_feedback_is_silent_for_ai_player(self):
        player = SimpleNamespace(
            name="Bot",
            team_code="B",
            color=(100, 186, 255),
            combo_count=1,
            control_mode=AI_CONTROL_MODE,
        )
        orb = SimpleNamespace(variant="common")

        feedback = build_local_pickup_feedback(
            player,
            awarded_value=1,
            combo_bonus=0,
            orb=orb,
            elapsed_ms=1000,
        )

        self.assertIsNone(feedback)

    def test_build_local_trap_feedback_is_silent_for_ai_player(self):
        player = SimpleNamespace(
            name="Bot",
            team_code="B",
            color=(100, 186, 255),
            control_mode=AI_CONTROL_MODE,
        )
        trap_state = SimpleNamespace(kind="ember_trap")

        feedback = build_local_trap_feedback(
            player,
            trap_state,
            elapsed_ms=500,
        )

        self.assertIsNone(feedback)

    def test_build_local_trap_feedback_returns_banner_for_human_player(self):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            control_mode=HUMAN_CONTROL_MODE,
        )
        trap_state = SimpleNamespace(kind="spike_trap")

        feedback = build_local_trap_feedback(
            player,
            trap_state,
            elapsed_ms=500,
        )

        self.assertIsNotNone(feedback)
        self.assertEqual(
            feedback["message"],
            "Braise · Alpha heurte les pointes",
        )
        self.assertEqual(feedback["accent_color"], (242, 209, 118))
        self.assertEqual(feedback["until_ms"], 2150)
        self.assertEqual(feedback["priority"], 2)
        self.assertEqual(feedback["audio"], {"trap_kind": "spike_trap"})

    def test_select_local_event_banner_keeps_higher_priority_current_banner(self):
        current_banner = {
            "message": "Braise · Alpha capte orbe rare +3 · combo x2 (+1)",
            "accent_color": (242, 209, 118),
            "until_ms": 2650,
            "priority": 4,
        }
        next_banner = {
            "message": "Braise · Alpha heurte les pointes",
            "accent_color": (242, 209, 118),
            "until_ms": 2650,
            "priority": 2,
        }

        selected_banner = select_local_event_banner(current_banner, next_banner)

        self.assertIs(selected_banner, current_banner)

    def test_select_local_event_banner_replaces_with_higher_priority_next_banner(self):
        current_banner = {
            "message": "Braise · Alpha heurte les pointes",
            "accent_color": (242, 209, 118),
            "until_ms": 2150,
            "priority": 2,
        }
        next_banner = {
            "message": "Braise · Alpha capte orbe +3 · combo x2 (+1)",
            "accent_color": (242, 209, 118),
            "until_ms": 2650,
            "priority": 3,
        }

        selected_banner = select_local_event_banner(current_banner, next_banner)

        self.assertIs(selected_banner, next_banner)

    def test_handle_local_orb_pickup_foregrounds_human_and_keeps_spawn_bonus(self):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            combo_count=2,
            control_mode=HUMAN_CONTROL_MODE,
        )

        def _register_orb_pickup(_elapsed_ms, _value):
            player.combo_count = 2
            return 3, 1

        player.register_orb_pickup = _register_orb_pickup

        orb = SimpleNamespace(
            x=120.0,
            y=144.0,
            value=2,
            variant="common",
        )

        def _respawn(_arena_rect, _obstacles):
            orb.variant = "rare"

        orb.respawn = _respawn
        orb_effects = []

        with (
            mock.patch.object(game_window, "play_pickup") as play_pickup,
            mock.patch.object(
                game_window,
                "play_bonus_spawn",
            ) as play_bonus_spawn,
        ):
            feedback = handle_local_orb_pickup(
                player,
                orb,
                arena_rect=object(),
                obstacles=["rock"],
                elapsed_ms=1000,
                orb_effects=orb_effects,
            )

        self.assertEqual(
            feedback,
            {
                "message": "Braise · Alpha capte orbe +3 · combo x2 (+1)",
                "accent_color": (242, 209, 118),
                "until_ms": 2650,
                "priority": 3,
            },
        )
        self.assertEqual(
            orb_effects,
            [
                {
                    "x": 120.0,
                    "y": 144.0,
                    "value": 3,
                    "variant": "common",
                    "combo_count": 2,
                    "combo_bonus": 1,
                    "started_at_ms": 1000,
                }
            ],
        )
        play_pickup.assert_called_once_with(combo_bonus=1, variant="common")
        play_bonus_spawn.assert_called_once_with()
        self.assertEqual(orb.variant, "rare")

    def test_handle_local_orb_pickup_keeps_ai_silent_but_preserves_world_effects(self):
        player = SimpleNamespace(
            name="Bot",
            team_code="B",
            color=(100, 186, 255),
            combo_count=1,
            control_mode=AI_CONTROL_MODE,
        )

        def _register_orb_pickup(_elapsed_ms, _value):
            player.combo_count = 1
            return 1, 0

        player.register_orb_pickup = _register_orb_pickup

        orb = SimpleNamespace(
            x=88.0,
            y=96.0,
            value=1,
            variant="common",
        )

        def _respawn(_arena_rect, _obstacles):
            orb.variant = "rare"

        orb.respawn = _respawn
        orb_effects = []

        with (
            mock.patch.object(game_window, "play_pickup") as play_pickup,
            mock.patch.object(
                game_window,
                "play_bonus_spawn",
            ) as play_bonus_spawn,
        ):
            feedback = handle_local_orb_pickup(
                player,
                orb,
                arena_rect=object(),
                obstacles=["rock"],
                elapsed_ms=1000,
                orb_effects=orb_effects,
            )

        self.assertIsNone(feedback)
        self.assertEqual(len(orb_effects), 1)
        play_pickup.assert_not_called()
        play_bonus_spawn.assert_called_once_with()
        self.assertEqual(orb.variant, "rare")

    def test_handle_local_trap_trigger_plays_audio_for_human(self):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            control_mode=HUMAN_CONTROL_MODE,
        )
        player.trigger_trap = lambda *_args, **_kwargs: True
        trap_state = SimpleNamespace(
            kind="spike_trap",
            slow_duration_ms=850,
            slow_multiplier=0.48,
        )

        with mock.patch.object(game_window, "play_trap") as play_trap:
            feedback = handle_local_trap_trigger(
                player,
                trap_state,
                elapsed_ms=500,
            )

        self.assertEqual(
            feedback,
            {
                "message": "Braise · Alpha heurte les pointes",
                "accent_color": (242, 209, 118),
                "until_ms": 2150,
                "priority": 2,
            },
        )
        play_trap.assert_called_once_with(trap_kind="spike_trap")

    def test_handle_local_trap_trigger_ignores_repeated_slow_window(self):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            control_mode=HUMAN_CONTROL_MODE,
        )
        player.trigger_trap = lambda *_args, **_kwargs: False
        trap_state = SimpleNamespace(
            kind="spike_trap",
            slow_duration_ms=850,
            slow_multiplier=0.48,
        )

        with mock.patch.object(game_window, "play_trap") as play_trap:
            feedback = handle_local_trap_trigger(
                player,
                trap_state,
                elapsed_ms=500,
            )

        self.assertIsNone(feedback)
        play_trap.assert_not_called()

    def test_local_feedback_flow_keeps_pickup_banner_over_trap_and_preserves_effects(
        self,
    ):
        player = SimpleNamespace(
            name="Alpha",
            team_code="A",
            color=(242, 209, 118),
            combo_count=2,
            control_mode=HUMAN_CONTROL_MODE,
        )
        player.trigger_trap = lambda *_args, **_kwargs: True

        def _register_orb_pickup(_elapsed_ms, _value):
            player.combo_count = 2
            return 3, 1

        player.register_orb_pickup = _register_orb_pickup

        trap_state = SimpleNamespace(
            kind="spike_trap",
            slow_duration_ms=850,
            slow_multiplier=0.48,
        )
        orb = SimpleNamespace(
            x=120.0,
            y=144.0,
            value=2,
            variant="common",
        )

        def _respawn(_arena_rect, _obstacles):
            orb.variant = "rare"

        orb.respawn = _respawn
        orb_effects = []
        event_banner = None

        with (
            mock.patch.object(game_window, "play_trap") as play_trap,
            mock.patch.object(game_window, "play_pickup") as play_pickup,
            mock.patch.object(game_window, "play_bonus_spawn") as play_bonus_spawn,
        ):
            event_banner = select_local_event_banner(
                event_banner,
                handle_local_trap_trigger(
                    player,
                    trap_state,
                    elapsed_ms=1000,
                ),
            )
            event_banner = select_local_event_banner(
                event_banner,
                handle_local_orb_pickup(
                    player,
                    orb,
                    arena_rect=object(),
                    obstacles=["rock"],
                    elapsed_ms=1000,
                    orb_effects=orb_effects,
                ),
            )

        self.assertEqual(
            event_banner,
            {
                "message": "Braise · Alpha capte orbe +3 · combo x2 (+1)",
                "accent_color": (242, 209, 118),
                "until_ms": 2650,
                "priority": 3,
            },
        )
        self.assertEqual(
            orb_effects,
            [
                {
                    "x": 120.0,
                    "y": 144.0,
                    "value": 3,
                    "variant": "common",
                    "combo_count": 2,
                    "combo_bonus": 1,
                    "started_at_ms": 1000,
                }
            ],
        )
        play_trap.assert_called_once_with(trap_kind="spike_trap")
        play_pickup.assert_called_once_with(combo_bonus=1, variant="common")
        play_bonus_spawn.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
