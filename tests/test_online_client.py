import importlib
import json
import subprocess
import time
import unittest
from unittest import mock


online_client_module = importlib.import_module("ui.online_client")


class OnlineClientTests(unittest.TestCase):
    def setUp(self):
        self.client = online_client_module.OnlineClient()

    def tearDown(self):
        self.client.disconnect()

    def test_configure_socket_keepalive_enables_socket_option(self):
        sock = mock.Mock()

        getattr(self.client, "_configure_socket_keepalive")(sock)

        sock.setsockopt.assert_called_once_with(
            online_client_module.socket.SOL_SOCKET,
            online_client_module.socket.SO_KEEPALIVE,
            1,
        )

    def test_socket_timeout_sends_ping_when_server_is_idle(self):
        sock = mock.Mock()
        self.client.running = True
        self.client.sock = sock
        setattr(self.client, "_last_server_activity_time", time.monotonic())
        setattr(self.client, "_last_ping_sent_time", 0.0)

        getattr(self.client, "_handle_socket_timeout")(sock)

        payload = sock.sendall.call_args.args[0]
        message = json.loads(payload[4:].decode("utf-8"))
        self.assertEqual(message["type"], "PING")
        self.assertGreater(getattr(self.client, "_last_ping_sent_time"), 0.0)

    def test_socket_timeout_raises_when_server_stays_silent(self):
        sock = mock.Mock()
        self.client.running = True
        self.client.sock = sock
        setattr(
            self.client,
            "_last_server_activity_time",
            time.monotonic()
            - (online_client_module.ONLINE_HEARTBEAT_TIMEOUT_SECONDS + 1.0),
        )
        setattr(self.client, "_last_ping_sent_time", 0.0)

        with self.assertRaises(ConnectionError):
            getattr(self.client, "_handle_socket_timeout")(sock)

    def test_get_online_network_status_prefers_ethernet_when_connected(self):
        interface_listing = (
            "État admin    État          Type            Nom de l’interface\n"
            "------------------------------------------"
            "-------------------------------\n"
            "Activé         Connecté       Dédié            Ethernet\n"
            "Activé         Déconnecté     Dédié            Wi-Fi\n"
        )
        completed_process = subprocess.CompletedProcess(
            args=["netsh"],
            returncode=0,
            stdout=interface_listing,
            stderr="",
        )

        with (
            mock.patch.object(
                online_client_module.subprocess,
                "run",
                return_value=completed_process,
            ),
            mock.patch.object(
                online_client_module,
                "probe_online_service",
                return_value=True,
            ),
            mock.patch.object(
                online_client_module.time,
                "perf_counter",
                side_effect=[1.0, 1.08],
            ),
        ):
            status = online_client_module.get_online_network_status()

        self.assertEqual(status.transport_kind, "ethernet")
        self.assertEqual(status.transport_label, "Ethernet")
        self.assertEqual(status.tone, "success")
        self.assertEqual(status.signal_bars, 4)
        self.assertTrue(status.online_available)

    def test_get_online_network_status_returns_offline_without_link(self):
        interface_listing = (
            "État admin    État          Type            Nom de l’interface\n"
            "------------------------------------------"
            "-------------------------------\n"
            "Activé         Déconnecté     Dédié            Ethernet\n"
            "Activé         Déconnecté     Dédié            Wi-Fi\n"
        )
        completed_process = subprocess.CompletedProcess(
            args=["netsh"],
            returncode=0,
            stdout=interface_listing,
            stderr="",
        )

        with (
            mock.patch.object(
                online_client_module.subprocess,
                "run",
                return_value=completed_process,
            ),
            mock.patch.object(
                online_client_module,
                "probe_online_service",
            ) as probe_online,
        ):
            status = online_client_module.get_online_network_status()

        probe_online.assert_not_called()
        self.assertEqual(status.transport_kind, "offline")
        self.assertEqual(status.transport_label, "Hors ligne")
        self.assertEqual(status.tone, "neutral")
        self.assertEqual(status.signal_bars, 0)
        self.assertFalse(status.online_available)

    def test_get_online_network_status_marks_slow_wifi_as_warning(self):
        interface_listing = (
            "État admin    État          Type            Nom de l’interface\n"
            "------------------------------------------"
            "-------------------------------\n"
            "Activé         Connecté       Dédié            Wi-Fi\n"
        )
        completed_process = subprocess.CompletedProcess(
            args=["netsh"],
            returncode=0,
            stdout=interface_listing,
            stderr="",
        )

        with (
            mock.patch.object(
                online_client_module.subprocess,
                "run",
                return_value=completed_process,
            ),
            mock.patch.object(
                online_client_module,
                "probe_online_service",
                return_value=True,
            ),
            mock.patch.object(
                online_client_module.time,
                "perf_counter",
                side_effect=[2.0, 2.32],
            ),
        ):
            status = online_client_module.get_online_network_status()

        self.assertEqual(status.transport_kind, "wifi")
        self.assertEqual(status.transport_label, "Wi-Fi")
        self.assertEqual(status.tone, "warning")
        self.assertEqual(status.signal_bars, 3)
        self.assertEqual(status.quality_label, "Moyen")

    def test_get_online_network_status_accepts_garbled_windows_output(self):
        interface_listing = (
            "atat admin    atat          type            "
            "nom de latminterface\n"
            "------------------------------------------"
            "-------------------------------\n"
            "activa         connecta       dadia            Ethernet\n"
            "activa         daconnecta     dadia            Wi-Fi\n"
        )
        completed_process = subprocess.CompletedProcess(
            args=["netsh"],
            returncode=0,
            stdout=interface_listing,
            stderr="",
        )

        with (
            mock.patch.object(
                online_client_module.subprocess,
                "run",
                return_value=completed_process,
            ),
            mock.patch.object(
                online_client_module,
                "probe_online_service",
                return_value=False,
            ),
        ):
            status = online_client_module.get_online_network_status()

        self.assertEqual(status.transport_kind, "ethernet")
        self.assertEqual(status.transport_label, "Ethernet")


if __name__ == "__main__":
    unittest.main()
