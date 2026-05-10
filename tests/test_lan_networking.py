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
TELEMETRY_DATA = importlib.import_module("network.messages").TELEMETRY_DATA
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

    def test_history_request_returns_soft_error_when_history_lookup_fails(self):
        port = _reserve_free_port()
        with patch(
            "network.server.get_serializable_match_history",
            side_effect=RuntimeError("base hors ligne"),
        ):
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
            while time.time() < deadline:
                if any(
                    message.get("type") == ASSIGN_SLOT
                    for message in client.poll_messages()
                ):
                    break
                time.sleep(0.05)

            client.send_request_history()

            deadline = time.time() + 2
            history_error = None
            while time.time() < deadline and history_error is None:
                for message in client.poll_messages():
                    if message.get("type") == "HISTORY_DATA" and not message.get("ok"):
                        history_error = message
                        break
                if history_error is None:
                    time.sleep(0.05)

        self.assertIsNotNone(history_error)
        self.assertIn("base hors ligne", history_error.get("message", ""))

    def test_host_can_request_server_telemetry(self):
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
        while time.time() < deadline:
            if any(
                message.get("type") == ASSIGN_SLOT for message in client.poll_messages()
            ):
                break
            time.sleep(0.05)

        self.assertTrue(client.send_request_telemetry())

        deadline = time.time() + 2
        telemetry_payload = None
        while time.time() < deadline and telemetry_payload is None:
            for message in client.poll_messages():
                if message.get("type") == TELEMETRY_DATA and message.get("ok"):
                    telemetry_payload = message.get("telemetry", {})
                    break
            if telemetry_payload is None:
                time.sleep(0.05)

        self.assertIsNotNone(telemetry_payload)
        self.assertIn("uptime_seconds", telemetry_payload)
        self.assertIn("connected_clients", telemetry_payload)
        self.assertIn("messages_received", telemetry_payload)
        self.assertGreaterEqual(telemetry_payload["connected_clients"], 1)

    def test_non_host_cannot_request_server_telemetry(self):
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
        assigned_slots = 0
        while time.time() < deadline and assigned_slots < 2:
            messages = host_client.poll_messages() + guest_client.poll_messages()
            for message in messages:
                if message.get("type") == ASSIGN_SLOT:
                    assigned_slots += 1
            if assigned_slots < 2:
                time.sleep(0.05)

        self.assertGreaterEqual(assigned_slots, 2)
        self.assertTrue(guest_client.send_request_telemetry())

        deadline = time.time() + 2
        error_message = None
        received_telemetry = False
        while time.time() < deadline and error_message is None:
            for message in guest_client.poll_messages():
                if message.get("type") == "ERROR":
                    error_message = message.get("message", "")
                    break
                if message.get("type") == TELEMETRY_DATA:
                    received_telemetry = True
            if error_message is None:
                time.sleep(0.05)

        self.assertFalse(received_telemetry)
        self.assertIsNotNone(error_message)
        self.assertIn("gardien", error_message.lower())

    def test_spectator_connects_and_is_flagged_in_lobby(self):
        port = _reserve_free_port()
        server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(server)

        host_client = NetworkClient()
        spectator_client = NetworkClient()
        self.clients.extend([host_client, spectator_client])

        host_client.connect(
            "127.0.0.1",
            port,
            "Gardien",
            is_host=True,
            timeout_seconds=1,
        )
        spectator_client.connect(
            "127.0.0.1",
            port,
            "Observateur",
            spectator=True,
            timeout_seconds=1,
        )

        deadline = time.time() + 2
        spectator_assign = None
        while time.time() < deadline and spectator_assign is None:
            for message in spectator_client.poll_messages():
                if message.get("type") == ASSIGN_SLOT:
                    spectator_assign = message
                    break
            if spectator_assign is None:
                time.sleep(0.05)

        self.assertIsNotNone(spectator_assign)
        self.assertTrue(spectator_assign.get("spectator"))
        self.assertEqual(spectator_assign.get("team"), "S")
        self.assertIsNone(spectator_assign.get("slot"))

        public_players = server.lobby.export_public_state()
        spectator_row = next(
            (
                p
                for p in public_players
                if p.get("name") == "Observateur" and p.get("spectator")
            ),
            None,
        )
        self.assertIsNotNone(spectator_row)

    def test_spectator_cannot_set_ready(self):
        port = _reserve_free_port()
        server, _thread, _address_info = start_server_in_background(
            "127.0.0.1",
            port,
        )
        self.servers.append(server)

        host_client = NetworkClient()
        spectator_client = NetworkClient()
        self.clients.extend([host_client, spectator_client])

        host_client.connect(
            "127.0.0.1",
            port,
            "Gardien",
            is_host=True,
            timeout_seconds=1,
        )
        spectator_client.connect(
            "127.0.0.1",
            port,
            "Observateur",
            spectator=True,
            timeout_seconds=1,
        )

        deadline = time.time() + 2
        assigned_slots = 0
        while time.time() < deadline and assigned_slots < 2:
            messages = host_client.poll_messages() + spectator_client.poll_messages()
            for message in messages:
                if message.get("type") == ASSIGN_SLOT:
                    assigned_slots += 1
            if assigned_slots < 2:
                time.sleep(0.05)

        self.assertGreaterEqual(assigned_slots, 2)
        self.assertTrue(spectator_client.send_ready(True))

        deadline = time.time() + 2
        error_message = None
        while time.time() < deadline and error_message is None:
            for message in spectator_client.poll_messages():
                if message.get("type") == "ERROR":
                    error_message = message.get("message", "")
                    break
            if error_message is None:
                time.sleep(0.05)

        self.assertIsNotNone(error_message)
        self.assertIn("spectateur", error_message.lower())

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
        self.assertEqual(last_pickup["variant"], "common")
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

    def test_game_state_removes_players_missing_from_lobby_snapshot(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            },
            "guest": {
                "slot": 2,
                "name": "Invite",
                "team": "B",
                "ready": True,
                "input": {},
            },
        }

        game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        game_state.update(
            1.0 / 20.0,
            {
                "host": dict(lobby_snapshot["host"]),
            },
        )
        exported_state = game_state.export_state()
        end_message = game_state.build_end_message()

        self.assertEqual(list(game_state.players.keys()), ["host"])
        self.assertEqual(
            [player["client_id"] for player in exported_state["players"]],
            ["host"],
        )
        self.assertEqual(
            [player["name"] for player in end_message["players"]],
            ["Gardien"],
        )

    def test_game_state_uses_monotonic_clock_for_match_duration(self):
        lobby_snapshot = {
            "host": {
                "slot": 1,
                "name": "Gardien",
                "team": "A",
                "ready": True,
                "input": {},
            }
        }

        with patch("network.server.time.time", return_value=1000.0):
            with patch("network.server.time.monotonic", return_value=500.0):
                game_state = GameState(lobby_snapshot, match_duration_seconds=60)

        with patch("network.server.time.time", return_value=1300.0):
            with patch("network.server.time.monotonic", return_value=501.0):
                exported_state = game_state.export_state()
                is_finished = game_state.is_finished()

        self.assertEqual(exported_state["remaining_time"], 59)
        self.assertFalse(is_finished)
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


