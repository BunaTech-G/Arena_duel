import os
import socket
import sys
import tempfile
import time
import types
import unittest
import importlib
from unittest.mock import patch


TEST_APPDATA_DIR = tempfile.mkdtemp(prefix="arena_duel_lan_tests_")
os.environ.setdefault("APPDATA", TEST_APPDATA_DIR)

if "mariadb" not in sys.modules:
    sys.modules["mariadb"] = types.SimpleNamespace(
        Error=Exception,
        connect=lambda **_kwargs: None,
    )


NetworkClient = importlib.import_module("network.client").NetworkClient
ASSIGN_SLOT = importlib.import_module("network.messages").ASSIGN_SLOT
START = importlib.import_module("network.messages").START
get_lan_address_info = importlib.import_module("network.net_utils").get_lan_address_info
parse_server_invitation = importlib.import_module(
    "network.net_utils"
).parse_server_invitation
start_server_in_background = importlib.import_module(
    "network.server"
).start_server_in_background
GameState = importlib.import_module("network.server").GameState
ORB_RARE_SCORE_VALUE = importlib.import_module("game.settings").ORB_RARE_SCORE_VALUE
TRAP_SLOW_DURATION_MS = importlib.import_module("game.settings").TRAP_SLOW_DURATION_MS


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LanNetworkingTests(unittest.TestCase):
    def setUp(self):
        self.servers = []
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            try:
                client.close()
            except OSError:
                pass

        for server in self.servers:
            try:
                server.shutdown()
            except OSError:
                pass
            try:
                server.server_close()
            except OSError:
                pass

    def test_parse_server_invitation_supports_explicit_port(self):
        host, port = parse_server_invitation("192.168.1.25:5400", 5000)

        self.assertEqual(host, "192.168.1.25")
        self.assertEqual(port, 5400)

    def test_parse_server_invitation_rejects_invalid_ip(self):
        with self.assertRaises(ValueError):
            parse_server_invitation("999.999.1.5:5000", 5000)

    def test_get_lan_address_info_prefers_private_ipv4(self):
        with patch(
            "network.net_utils._collect_candidate_ipv4_addresses",
            return_value=["8.8.8.8", "192.168.1.44", "10.0.0.8"],
        ):
            info = get_lan_address_info()

        self.assertEqual(info.primary_ip, "10.0.0.8")
        self.assertEqual(info.candidate_ips[0], "10.0.0.8")

    def test_client_reports_clear_error_when_host_is_absent(self):
        client = NetworkClient()
        self.clients.append(client)
        port = _reserve_free_port()

        with self.assertRaises(ConnectionError) as context:
            client.connect(
                "127.0.0.1",
                port,
                "Spectateur",
                timeout_seconds=0.5,
            )

        self.assertIn("Aucun hall n'ecoute", str(context.exception))

    def test_start_server_reports_port_occupied(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen(1)
            occupied_port = blocker.getsockname()[1]

            with self.assertRaises(RuntimeError) as context:
                start_server_in_background("127.0.0.1", occupied_port)

        self.assertIn("port est deja occupe", str(context.exception))

    def test_same_pc_host_client_connection_and_restart(self):
        port = _reserve_free_port()
        server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(server)

        client = NetworkClient()
        self.clients.append(client)
        client.connect(
            "127.0.0.1",
            port,
            "Gardien",
            is_host=True,
            timeout_seconds=1,
        )

        deadline = time.time() + 2
        received_assign_slot = False
        while time.time() < deadline and not received_assign_slot:
            for message in client.poll_messages():
                if message.get("type") == ASSIGN_SLOT:
                    received_assign_slot = True
                    break
            if not received_assign_slot:
                time.sleep(0.05)

        self.assertTrue(received_assign_slot)

        client.close()
        self.clients.remove(client)
        server.shutdown()
        server.server_close()
        self.servers.remove(server)

        restarted_server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(restarted_server)

    def test_two_ready_players_receive_start(self):
        port = _reserve_free_port()
        server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(server)

        host_client = NetworkClient()
        guest_client = NetworkClient()
        self.clients.extend([host_client, guest_client])

        host_client.connect(
            "127.0.0.1",
            port,
            "Gardien",
            is_host=True,
            timeout_seconds=1,
        )
        guest_client.connect(
            "127.0.0.1",
            port,
            "Invite",
            timeout_seconds=1,
        )

        deadline = time.time() + 2
        assigned_slots = set()
        while time.time() < deadline and len(assigned_slots) < 2:
            messages = host_client.poll_messages() + guest_client.poll_messages()
            for message in messages:
                if message.get("type") == ASSIGN_SLOT:
                    assigned_slots.add(message.get("client_id"))
            if len(assigned_slots) < 2:
                time.sleep(0.05)

        self.assertEqual(len(assigned_slots), 2)

        host_client.send_ready(True)
        guest_client.send_ready(True)

        deadline = time.time() + 3
        start_seen = False
        while time.time() < deadline and not start_seen:
            messages = host_client.poll_messages() + guest_client.poll_messages()
            for message in messages:
                if message.get("type") == START:
                    start_seen = True
                    break
            if not start_seen:
                time.sleep(0.05)

        self.assertTrue(start_seen)

        with server.game_lock:
            server.match_running = False
            server.game_state = None

    def test_client_connect_transmits_selected_sprite_to_lobby(self):
        port = _reserve_free_port()
        server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(server)

        client = NetworkClient()
        self.clients.append(client)
        client.connect(
            "127.0.0.1",
            port,
            "Gardien",
            is_host=True,
            timeout_seconds=1,
            sprite_id="skeleton_fighter_aether",
        )

        deadline = time.time() + 2
        received_assign_slot = False
        while time.time() < deadline and not received_assign_slot:
            for message in client.poll_messages():
                if message.get("type") == ASSIGN_SLOT:
                    received_assign_slot = True
                    break
            if not received_assign_slot:
                time.sleep(0.05)

        self.assertTrue(received_assign_slot)
        public_players = server.lobby.export_public_state()
        self.assertEqual(
            public_players[0]["sprite_id"],
            "skeleton_fighter_aether",
        )

    def test_game_state_exports_rare_orb_value_and_variant(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.random_free_point", return_value=(128, 144)):
            with patch("network.server.random.random", return_value=0.0):
                game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        exported_state = game_state.export_state()

        self.assertEqual(exported_state["orbs"][0]["variant"], "rare")
        self.assertEqual(
            exported_state["orbs"][0]["value"],
            ORB_RARE_SCORE_VALUE,
        )

    def test_game_state_respawn_preserves_orb_id_and_increments_serial(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        spawn_points = [(128, 144), (216, 244)]
        with patch("network.server.ORB_COUNT", 1):
            with patch("network.server.random_free_point", side_effect=spawn_points):
                with patch("network.server.random.random", side_effect=[0.5, 0.0]):
                    game_state = GameState(lobby_snapshot, match_duration_seconds=60)
                    first_orb = game_state.orbs[0]
                    game_state.players["host"]["x"] = first_orb["x"]
                    game_state.players["host"]["y"] = first_orb["y"]
                    original_orb_id = first_orb["orb_id"]
                    original_serial = first_orb["spawn_serial"]
                    game_state._handle_orbs()

        self.assertEqual(game_state.orbs[0]["orb_id"], original_orb_id)
        self.assertEqual(game_state.orbs[0]["spawn_serial"], original_serial + 1)
        self.assertEqual(game_state.orbs[0]["variant"], "rare")
        self.assertEqual(game_state.orbs[0]["value"], ORB_RARE_SCORE_VALUE)

    def test_game_state_exports_active_combo_state(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.ORB_COUNT", 1):
            with patch("network.server.random_free_point", return_value=(128, 144)):
                with patch("network.server.random.random", return_value=0.5):
                    game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        with patch("network.server.time.monotonic", return_value=1.0):
            awarded_value, combo_bonus = game_state._register_orb_pickup(
                game_state.players["host"],
                1,
            )
        with patch("network.server.time.monotonic", return_value=1.4):
            exported_state = game_state.export_state()

        self.assertEqual((awarded_value, combo_bonus), (1, 0))
        self.assertEqual(exported_state["players"][0]["combo_count"], 1)
        self.assertGreater(exported_state["players"][0]["combo_remaining_ms"], 0)

    def test_game_state_exports_last_pickup_payload(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.ORB_COUNT", 1):
            with patch(
                "network.server.random_free_point", side_effect=[(128, 144), (220, 240)]
            ):
                with patch("network.server.random.random", side_effect=[0.5, 0.5]):
                    game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        game_state.players["host"]["x"] = 128
        game_state.players["host"]["y"] = 144

        with patch("network.server.time.monotonic", return_value=1.0):
            game_state._handle_orbs()
        with patch("network.server.time.monotonic", return_value=1.2):
            exported_state = game_state.export_state()

        last_pickup = exported_state["players"][0]["last_pickup"]
        self.assertEqual(exported_state["players"][0]["last_pickup_serial"], 1)
        self.assertEqual(last_pickup["x"], 128.0)
        self.assertEqual(last_pickup["y"], 144.0)
        self.assertEqual(last_pickup["value"], 1)
        self.assertEqual(last_pickup["combo_count"], 1)
        self.assertEqual(last_pickup["combo_bonus"], 0)

    def test_game_state_trap_breaks_combo_and_applies_slow(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.ORB_COUNT", 0):
            game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        trap_rect = game_state.layout.traps[0].rect
        game_state.traps[0].active = True
        game_state.traps[0].slow_duration_ms = TRAP_SLOW_DURATION_MS
        game_state.traps[0].slow_multiplier = 0.5
        player = game_state.players["host"]
        player["x"] = trap_rect[0] + trap_rect[2] / 2
        player["y"] = trap_rect[1] + trap_rect[3] / 2
        player["combo_count"] = 3
        player["combo_expires_at_ms"] = 5000.0

        game_state._handle_traps(1000.0)
        first_slow_until = player["trap_slowed_until_ms"]
        exported_state = game_state.export_state()
        game_state._handle_traps(1100.0)

        self.assertEqual(player["combo_count"], 0)
        self.assertEqual(player["combo_expires_at_ms"], 0.0)
        self.assertEqual(first_slow_until, 1000.0 + TRAP_SLOW_DURATION_MS)
        self.assertEqual(player["trap_slowed_until_ms"], first_slow_until)
        self.assertEqual(exported_state["players"][0]["last_trap_serial"], 1)
        self.assertEqual(
            exported_state["players"][0]["last_trap_kind"],
            game_state.traps[0].kind,
        )

    def test_game_state_exports_dynamic_traps(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.ORB_COUNT", 0):
            game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        game_state.update(6.0, lobby_snapshot)
        exported_state = game_state.export_state()

        self.assertTrue(exported_state["traps"])
        self.assertGreaterEqual(
            len({trap["kind"] for trap in exported_state["traps"]}), 3
        )
        self.assertTrue(all("presence" in trap for trap in exported_state["traps"]))

    def test_game_state_exports_sprite_direction_and_end_payload(self):
        lobby_snapshot = {
            "guest": {
                "slot": 2,
                "name": "Invite",
                "team": "B",
                "ready": True,
                "input": {
                    "up": True,
                    "down": False,
                    "left": False,
                    "right": False,
                },
                "sprite_id": "skeleton_fighter_ember",
            }
        }

        with patch("network.server.ORB_COUNT", 0):
            game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        game_state.update(0.1, lobby_snapshot)
        exported_player = game_state.export_state()["players"][0]
        end_message = game_state.build_end_message()
        end_player = end_message["players"][0]

        self.assertEqual(
            exported_player["sprite_id"],
            "skeleton_fighter_ember",
        )
        self.assertEqual(exported_player["direction"], "up")
        self.assertTrue(exported_player["is_moving"])
        self.assertEqual(end_player["sprite_id"], "skeleton_fighter_ember")
        self.assertEqual(
            end_message["summary_metric_label"],
            "Points d'équipe",
        )
        self.assertEqual(
            end_message["team_panel_value_label"],
            "Points",
        )


if __name__ == "__main__":
    unittest.main()
