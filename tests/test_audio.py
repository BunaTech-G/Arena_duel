import importlib
import unittest
from unittest import mock


audio_module = importlib.import_module("game.audio")


class AudioRoutingTests(unittest.TestCase):
    def test_play_pickup_uses_default_sound_without_combo(self):
        with (
            mock.patch.object(
                audio_module, "_get_role_sound", return_value="pickup-snd"
            ) as get_sound,
            mock.patch.object(
                audio_module, "_role_maxtime", return_value=120
            ) as role_maxtime,
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_pickup()

        get_sound.assert_called_once_with("pickup")
        role_maxtime.assert_called_once_with("pickup")
        safe_play.assert_called_once_with("pickup-snd", "pickup", 120)

    def test_play_pickup_uses_combo_sound_when_bonus_is_active(self):
        def _get_sound(role_name):
            return {
                "select": "combo-snd",
                "pickup": "pickup-snd",
            }.get(role_name)

        def _get_maxtime(role_name):
            return {
                "select": 420,
                "pickup": 120,
            }.get(role_name)

        with (
            mock.patch.object(audio_module, "_get_role_sound", side_effect=_get_sound),
            mock.patch.object(audio_module, "_role_maxtime", side_effect=_get_maxtime),
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_pickup(combo_bonus=2)

        safe_play.assert_called_once_with("combo-snd", "pickup_combo", 420)

    def test_play_pickup_uses_rare_route_when_variant_is_rare(self):
        def _get_sound(role_name):
            return {
                "transition": "rare-snd",
                "bonus_spawn": "spawn-snd",
                "pickup": "pickup-snd",
            }.get(role_name)

        def _get_maxtime(role_name):
            return {
                "transition": 650,
                "bonus_spawn": 900,
                "pickup": 120,
            }.get(role_name)

        with (
            mock.patch.object(audio_module, "_get_role_sound", side_effect=_get_sound),
            mock.patch.object(audio_module, "_role_maxtime", side_effect=_get_maxtime),
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_pickup(combo_bonus=2, variant="rare")

        safe_play.assert_called_once_with("rare-snd", "pickup_rare", 650)

    def test_play_trap_prefers_kind_specific_role_when_available(self):
        def _get_sound(role_name):
            return {
                "trap_a": "spike-snd",
                "trap_b": "ember-snd",
            }.get(role_name)

        with (
            mock.patch.object(audio_module, "_get_role_sound", side_effect=_get_sound),
            mock.patch.object(audio_module, "_role_maxtime", return_value=700),
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_trap(trap_kind="ember_trap")

        safe_play.assert_called_once_with("ember-snd", "trap_b", 700)

    def test_play_trap_prefers_rune_specific_alert_route_before_fallback(self):
        def _get_sound(role_name):
            return {
                "alert": "rune-snd",
                "trap_b": "ember-snd",
                "trap_a": "spike-snd",
            }.get(role_name)

        def _get_maxtime(role_name):
            return {
                "alert": 700,
                "trap_b": 700,
                "trap_a": 700,
            }.get(role_name)

        with (
            mock.patch.object(audio_module, "_get_role_sound", side_effect=_get_sound),
            mock.patch.object(audio_module, "_role_maxtime", side_effect=_get_maxtime),
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_trap(trap_kind="rune_trap")

        safe_play.assert_called_once_with("rune-snd", "alert", 700)

    def test_play_trap_falls_back_to_trap_b_when_rune_alert_is_missing(self):
        def _get_sound(role_name):
            return {
                "alert": None,
                "trap_b": "ember-snd",
                "trap_a": "spike-snd",
            }.get(role_name)

        with (
            mock.patch.object(audio_module, "_get_role_sound", side_effect=_get_sound),
            mock.patch.object(audio_module, "_role_maxtime", return_value=700),
            mock.patch.object(audio_module, "_safe_play") as safe_play,
        ):
            audio_module.play_trap(trap_kind="rune_trap")

        safe_play.assert_called_once_with("ember-snd", "trap_b", 700)


if __name__ == "__main__":
    unittest.main()