class ProtocolTests(unittest.TestCase):
    """Tests pour le protocole length-prefixed v1"""

    def setUp(self):
        self.encode_message = importlib.import_module("network.protocol").encode_message
        self.receive_message_binary = importlib.import_module(
            "network.protocol"
        ).receive_message_binary

    def test_encode_message_produces_4byte_header_plus_json(self):
        msg = {"type": "TEST", "value": 42}
        raw = self.encode_message(msg)

        import struct

        length = struct.unpack("!I", raw[:4])[0]

        self.assertEqual(length, len(raw) - 4)
        self.assertGreater(length, 0)

    def test_encode_decode_roundtrip(self):
        import io

        msg = {"type": "HELLO", "name": "Joueur_Test", "host": True}
        raw = self.encode_message(msg)

        rfile = io.BytesIO(raw)
        decoded = self.receive_message_binary(rfile)

        self.assertEqual(decoded["type"], "HELLO")
        self.assertEqual(decoded["name"], "Joueur_Test")
        self.assertTrue(decoded["host"])

    def test_encode_message_handles_french_accents(self):
        import io

        msg = {"type": "HELLO", "name": "Héros_Général_éèàü"}
        raw = self.encode_message(msg)

        rfile = io.BytesIO(raw)
        decoded = self.receive_message_binary(rfile)

        self.assertEqual(decoded["name"], "Héros_Général_éèàü")

    def test_encode_message_handles_embedded_newlines(self):
        import io

        msg = {"type": "TEST", "text": "ligne1\nligne2\nligne3"}
        raw = self.encode_message(msg)

        rfile = io.BytesIO(raw)
        decoded = self.receive_message_binary(rfile)

        self.assertEqual(decoded["text"], "ligne1\nligne2\nligne3")

    def test_receive_returns_none_on_empty_stream(self):
        import io

        rfile = io.BytesIO(b"")
        result = self.receive_message_binary(rfile)

        self.assertIsNone(result)

    def test_multiple_messages_in_sequence(self):
        import io

        messages = [
            {"type": "HELLO", "name": "A"},
            {"type": "READY", "ready": True},
            {"type": "INPUT", "up": True, "down": False, "left": False, "right": False},
        ]
        stream = b"".join(self.encode_message(m) for m in messages)
        rfile = io.BytesIO(stream)

        decoded = []
        for _ in range(3):
            msg = self.receive_message_binary(rfile)
            if msg:
                decoded.append(msg)

        self.assertEqual(len(decoded), 3)
        self.assertEqual(decoded[0]["type"], "HELLO")
        self.assertEqual(decoded[1]["type"], "READY")
        self.assertEqual(decoded[2]["type"], "INPUT")
        self.assertTrue(decoded[2]["up"])


