import asyncio
import importlib
import unittest
from unittest import mock


online_server = importlib.import_module("network.online_server")


class _DummyWriter:
    def __init__(self):
        self.messages = []
        self.closed = False

    def get_extra_info(self, _name):
        return ("127.0.0.1", 27015)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


class _FinishedGameState:
    def __init__(self):
        self.snapshots = []

    def update(self, dt, snapshot):
        self.snapshots.append((dt, snapshot))

    def export_state(self):
        return {"type": "GAME_STATE"}

    def is_finished(self):
        return True

    def build_end_message(self):
        return {"type": "END", "winner": "A"}


class OnlineServerReadyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        online_server.clients.clear()
        online_server.rooms.clear()
        online_server.registry_lock = asyncio.Lock()
        self.send_patcher = mock.patch.object(
            online_server,
            "send",
            new=self._capture_send,
        )
        self.send_patcher.start()

    async def asyncTearDown(self):
        self.send_patcher.stop()

        pending_tasks = []
        for room in online_server.rooms.values():
            task = room.game_task
            if task is not None and not task.done():
                task.cancel()
                pending_tasks.append(task)

        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        online_server.clients.clear()
        online_server.rooms.clear()

    async def _capture_send(self, writer, obj):
        writer.messages.append(dict(obj))

    async def _register_client(
        self,
        client_id: str,
        pseudo: str,
    ) -> _DummyWriter:
        writer = _DummyWriter()
        async with online_server.registry_lock:
            online_server.clients[client_id] = online_server.ClientSession(
                client_id=client_id,
                writer=writer,
                pseudo=pseudo,
            )
        return writer

    async def _create_room_with_two_players(self):
        host_writer = await self._register_client("host", "HostPlayer")
        guest_writer = await self._register_client("guest", "GuestPlayer")

        await online_server.create_room("host", "Ready Room", 2)
        room_id = next(iter(online_server.rooms))
        await online_server.join_room("guest", room_id)
        return room_id, host_writer, guest_writer

    def _clear_messages(self, *writers: _DummyWriter) -> None:
        for writer in writers:
            writer.messages.clear()

    def _last_message_of_type(
        self,
        writer: _DummyWriter,
        message_type: str,
    ) -> dict:
        for message in reversed(writer.messages):
            if message.get("type") == message_type:
                return message
        self.fail(f"Message {message_type} introuvable dans {writer.messages!r}")

    async def test_set_ready_state_broadcasts_ready_players(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        self._clear_messages(host_writer, guest_writer)
        await online_server.set_ready_state("host", True)

        host_update = self._last_message_of_type(host_writer, "ROOM_UPDATE")
        guest_update = self._last_message_of_type(guest_writer, "ROOM_UPDATE")

        self.assertEqual(host_update["room"]["room_id"], room_id)
        self.assertEqual(host_update["room"]["ready_players"], ["HostPlayer"])
        self.assertEqual(guest_update["room"]["ready_players"], ["HostPlayer"])
        self.assertTrue(online_server.clients["host"].ready_to_start)
        self.assertFalse(online_server.clients["guest"].ready_to_start)

    async def test_create_room_keeps_room_duration_in_directory_payloads(self):
        host_writer = await self._register_client("host", "HostPlayer")

        await online_server.create_room(
            "host",
            "Long Room",
            4,
            90,
        )

        room_id = next(iter(online_server.rooms))
        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            summary = online_server.serialize_room_summary_unlocked(room)
            state = online_server.serialize_room_state_unlocked(room)

        self.assertEqual(room.match_duration_seconds, 90)
        self.assertEqual(summary["match_duration_seconds"], 90)
        self.assertEqual(state["match_duration_seconds"], 90)
        created_message = self._last_message_of_type(host_writer, "ROOM_CREATED")
        self.assertEqual(created_message["match_duration_seconds"], 90)

    async def test_prelogin_room_listing_returns_rooms_before_login(self):
        writer = _DummyWriter()
        await self._register_client("host", "HostPlayer")
        await online_server.create_room("host", "Preview Room", 2, 45)

        reader = mock.AsyncMock()
        with mock.patch.object(
            online_server,
            "read_msg",
            side_effect=[
                {"type": "LIST_ROOMS"},
                {"type": "LOGIN", "pseudo": "PreviewGuest"},
            ],
        ):
            login = await online_server.read_login_or_prelogin_request(reader, writer)

        self.assertEqual(login, {"type": "LOGIN", "pseudo": "PreviewGuest"})
        rooms_message = self._last_message_of_type(writer, "ROOMS")
        self.assertEqual(len(rooms_message["rooms"]), 1)
        self.assertEqual(rooms_message["rooms"][0]["name"], "Preview Room")
        self.assertEqual(rooms_message["rooms"][0]["match_duration_seconds"], 45)

    async def test_prelogin_times_out_even_if_client_keeps_listing_rooms(self):
        writer = _DummyWriter()
        reader = mock.AsyncMock()

        async def _wait_for_passthrough(awaitable, timeout):
            del timeout
            return await awaitable

        async def _list_rooms_stub():
            return [
                {
                    "room_id": "preview-room",
                    "name": "Preview Room",
                    "players": 1,
                    "max_players": 2,
                    "match_duration_seconds": 45,
                    "state": "lobby",
                    "host_pseudo": "HostPlayer",
                }
            ]

        with (
            mock.patch.object(
                online_server,
                "read_msg",
                side_effect=[{"type": "LIST_ROOMS"}],
            ),
            mock.patch.object(
                online_server,
                "list_rooms",
                new=_list_rooms_stub,
            ),
            mock.patch.object(
                online_server.asyncio,
                "wait_for",
                new=_wait_for_passthrough,
            ),
            mock.patch.object(
                online_server.time,
                "monotonic",
                side_effect=[100.0, 100.0, 111.0],
            ),
        ):
            with self.assertRaises(TimeoutError):
                await online_server.read_login_or_prelogin_request(
                    reader,
                    writer,
                    timeout_seconds=10.0,
                )

        rooms_message = self._last_message_of_type(writer, "ROOMS")
        self.assertEqual(len(rooms_message["rooms"]), 1)

    async def test_handle_rejects_client_when_handshake_times_out(self):
        reader = mock.Mock()
        writer = _DummyWriter()

        async def _slow_read_msg(_reader):
            await asyncio.sleep(0.02)
            return {"type": "HELLO", "proto": online_server.PROTO_VERSION}

        with (
            mock.patch.object(
                online_server,
                "read_msg",
                new=_slow_read_msg,
            ),
            mock.patch.object(
                online_server,
                "ONLINE_HANDSHAKE_TIMEOUT_SECONDS",
                0.001,
            ),
        ):
            await online_server.handle(reader, writer)

        self.assertIn(
            {"type": "ERROR", "code": "HANDSHAKE_TIMEOUT"},
            writer.messages,
        )
        self.assertTrue(writer.closed)
        self.assertEqual(online_server.clients, {})

    async def test_start_match_uses_selected_room_duration(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        async with online_server.registry_lock:
            online_server.rooms[room_id].match_duration_seconds = 180

        await online_server.set_ready_state("host", True)
        await online_server.set_ready_state("guest", True)
        self._clear_messages(host_writer, guest_writer)

        async def _run_room_match_stub(_room_id: str) -> None:
            return None

        with mock.patch.object(
            online_server,
            "run_room_match",
            new=_run_room_match_stub,
        ):
            await online_server.start_match("host")
            await asyncio.sleep(0)

        self.assertEqual(
            online_server.rooms[room_id].game_state.match_duration_seconds,
            180,
        )

    async def test_start_match_requires_all_players_ready(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        await online_server.set_ready_state("host", True)
        self._clear_messages(host_writer, guest_writer)

        await online_server.start_match("host")

        self.assertEqual(
            host_writer.messages,
            [{"type": "ERROR", "code": "PLAYERS_NOT_READY"}],
        )
        self.assertEqual(guest_writer.messages, [])
        self.assertEqual(online_server.rooms[room_id].state, "lobby")

        await online_server.set_ready_state("guest", True)
        self._clear_messages(host_writer, guest_writer)

        async def _run_room_match_stub(_room_id: str) -> None:
            return None

        with mock.patch.object(
            online_server,
            "run_room_match",
            new=_run_room_match_stub,
        ):
            await online_server.start_match("host")
            await asyncio.sleep(0)

        host_message_types = [message.get("type") for message in host_writer.messages]
        guest_message_types = [message.get("type") for message in guest_writer.messages]

        self.assertEqual(
            host_message_types,
            ["MATCH_STARTED", "START", "ROOM_UPDATE"],
        )
        self.assertEqual(
            guest_message_types,
            ["MATCH_STARTED", "START", "ROOM_UPDATE"],
        )
        self.assertEqual(online_server.rooms[room_id].state, "in_game")

        host_room_update = self._last_message_of_type(
            host_writer,
            "ROOM_UPDATE",
        )
        self.assertEqual(host_room_update["room"]["state"], "in_game")
        self.assertEqual(
            host_room_update["room"]["ready_players"],
            ["HostPlayer", "GuestPlayer"],
        )

    async def test_run_room_match_resets_ready_players_after_end(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        await online_server.set_ready_state("host", True)
        await online_server.set_ready_state("guest", True)
        self._clear_messages(host_writer, guest_writer)

        game_state = _FinishedGameState()

        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            room.state = "in_game"
            room.game_state = game_state

        await online_server.run_room_match(room_id)

        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            self.assertEqual(room.state, "lobby")
            self.assertIsNone(room.game_state)
            self.assertIsNone(room.game_task)
            self.assertFalse(online_server.clients["host"].ready_to_start)
            self.assertFalse(online_server.clients["guest"].ready_to_start)

        host_message_types = [message.get("type") for message in host_writer.messages]
        guest_message_types = [message.get("type") for message in guest_writer.messages]

        self.assertEqual(
            host_message_types,
            ["GAME_STATE", "END", "ROOM_UPDATE", "ASSIGN_SLOT"],
        )
        self.assertEqual(
            guest_message_types,
            ["GAME_STATE", "END", "ROOM_UPDATE", "ASSIGN_SLOT"],
        )

        host_room_update = self._last_message_of_type(
            host_writer,
            "ROOM_UPDATE",
        )
        guest_room_update = self._last_message_of_type(
            guest_writer,
            "ROOM_UPDATE",
        )

        self.assertEqual(host_room_update["room"]["state"], "lobby")
        self.assertEqual(host_room_update["room"]["ready_players"], [])
        self.assertEqual(guest_room_update["room"]["ready_players"], [])
        self.assertEqual(len(game_state.snapshots), 1)

    async def test_leave_room_removes_ready_player_and_transfers_host(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        await online_server.set_ready_state("host", True)
        await online_server.set_ready_state("guest", True)
        self._clear_messages(host_writer, guest_writer)

        await online_server.leave_room("host")

        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            host_client = online_server.clients["host"]
            guest_client = online_server.clients["guest"]
            self.assertEqual(room.host_client_id, "guest")
            self.assertEqual(room.client_ids, ["guest"])
            self.assertIsNone(host_client.room_id)
            self.assertFalse(host_client.ready_to_start)
            self.assertIsNone(host_client.slot)
            self.assertIsNone(host_client.team)
            self.assertEqual(guest_client.room_id, room_id)
            self.assertTrue(guest_client.ready_to_start)

        self.assertEqual(host_writer.messages, [])

        guest_message_types = [message.get("type") for message in guest_writer.messages]
        self.assertEqual(
            guest_message_types,
            ["HOST_CHANGED", "ROOM_UPDATE", "ASSIGN_SLOT"],
        )

        guest_host_changed = self._last_message_of_type(
            guest_writer,
            "HOST_CHANGED",
        )
        guest_room_update = self._last_message_of_type(
            guest_writer,
            "ROOM_UPDATE",
        )
        guest_assign_slot = self._last_message_of_type(
            guest_writer,
            "ASSIGN_SLOT",
        )

        self.assertEqual(guest_host_changed["room_id"], room_id)
        self.assertEqual(guest_host_changed["host_client_id"], "guest")
        self.assertEqual(guest_host_changed["host_pseudo"], "GuestPlayer")
        self.assertEqual(guest_room_update["room"]["players"], ["GuestPlayer"])
        self.assertEqual(
            guest_room_update["room"]["ready_players"],
            ["GuestPlayer"],
        )
        self.assertEqual(guest_room_update["room"]["host_client_id"], "guest")
        self.assertEqual(guest_assign_slot["client_id"], "guest")
        self.assertEqual(guest_assign_slot["slot"], 1)

    async def test_leave_room_closes_active_match_for_everyone(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()

        game_task = mock.Mock()
        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            room.state = "in_game"
            room.game_state = mock.Mock()
            room.game_task = game_task

        self._clear_messages(host_writer, guest_writer)
        await online_server.leave_room("guest")

        self.assertEqual(online_server.rooms, {})
        self.assertEqual(online_server.clients, {})
        self.assertTrue(host_writer.closed)
        self.assertTrue(guest_writer.closed)
        game_task.cancel.assert_called_once_with()

        self.assertEqual(host_writer.messages[0]["type"], "DISCONNECTED")
        self.assertEqual(host_writer.messages[0]["code"], "ROOM_CLOSED")
        self.assertIn(
            "GuestPlayer a quitté la partie", host_writer.messages[0]["message"]
        )
        self.assertEqual(guest_writer.messages[0]["type"], "DISCONNECTED")
        self.assertEqual(guest_writer.messages[0]["code"], "ROOM_CLOSED")

    async def test_list_rooms_closes_room_after_fifteen_minutes(self):
        host_writer = await self._register_client("host", "HostPlayer")
        await online_server.create_room("host", "Session longue", 2)
        self._clear_messages(host_writer)

        room_id = next(iter(online_server.rooms))
        async with online_server.registry_lock:
            online_server.rooms[room_id].created_at = (
                online_server.time.time()
                - online_server.ONLINE_ROOM_OPEN_TIMEOUT_SECONDS
                - 1.0
            )

        rooms = await online_server.list_rooms()

        self.assertEqual(rooms, [])
        self.assertEqual(online_server.rooms, {})
        self.assertEqual(online_server.clients, {})
        self.assertTrue(host_writer.closed)
        self.assertEqual(host_writer.messages[0]["type"], "DISCONNECTED")
        self.assertEqual(host_writer.messages[0]["code"], "ROOM_EXPIRED")
        self.assertIn("15 minutes", host_writer.messages[0]["message"])

    async def test_list_rooms_prunes_room_with_only_stale_client(self):
        await self._register_client("host", "HostPlayer")
        await online_server.create_room("host", "Ghost Room", 2)

        stale_at = (
            online_server.time.monotonic()
            - online_server.ONLINE_CLIENT_STALE_TIMEOUT_SECONDS
            - 1.0
        )
        async with online_server.registry_lock:
            online_server.clients["host"].last_activity_at = stale_at

        rooms = await online_server.list_rooms()

        self.assertEqual(rooms, [])
        self.assertEqual(online_server.rooms, {})
        self.assertEqual(online_server.clients, {})

    async def test_list_rooms_prunes_stale_guest_from_room_counts(self):
        room_id, host_writer, guest_writer = await self._create_room_with_two_players()
        self._clear_messages(host_writer, guest_writer)

        stale_at = (
            online_server.time.monotonic()
            - online_server.ONLINE_CLIENT_STALE_TIMEOUT_SECONDS
            - 1.0
        )
        async with online_server.registry_lock:
            online_server.clients["guest"].last_activity_at = stale_at

        rooms = await online_server.list_rooms()

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["room_id"], room_id)
        self.assertEqual(rooms[0]["players"], 1)
        self.assertEqual(host_writer.messages[-2]["type"], "ROOM_UPDATE")
        self.assertEqual(host_writer.messages[-1]["type"], "ASSIGN_SLOT")
        async with online_server.registry_lock:
            room = online_server.rooms[room_id]
            self.assertEqual(room.client_ids, ["host"])
            self.assertNotIn("guest", online_server.clients)

    async def test_list_rooms_logs_diagnostics_when_enabled(self):
        await self._register_client("host", "HostPlayer")
        await online_server.create_room("host", "Diag Room", 2)

        with (
            mock.patch.object(
                online_server,
                "ONLINE_DIAGNOSTIC_LIST_ROOMS",
                True,
            ),
            mock.patch("builtins.print") as mocked_print,
        ):
            rooms = await online_server.list_rooms()

        self.assertEqual(len(rooms), 1)
        printed_lines = [
            " ".join(str(arg) for arg in call.args)
            for call in mocked_print.call_args_list
        ]
        self.assertTrue(
            any(
                "[ONLINE][LIST_ROOMS]" in line
                and '"room_id"' in line
                and '"name":"Diag Room"' in line
                and '"client_id":"host"' in line
                for line in printed_lines
            ),
            printed_lines,
        )

    def test_build_start_server_kwargs_enables_keep_alive_when_supported(self):
        with mock.patch.object(
            online_server,
            "_supports_start_server_keep_alive",
            return_value=True,
        ):
            self.assertEqual(
                online_server.build_start_server_kwargs(),
                {"keep_alive": True},
            )

    def test_build_start_server_kwargs_is_empty_without_support(self):
        with mock.patch.object(
            online_server,
            "_supports_start_server_keep_alive",
            return_value=False,
        ):
            self.assertEqual(online_server.build_start_server_kwargs(), {})

    def test_build_welcome_payload_includes_ready_capability(self):
        payload = online_server.build_welcome_payload()

        self.assertEqual(payload["type"], "WELCOME")
        self.assertEqual(payload["proto"], online_server.PROTO_VERSION)
        self.assertEqual(
            payload["capabilities"],
            {"ready_state": True},
        )


if __name__ == "__main__":
    unittest.main()
