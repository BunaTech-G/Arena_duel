import importlib
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

net_match_window = importlib.import_module("game.net_match_window")


class _NoKeys(dict):
    def __getitem__(self, key):
        return False


class _FakeSurface:
    def __init__(self, size):
        self._size = size
        self.blits = []
        self.fills = []

    def get_size(self):
        return self._size

    def fill(self, _color):
        self.fills.append(_color)
        return None

    def blit(self, _surface, _position):
        self.blits.append((_surface, _position))
        return None


class _FakeRenderedText:
    def __init__(self, text):
        self.text = text

    def get_width(self):
        return max(12, len(self.text) * 6)


class _RecordingFont:
    def __init__(self):
        self.render_calls = []

    def render(self, text, _antialias, _color):
        self.render_calls.append(text)
        return _FakeRenderedText(text)


class _FakeClient:
    def __init__(self, polls):
        self.running = True
        self._polls = list(polls)
        self.sent_inputs = []
        self.close_called = False

    def send_input(self, up, down, left, right):
        self.sent_inputs.append((up, down, left, right))

    def poll_messages(self):
        if not self._polls:
            self.running = False
            return []

        messages = list(self._polls.pop(0))
        if not self._polls:
            self.running = False
        return messages

    def close(self):
        self.close_called = True
        self.running = False