class LobbyStateHeartbeatTests(unittest.TestCase):
    """Tests pour le heartbeat timeout de LobbyState"""

    def setUp(self):
        LobbyState = importlib.import_module("network.server").LobbyState
        self.lobby = LobbyState()

    def _add_fake_client(self, name="TestJoueur"):
        """Ajoute un client factice avec un handler mock"""
        import unittest.mock as mock

        handler = mock.MagicMock()
        info = self.lobby.add_client(name=name, handler=handler, is_host=False)
        return info

    def test_new_client_has_last_message_time(self):
        info = self._add_fake_client()
        self.assertIsNotNone(info)
        self.assertIn("last_message_time", info)

    def test_update_heartbeat_refreshes_timestamp(self):
        info = self._add_fake_client()
        client_id = info["client_id"]

        old_time = info["last_message_time"]
        time.sleep(0.01)
        self.lobby.update_heartbeat(client_id)

        with self.lobby.lock:
            new_time = self.lobby.clients[client_id]["last_message_time"]

        self.assertGreater(new_time, old_time)

    def test_get_timed_out_clients_returns_stale_client(self):
        import network.server as srv_module

        original_timeout = srv_module.HEARTBEAT_TIMEOUT_SECONDS
        srv_module.HEARTBEAT_TIMEOUT_SECONDS = 0.01  # 10ms pour le test

        try:
            info = self._add_fake_client()
            client_id = info["client_id"]
            time.sleep(0.05)  # Attendre le timeout
            timed_out = self.lobby.get_timed_out_clients()
            self.assertIn(client_id, timed_out)
        finally:
            srv_module.HEARTBEAT_TIMEOUT_SECONDS = original_timeout

    def test_fresh_client_not_in_timed_out_list(self):
        info = self._add_fake_client()
        client_id = info["client_id"]

        timed_out = self.lobby.get_timed_out_clients()

        self.assertNotIn(client_id, timed_out)


class InputValidationTests(unittest.TestCase):
    """Tests pour la validation des inputs réseau"""

    def setUp(self):
        LobbyState = importlib.import_module("network.server").LobbyState
        self.lobby = LobbyState()

    def _add_fake_client(self):
        import unittest.mock as mock

        handler = mock.MagicMock()
        return self.lobby.add_client(name="TestJoueur", handler=handler, is_host=False)

    def test_set_input_rejects_non_dict(self):
        info = self._add_fake_client()
        client_id = info["client_id"]

        # Should NOT raise, just ignore
        self.lobby.set_input(client_id, "invalid_string")
        self.lobby.set_input(client_id, 42)
        self.lobby.set_input(client_id, None)

        # Input should remain the default (all False)
        with self.lobby.lock:
            inp = self.lobby.clients[client_id]["input"]
        self.assertFalse(inp["up"])
        self.assertFalse(inp["down"])

    def test_set_input_accepts_valid_dict(self):
        info = self._add_fake_client()
        client_id = info["client_id"]

        self.lobby.set_input(
            client_id, {"up": True, "down": False, "left": True, "right": False}
        )

        with self.lobby.lock:
            inp = self.lobby.clients[client_id]["input"]
        self.assertTrue(inp["up"])
        self.assertTrue(inp["left"])
        self.assertFalse(inp["down"])

    def test_set_input_coerces_truthy_values_to_bool(self):
        info = self._add_fake_client()
        client_id = info["client_id"]

        self.lobby.set_input(
            client_id, {"up": 1, "down": 0, "left": "yes", "right": ""}
        )

        with self.lobby.lock:
            inp = self.lobby.clients[client_id]["input"]
        self.assertIsInstance(inp["up"], bool)
        self.assertIsInstance(inp["down"], bool)
        self.assertTrue(inp["up"])
        self.assertFalse(inp["down"])


if __name__ == "__main__":
    unittest.main()
