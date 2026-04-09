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
get_lan_address_info = importlib.import_module(
    "network.net_utils"
).get_lan_address_info
parse_server_invitation = importlib.import_module(
    "network.net_utils"
).parse_server_invitation
start_server_in_background = importlib.import_module(
    "network.server"
).start_server_in_background


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
            messages = (
                host_client.poll_messages() + guest_client.poll_messages()
            )
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
            messages = (
                host_client.poll_messages() + guest_client.poll_messages()
            )
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


if __name__ == "__main__":
    unittest.main()