class RunNetworkMatchTests(unittest.TestCase):
    def _run_match(
        self,
        polls,
    ) -> tuple[dict, _FakeClient, dict[str, object]]:
        client = _FakeClient(polls)
        layout = SimpleNamespace(window_size=(640, 360))
        screen = _FakeSurface(layout.window_size)
        draw_state_snapshots = []

        def _fake_surface_factory(size, *_unused):
            return _FakeSurface(size)

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(net_match_window, "pg_init"))
            stack.enter_context(mock.patch.object(net_match_window, "init_audio"))
            stop_music = stack.enter_context(
                mock.patch.object(net_match_window, "stop_music")
            )
            play_win = stack.enter_context(
                mock.patch.object(net_match_window, "play_win")
            )
            play_lose = stack.enter_context(
                mock.patch.object(net_match_window, "play_lose")
            )
            play_draw = stack.enter_context(
                mock.patch.object(net_match_window, "play_draw")
            )
            play_pickup = stack.enter_context(
                mock.patch.object(net_match_window, "play_pickup")
            )
            play_bonus_spawn = stack.enter_context(
                mock.patch.object(net_match_window, "play_bonus_spawn")
            )
            play_trap = stack.enter_context(
                mock.patch.object(net_match_window, "play_trap")
            )
            stack.enter_context(mock.patch.object(net_match_window, "draw_background"))

            def _capture_draw_state(*args):
                draw_state_snapshots.append(
                    {
                        "state": dict(args[1]),
                        "movement_flags": dict(args[8]),
                        "facing_by_slot": dict(args[9]),
                        "orb_effects": [dict(effect) for effect in args[10]],
                    }
                )

            draw_state = stack.enter_context(
                mock.patch.object(
                    net_match_window,
                    "draw_state",
                    side_effect=_capture_draw_state,
                )
            )
            draw_end_overlay = stack.enter_context(
                mock.patch.object(net_match_window, "draw_end_overlay")
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window,
                    "load_font",
                    return_value=object(),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window,
                    "get_map_layout",
                    return_value=layout,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window,
                    "get_app_icon_png_path",
                    return_value="Z:/__arena_duel_missing_icon__.png",
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window,
                    "_tick_frame",
                    return_value=2000,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame.time,
                    "Clock",
                    return_value=mock.Mock(),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame.event,
                    "get",
                    return_value=[],
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame.key,
                    "get_pressed",
                    return_value=_NoKeys(),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame.display,
                    "set_mode",
                    return_value=screen,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame.display,
                    "set_caption",
                )
            )
            stack.enter_context(
                mock.patch.object(net_match_window.pygame.display, "flip")
            )
            stack.enter_context(
                mock.patch.object(net_match_window.pygame.display, "quit")
            )
            stack.enter_context(
                mock.patch.object(
                    net_match_window.pygame,
                    "Surface",
                    side_effect=_fake_surface_factory,
                )
            )

            result = net_match_window.run_network_match(
                client,
                1,
                "HostPlayer",
                "A",
            )

        handles = {
            "stop_music": stop_music,
            "play_win": play_win,
            "play_lose": play_lose,
            "play_draw": play_draw,
            "play_pickup": play_pickup,
            "play_bonus_spawn": play_bonus_spawn,
            "play_trap": play_trap,
            "draw_state": draw_state,
            "draw_state_snapshots": draw_state_snapshots,
            "draw_end_overlay": draw_end_overlay,
        }
        return result, client, handles

    def test_run_network_match_returns_completed_end_result(self):
        end_message = {
            "type": "END",
            "winner_team": "A",
            "winner_text": "Victoire équipe A",
            "team_a_score": 4,
            "team_b_score": 2,
            "players": [],
        }
        custom_message = {
            "type": "POST_MATCH_ROOM_UPDATE",
            "room_id": "room-1",
        }

        result, client, handles = self._run_match([[custom_message, end_message]])

        self.assertTrue(result["completed"])
        self.assertEqual(result["end_message"], end_message)
        self.assertEqual(result["deferred_messages"], [custom_message])
        self.assertIsNone(result["disconnect_message"])
        self.assertEqual(client.sent_inputs, [(False, False, False, False)])
        handles["play_win"].assert_called_once_with()
        self.assertEqual(
            handles["stop_music"].call_args_list[0].kwargs,
            {"fade_ms": 0},
        )
        self.assertEqual(
            handles["stop_music"].call_args_list[-1].kwargs,
            {"fade_ms": 120},
        )

    def test_run_network_match_uses_last_error_message_when_stream_stops(self):
        result, client, handles = self._run_match(
            [[{"type": "ERROR", "message": "Hall saturé"}]]
        )

        self.assertFalse(result["completed"])
        self.assertIsNone(result["end_message"])
        self.assertEqual(result["deferred_messages"], [])
        self.assertEqual(result["disconnect_message"], "Hall saturé")
        self.assertEqual(client.sent_inputs, [(False, False, False, False)])
        handles["play_win"].assert_not_called()

    def test_run_network_match_prefers_disconnect_message(self):
        result, client, handles = self._run_match(
            [
                [
                    {"type": "ERROR", "message": "Hall saturé"},
                    {
                        "type": "DISCONNECTED",
                        "message": "Le lien au hall s'est rompu.",
                    },
                ]
            ]
        )

        self.assertFalse(result["completed"])
        self.assertIsNone(result["end_message"])
        self.assertEqual(result["deferred_messages"], [])
        self.assertEqual(
            result["disconnect_message"],
            "Le lien au hall s'est rompu.",
        )
        self.assertFalse(client.close_called)
        handles["play_win"].assert_not_called()

    def test_run_network_match_tracks_state_audio_effects_and_direction(self):
        first_state = {
            "type": "STATE",
            "team_a_score": 1,
            "team_b_score": 0,
            "remaining_time": 42,
            "players": [
                {
                    "slot": 1,
                    "name": "HostPlayer",
                    "team": "A",
                    "score": 1,
                    "x": 10.0,
                    "y": 12.0,
                    "direction": "left",
                    "is_moving": True,
                    "last_pickup_serial": 1,
                    "last_trap_serial": 0,
                    "last_pickup": {
                        "value": 2,
                        "x": 10.0,
                        "y": 12.0,
                        "combo_count": 1,
                        "combo_bonus": 0,
                    },
                }
            ],
            "orbs": [
                {
                    "orb_id": 7,
                    "x": 100.0,
                    "y": 110.0,
                    "value": 1,
                    "variant": "common",
                    "spawn_serial": 1,
                }
            ],
        }
        second_state = {
            "type": "STATE",
            "team_a_score": 2,
            "team_b_score": 0,
            "remaining_time": 39,
            "players": [
                {
                    "slot": 1,
                    "name": "HostPlayer",
                    "team": "A",
                    "score": 2,
                    "x": 18.0,
                    "y": 12.0,
                    "direction": "right",
                    "is_moving": True,
                    "last_pickup_serial": 2,
                    "last_trap_serial": 1,
                    "last_pickup": {
                        "value": 3,
                        "x": 18.0,
                        "y": 12.0,
                        "combo_count": 2,
                        "combo_bonus": 1,
                    },
                }
            ],
            "orbs": [
                {
                    "orb_id": 7,
                    "x": 100.0,
                    "y": 110.0,
                    "value": 1,
                    "variant": "rare",
                    "spawn_serial": 2,
                }
            ],
        }
        end_message = {
            "type": "END",
            "winner_team": "A",
            "winner_text": "Victoire équipe A",
            "team_a_score": 2,
            "team_b_score": 0,
            "players": [],
        }

        result, client, handles = self._run_match(
            [[first_state], [second_state, end_message]]
        )

        self.assertTrue(result["completed"])
        self.assertEqual(
            client.sent_inputs,
            [(False, False, False, False)] * 2,
        )
        handles["play_pickup"].assert_called_once_with()
        handles["play_trap"].assert_called_once_with()
        handles["play_bonus_spawn"].assert_called_once_with()
        self.assertEqual(handles["draw_state"].call_count, 2)

        snapshots = handles["draw_state_snapshots"]
        self.assertEqual(len(snapshots), 2)
        first_snapshot = snapshots[0]
        second_snapshot = snapshots[1]
        self.assertEqual(first_snapshot["state"], first_state)
        self.assertEqual(second_snapshot["state"], second_state)
        self.assertEqual(first_snapshot["movement_flags"], {1: True})
        self.assertEqual(second_snapshot["movement_flags"], {1: True})
        self.assertEqual(first_snapshot["facing_by_slot"], {1: -1})
        self.assertEqual(second_snapshot["facing_by_slot"], {1: 1})
        self.assertEqual(len(first_snapshot["orb_effects"]), 1)
        self.assertEqual(len(second_snapshot["orb_effects"]), 2)
        self.assertEqual(second_snapshot["orb_effects"][-1]["combo_bonus"], 1)

    def test_draw_state_routes_hud_orbs_and_players(self):
        screen = _FakeSurface((640, 360))
        layout = SimpleNamespace(window_size=(640, 360))
        orb_effects = [
            {
                "x": 50.0,
                "y": 60.0,
                "value": 2,
                "started_at_ms": 1000,
                "combo_count": 2,
                "combo_bonus": 1,
            }
        ]
        state = {
            "team_a_score": 3,
            "team_b_score": 1,
            "remaining_time": 27,
            "traps": [{"x": 10, "y": 12}],
            "orbs": [
                {
                    "x": 120.0,
                    "y": 140.0,
                    "value": 3,
                    "variant": "rare",
                    "_local_spawned_at_ms": 900,
                }
            ],
            "players": [
                {
                    "slot": 1,
                    "name": "HostPlayer",
                    "team": "A",
                    "score": 5,
                    "x": 18.0,
                    "y": 24.0,
                    "direction": "left",
                    "sprite_id": "skeleton_fighter_ember",
                    "combo_count": 2,
                    "combo_remaining_ms": 400,
                },
                {
                    "slot": 2,
                    "name": "GuestPlayer",
                    "team": "B",
                    "score": 1,
                    "x": 40.0,
                    "y": 48.0,
                    "direction": "right",
                },
            ],
        }

        with (
            mock.patch.object(
                net_match_window.pygame.time,
                "get_ticks",
                return_value=1234,
            ),
            mock.patch.object(
                net_match_window,
                "get_arena_rect",
                return_value="arena-rect",
            ),
            mock.patch.object(
                net_match_window,
                "get_obstacles",
                return_value=["rock"],
            ),
            mock.patch.object(net_match_window, "draw_arena") as draw_arena,
            mock.patch.object(
                net_match_window,
                "draw_match_hud",
            ) as draw_match_hud,
            mock.patch.object(
                net_match_window,
                "draw_orb_visual",
            ) as draw_orb_visual,
            mock.patch.object(
                net_match_window,
                "draw_player_avatar",
            ) as draw_player_avatar,
            mock.patch.object(
                net_match_window,
                "draw_orb_collection_effect",
                side_effect=[False],
            ) as draw_orb_collection_effect,
            mock.patch.object(
                net_match_window,
                "get_team_color",
                side_effect=[
                    "ember-color",
                    "aether-color",
                    "ember-color",
                    "aether-color",
                ],
            ),
        ):
            net_match_window.draw_state(
                screen,
                state,
                1,
                font="body-font",
                big_font="big-font",
                _medium_font="medium-font",
                small_font="small-font",
                layout=layout,
                movement_flags={1: True, 2: False},
                facing_by_slot={1: -1, 2: 1},
                orb_effects=orb_effects,
            )

        draw_arena.assert_called_once_with(
            screen,
            "arena-rect",
            ["rock"],
            layout=layout,
            trap_states=state["traps"],
            elapsed_ms=1234,
        )
        draw_match_hud.assert_called_once()
        hud_kwargs = draw_match_hud.call_args.kwargs
        self.assertEqual(hud_kwargs["team_a_score"], 3)
        self.assertEqual(hud_kwargs["team_b_score"], 1)
        self.assertEqual(hud_kwargs["remaining_time"], 27)
        self.assertEqual(hud_kwargs["team_a_rows"][0]["name"], "HostPlayer")
        self.assertEqual(hud_kwargs["team_b_rows"][0]["name"], "GuestPlayer")
        self.assertEqual(
            hud_kwargs["team_b_rows"][0]["sprite_id"],
            "skeleton_fighter_aether",
        )
        draw_orb_visual.assert_called_once()
        self.assertEqual(draw_orb_visual.call_args.kwargs["variant"], "rare")
        self.assertEqual(
            draw_orb_visual.call_args.kwargs["spawned_at_ms"],
            900,
        )
        self.assertEqual(draw_player_avatar.call_count, 2)
        first_player_kwargs = draw_player_avatar.call_args_list[0].kwargs
        second_player_kwargs = draw_player_avatar.call_args_list[1].kwargs
        self.assertTrue(first_player_kwargs["highlight"])
        self.assertEqual(first_player_kwargs["facing"], -1)
        self.assertEqual(first_player_kwargs["direction_name"], "left")
        self.assertTrue(first_player_kwargs["moving"])
        self.assertFalse(second_player_kwargs["highlight"])
        self.assertEqual(second_player_kwargs["facing"], 1)
        self.assertEqual(second_player_kwargs["direction_name"], "right")
        self.assertFalse(second_player_kwargs["moving"])
        draw_orb_collection_effect.assert_called_once()
        self.assertEqual(orb_effects, [])

    def test_draw_end_overlay_renders_history_and_team_cards(self):
        screen = _FakeSurface((960, 540))
        big_font = _RecordingFont()
        medium_font = _RecordingFont()
        small_font = _RecordingFont()
        end_message = {
            "team_a_score": 4,
            "team_b_score": 2,
            "winner_team": "A",
            "winner_text": "Victoire équipe A",
            "history_saved": True,
            "match_id": 12,
            "players": [
                {
                    "slot": 1,
                    "name": "HostPlayer",
                    "team": "A",
                    "score": 4,
                    "sprite_id": "skeleton_fighter_ember",
                },
                {
                    "slot": 2,
                    "name": "GuestPlayer",
                    "team": "B",
                    "score": 2,
                },
            ],
        }

        with (
            mock.patch.object(
                net_match_window,
                "choose_text_candidate",
                return_value="4 - 2",
            ),
            mock.patch.object(
                net_match_window,
                "get_shared_player_score_slot_width",
                return_value=77,
            ),
            mock.patch.object(
                net_match_window,
                "draw_end_team_card",
            ) as draw_end_team_card,
            mock.patch.object(
                net_match_window.pygame,
                "Surface",
                return_value=_FakeSurface((960, 540)),
            ),
            mock.patch.object(net_match_window.pygame.draw, "rect"),
        ):
            net_match_window.draw_end_overlay(
                screen,
                end_message,
                big_font,
                medium_font,
                small_font,
            )

        self.assertIn("Victoire équipe A", big_font.render_calls)
        self.assertIn(
            "Chronique du hall scellée · joute #12",
            small_font.render_calls,
        )
        self.assertIn(
            "Retour au hall dans un instant...",
            small_font.render_calls,
        )
        self.assertEqual(draw_end_team_card.call_count, 2)
        first_card_kwargs = draw_end_team_card.call_args_list[0].kwargs
        second_card_kwargs = draw_end_team_card.call_args_list[1].kwargs
        self.assertEqual(first_card_kwargs["align"], "left")
        self.assertEqual(second_card_kwargs["align"], "right")
        self.assertEqual(first_card_kwargs["rows"][0]["name"], "HostPlayer")
        self.assertEqual(second_card_kwargs["rows"][0]["name"], "GuestPlayer")
        self.assertEqual(
            second_card_kwargs["rows"][0]["sprite_id"],
            "skeleton_fighter_aether",
        )
        self.assertEqual(first_card_kwargs["score_slot_width"], 77)
        self.assertEqual(second_card_kwargs["score_slot_width"], 77)


if __name__ == "__main__":
    unittest.main()
