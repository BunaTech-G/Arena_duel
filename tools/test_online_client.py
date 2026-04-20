from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    from ui.online_client import OnlineClient


def message_type_of(message: dict) -> str:
    return str(message.get("type") or "").strip().upper()


def disconnect_error(messages: dict[str, dict]) -> str | None:
    disconnected_message = messages.get("DISCONNECTED")
    if disconnected_message is None:
        return None
    return str(disconnected_message.get("error") or "erreur inconnue")


def login_pseudo(messages: dict[str, dict], fallback: str) -> str:
    login_ok = messages.get("LOGIN_OK") or {}
    normalized = str(login_ok.get("pseudo") or fallback).strip()
    return normalized or fallback


def room_payload_from_messages(messages: dict[str, dict]) -> dict:
    room_update = messages.get("ROOM_UPDATE") or {}
    room_payload = room_update.get("room")
    if isinstance(room_payload, dict):
        return room_payload
    return {}


def room_host_pseudo(messages: dict[str, dict]) -> str | None:
    room_payload = room_payload_from_messages(messages)
    host_pseudo = str(room_payload.get("host_pseudo") or "").strip()
    if host_pseudo:
        return host_pseudo

    joined_message = messages.get("JOINED") or {}
    joined_host = str(joined_message.get("host_pseudo") or "").strip()
    return joined_host or None


def room_state_from_messages(messages: dict[str, dict]) -> str | None:
    room_payload = room_payload_from_messages(messages)
    state = str(room_payload.get("state") or "").strip().lower()
    return state or None


def room_ready_players_from_messages(messages: dict[str, dict]) -> list[str]:
    room_payload = room_payload_from_messages(messages)
    return [
        str(player).strip()
        for player in room_payload.get("ready_players", [])
        if str(player).strip()
    ]


def assigned_slot(messages: dict[str, dict]) -> int | None:
    assignment = messages.get("ASSIGN_SLOT") or {}
    try:
        return int(assignment.get("slot"))
    except (TypeError, ValueError):
        return None


def collect_messages(
    client: "OnlineClient",
    *,
    timeout_seconds: float,
) -> list[dict]:
    deadline = time.monotonic() + timeout_seconds
    seen: list[dict] = []

    while time.monotonic() < deadline:
        message = client.poll()
        if message is None:
            time.sleep(0.05)
            continue

        print(f"<<< {message}")
        seen.append(message)
        if message_type_of(message) == "DISCONNECTED":
            break

    return seen


def wait_for_messages(
    client: "OnlineClient",
    *,
    timeout_seconds: float,
    required_types: set[str],
) -> dict[str, dict]:
    deadline = time.monotonic() + timeout_seconds
    seen: dict[str, dict] = {}

    while time.monotonic() < deadline:
        message = client.poll()
        if message is None:
            time.sleep(0.05)
            continue

        message_type = message_type_of(message)
        print(f"<<< {message}")
        seen[message_type] = message

        if message_type == "DISCONNECTED":
            break

        if required_types.issubset(set(seen)):
            return seen

    return seen


def wait_for_post_match_reset(
    client: "OnlineClient",
    *,
    timeout_seconds: float,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    seen: dict[str, dict] = {}
    end_seen = False
    lobby_update_seen = False
    assignment_after_end = False

    while time.monotonic() < deadline:
        message = client.poll()
        if message is None:
            time.sleep(0.05)
            continue

        message_type = message_type_of(message)
        print(f"<<< {message}")
        seen[message_type] = message

        if message_type == "DISCONNECTED":
            break

        if message_type == "END":
            end_seen = True
            continue

        if not end_seen:
            continue

        if message_type == "ROOM_UPDATE":
            room_payload = room_payload_from_messages({"ROOM_UPDATE": message})
            state = str(room_payload.get("state") or "").strip().lower()
            lobby_update_seen = state == "lobby"
            if assignment_after_end and lobby_update_seen:
                return {
                    "messages": seen,
                    "end_seen": end_seen,
                    "lobby_update_seen": lobby_update_seen,
                    "assignment_after_end": assignment_after_end,
                }
            continue

        if message_type == "ASSIGN_SLOT":
            assignment_after_end = True
            if lobby_update_seen:
                return {
                    "messages": seen,
                    "end_seen": end_seen,
                    "lobby_update_seen": lobby_update_seen,
                    "assignment_after_end": assignment_after_end,
                }

    return {
        "messages": seen,
        "end_seen": end_seen,
        "lobby_update_seen": lobby_update_seen,
        "assignment_after_end": assignment_after_end,
    }


def room_players_from_messages(messages: dict[str, dict]) -> list[str]:
    room_payload = room_payload_from_messages(messages)
    return [
        str(player).strip()
        for player in room_payload.get("players", [])
        if str(player).strip()
    ]


def run_basic_scenario(args, *, OnlineClient, OnlineConnectionError) -> int:
    client = OnlineClient()

    try:
        print(f">>> connexion vers {args.host}:{args.port} en tant que {args.pseudo}")
        client.connect(args.host, args.port, args.pseudo)

        auth_messages = wait_for_messages(
            client,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(auth_messages)
        if error is not None:
            print("Connexion interrompue:", error)
            return 1

        missing_auth = {"WELCOME", "LOGIN_OK"} - set(auth_messages)
        if missing_auth:
            print(f"Réponse serveur incomplète: {sorted(missing_auth)}")
            return 1

        print(">>> LIST_ROOMS")
        client.send({"type": "LIST_ROOMS"})
        room_messages = wait_for_messages(
            client,
            timeout_seconds=args.timeout,
            required_types={"ROOMS"},
        )
        error = disconnect_error(room_messages)
        if error is not None:
            print("Connexion interrompue:", error)
            return 1

        if "ROOMS" not in room_messages:
            print("Le serveur n'a pas renvoyé ROOMS dans le délai imparti.")
            return 1

        rooms = room_messages["ROOMS"].get("rooms", [])
        print(f"Rooms reçues: {len(rooms)}")
        return 0
    except OnlineConnectionError as error:
        print(f"Erreur online: {error}")
        return 1
    finally:
        client.disconnect()


def build_create_join_names(base_pseudo: str) -> tuple[str, str, str]:
    stamp = int(time.time() * 1000)
    base = str(base_pseudo or "debug_online").strip() or "debug_online"
    creator_name = f"{base}_creator_{stamp}"
    joiner_name = f"{base}_joiner_{stamp}"
    room_name = f"Smoke Session {stamp}"
    return creator_name, joiner_name, room_name


def find_room_by_id(rooms: list[dict], room_id: str) -> dict | None:
    normalized_room_id = str(room_id or "").strip()
    for room in rooms:
        if str(room.get("room_id") or "").strip() == normalized_room_id:
            return room
    return None


def run_create_join_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
) -> int:
    creator = OnlineClient()
    joiner = OnlineClient()
    creator_name, joiner_name, room_name = build_create_join_names(args.pseudo)
    room_id = ""

    try:
        print(
            f">>> create-join smoke vers {args.host}:{args.port} "
            f"avec {creator_name} puis {joiner_name}"
        )
        creator.connect(args.host, args.port, creator_name)
        creator_auth = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(creator_auth)
        if error is not None:
            print("Créateur interrompu:", error)
            return 1

        missing_auth = {"WELCOME", "LOGIN_OK"} - set(creator_auth)
        if missing_auth:
            print(
                "Authentification créateur incomplète:",
                sorted(missing_auth),
            )
            return 1
        creator_login_pseudo = login_pseudo(creator_auth, creator_name)

        print(f">>> CREATE_ROOM {room_name}")
        creator.send(
            {
                "type": "CREATE_ROOM",
                "name": room_name,
                "max_players": args.max_players,
            }
        )
        created_messages = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_CREATED"},
        )
        error = disconnect_error(created_messages)
        if error is not None:
            print("Créateur interrompu après CREATE_ROOM:", error)
            return 1

        created_message = created_messages.get("ROOM_CREATED")
        if created_message is None:
            print("Le serveur n'a pas renvoyé ROOM_CREATED.")
            return 1

        room_id = str(created_message.get("room_id") or "").strip()
        if not room_id:
            print("ROOM_CREATED a été reçu sans room_id exploitable.")
            return 1

        creator_join = wait_for_messages(
            creator,
            timeout_seconds=min(args.timeout, 0.75),
            required_types={"JOINED", "ROOM_UPDATE", "ASSIGN_SLOT"},
        )
        if not {"JOINED", "ROOM_UPDATE", "ASSIGN_SLOT"}.issubset(creator_join):
            print(f">>> JOIN_ROOM créateur {room_id}")
            creator.send({"type": "JOIN_ROOM", "room_id": room_id})
            creator_join = wait_for_messages(
                creator,
                timeout_seconds=args.timeout,
                required_types={"JOINED", "ROOM_UPDATE", "ASSIGN_SLOT"},
            )

        error = disconnect_error(creator_join)
        if error is not None:
            print("Créateur interrompu après son JOIN_ROOM:", error)
            return 1

        if assigned_slot(creator_join) is None:
            print("Le créateur n'a pas reçu ASSIGN_SLOT.")
            return 1

        if "JOINED" not in creator_join or "ROOM_UPDATE" not in creator_join:
            print("Le créateur n'a pas reçu JOINED et ROOM_UPDATE complets.")
            return 1

        joiner.connect(args.host, args.port, joiner_name)
        joiner_auth = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(joiner_auth)
        if error is not None:
            print("Rejoignant interrompu:", error)
            return 1

        missing_auth = {"WELCOME", "LOGIN_OK"} - set(joiner_auth)
        if missing_auth:
            print(
                "Authentification rejoignant incomplète:",
                sorted(missing_auth),
            )
            return 1
        joiner_login_pseudo = login_pseudo(joiner_auth, joiner_name)

        listed_room = None
        for attempt in range(1, args.list_retries + 1):
            print(f">>> LIST_ROOMS tentative {attempt}/{args.list_retries}")
            joiner.send({"type": "LIST_ROOMS"})
            room_messages = wait_for_messages(
                joiner,
                timeout_seconds=args.timeout,
                required_types={"ROOMS"},
            )
            error = disconnect_error(room_messages)
            if error is not None:
                print("Rejoignant interrompu pendant LIST_ROOMS:", error)
                return 1

            listed_room = find_room_by_id(
                room_messages.get("ROOMS", {}).get("rooms", []),
                room_id,
            )
            if listed_room is not None:
                break

            time.sleep(args.list_retry_delay)

        if listed_room is None:
            print("La room créée n'apparaît pas dans LIST_ROOMS pour le second client.")
            print(f">>> JOIN_ROOM direct rejoignant {room_id}")
            joiner.send({"type": "JOIN_ROOM", "room_id": room_id})
            direct_join_messages = wait_for_messages(
                joiner,
                timeout_seconds=args.timeout,
                required_types={"JOINED"},
            )
            direct_error = disconnect_error(direct_join_messages)
            if direct_error is not None:
                print(
                    "Rejoignant interrompu pendant JOIN_ROOM direct:",
                    direct_error,
                )
            elif "ERROR" in direct_join_messages:
                print(
                    "JOIN_ROOM direct a échoué:",
                    direct_join_messages["ERROR"].get(
                        "code",
                        "erreur inconnue",
                    ),
                )
            elif "JOINED" in direct_join_messages:
                print("JOIN_ROOM direct fonctionne malgré LIST_ROOMS vide.")
            else:
                print("JOIN_ROOM direct n'a renvoyé aucune réponse exploitable.")

            creator_followup = collect_messages(
                creator,
                timeout_seconds=min(args.timeout, 3.0),
            )
            if creator_followup:
                print(
                    "Messages supplémentaires reçus côté créateur:",
                    creator_followup,
                )
            return 1

        print(f">>> JOIN_ROOM rejoignant {room_id}")
        joiner.send({"type": "JOIN_ROOM", "room_id": room_id})
        joiner_join = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"JOINED", "ROOM_UPDATE", "ASSIGN_SLOT"},
        )
        error = disconnect_error(joiner_join)
        if error is not None:
            print("Rejoignant interrompu après JOIN_ROOM:", error)
            return 1

        if assigned_slot(joiner_join) is None:
            print("Le rejoignant n'a pas reçu ASSIGN_SLOT.")
            return 1

        if "JOINED" not in joiner_join or "ROOM_UPDATE" not in joiner_join:
            if "ERROR" in joiner_join:
                print(
                    "JOIN_ROOM rejoignant a échoué:",
                    joiner_join["ERROR"].get("code", "erreur inconnue"),
                )
            else:
                print("Le rejoignant n'a pas reçu JOINED et ROOM_UPDATE complets.")
            return 1

        creator_followup_map = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(creator_followup_map)
        if error is not None:
            print("Créateur interrompu après l'arrivée du rejoignant:", error)
            return 1

        creator_players = (
            creator_followup_map["ROOM_UPDATE"]
            .get(
                "room",
                {},
            )
            .get("players", [])
        )
        joiner_players = (
            joiner_join["ROOM_UPDATE"]
            .get("room", {})
            .get(
                "players",
                [],
            )
        )

        if (
            creator_login_pseudo not in creator_players
            or joiner_login_pseudo not in creator_players
        ):
            print("ROOM_UPDATE créateur incomplet:", creator_players)
            return 1

        if (
            creator_login_pseudo not in joiner_players
            or joiner_login_pseudo not in joiner_players
        ):
            print("ROOM_UPDATE rejoignant incomplet:", joiner_players)
            return 1

        print("CREATE_JOIN_SMOKE_OK")
        print(
            {
                "room_id": room_id,
                "room_name": room_name,
                "listed_room": listed_room,
                "creator_players": creator_players,
                "joiner_players": joiner_players,
            }
        )
        return 0
    except OnlineConnectionError as error:
        print(f"Erreur online: {error}")
        return 1
    finally:
        creator.disconnect()
        joiner.disconnect()


def run_host_migration_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
) -> int:
    creator = OnlineClient()
    joiner = OnlineClient()
    creator_name, joiner_name, room_name = build_create_join_names(args.pseudo)

    try:
        print(
            f">>> host-migration smoke vers {args.host}:{args.port} "
            f"avec {creator_name} puis {joiner_name}"
        )
        creator.connect(args.host, args.port, creator_name)
        creator_auth = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(creator_auth)
        if error is not None:
            print("Créateur interrompu:", error)
            return 1

        creator_login_pseudo = login_pseudo(creator_auth, creator_name)

        print(f">>> CREATE_ROOM {room_name}")
        creator.send(
            {
                "type": "CREATE_ROOM",
                "name": room_name,
                "max_players": args.max_players,
            }
        )
        created_messages = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_CREATED"},
        )
        error = disconnect_error(created_messages)
        if error is not None:
            print("Créateur interrompu après CREATE_ROOM:", error)
            return 1

        created_message = created_messages.get("ROOM_CREATED")
        if created_message is None:
            print("Le serveur n'a pas renvoyé ROOM_CREATED.")
            return 1

        room_id = str(created_message.get("room_id") or "").strip()
        if not room_id:
            print("ROOM_CREATED a été reçu sans room_id exploitable.")
            return 1

        creator_join = wait_for_messages(
            creator,
            timeout_seconds=min(args.timeout, 0.75),
            required_types={"JOINED", "ROOM_UPDATE"},
        )
        if "JOINED" not in creator_join or "ROOM_UPDATE" not in creator_join:
            print(f">>> JOIN_ROOM créateur {room_id}")
            creator.send({"type": "JOIN_ROOM", "room_id": room_id})
            creator_join = wait_for_messages(
                creator,
                timeout_seconds=args.timeout,
                required_types={"JOINED", "ROOM_UPDATE"},
            )

        error = disconnect_error(creator_join)
        if error is not None:
            print("Créateur interrompu après son JOIN_ROOM:", error)
            return 1

        if room_host_pseudo(creator_join) != creator_login_pseudo:
            print(
                "Le créateur n'est pas marqué comme hôte initial:",
                room_payload_from_messages(creator_join),
            )
            return 1

        joiner.connect(args.host, args.port, joiner_name)
        joiner_auth = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(joiner_auth)
        if error is not None:
            print("Rejoignant interrompu:", error)
            return 1

        joiner_login_pseudo = login_pseudo(joiner_auth, joiner_name)

        listed_room = None
        for attempt in range(1, args.list_retries + 1):
            print(f">>> LIST_ROOMS tentative {attempt}/{args.list_retries}")
            joiner.send({"type": "LIST_ROOMS"})
            room_messages = wait_for_messages(
                joiner,
                timeout_seconds=args.timeout,
                required_types={"ROOMS"},
            )
            error = disconnect_error(room_messages)
            if error is not None:
                print("Rejoignant interrompu pendant LIST_ROOMS:", error)
                return 1

            listed_room = find_room_by_id(
                room_messages.get("ROOMS", {}).get("rooms", []),
                room_id,
            )
            if listed_room is not None:
                break

            time.sleep(args.list_retry_delay)

        if listed_room is None:
            print("Room absente de LIST_ROOMS pendant le test hôte.")
            return 1

        print(f">>> JOIN_ROOM rejoignant {room_id}")
        joiner.send({"type": "JOIN_ROOM", "room_id": room_id})
        joiner_join = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"JOINED", "ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_join)
        if error is not None:
            print("Rejoignant interrompu après JOIN_ROOM:", error)
            return 1

        creator_followup = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(creator_followup)
        if error is not None:
            print("Créateur interrompu avant le test de départ hôte:", error)
            return 1

        creator.disconnect()

        joiner_after_host_leave = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_after_host_leave)
        if error is not None:
            print("Rejoignant interrompu après le départ de l'hôte:", error)
            return 1

        migrated_host = room_host_pseudo(joiner_after_host_leave)
        if migrated_host != joiner_login_pseudo:
            print(
                "La migration d'hôte a échoué:",
                room_payload_from_messages(joiner_after_host_leave),
            )
            return 1

        final_players = room_payload_from_messages(joiner_after_host_leave).get(
            "players", []
        )
        if final_players != [joiner_login_pseudo]:
            print("Etat final joueur inattendu:", final_players)
            return 1

        print("HOST_MIGRATION_SMOKE_OK")
        print(
            {
                "room_id": room_id,
                "initial_host": creator_login_pseudo,
                "new_host": migrated_host,
                "final_players": final_players,
            }
        )
        return 0
    except OnlineConnectionError as error:
        print(f"Erreur online: {error}")
        return 1
    finally:
        creator.disconnect()
        joiner.disconnect()


def run_start_match_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
) -> int:
    return run_match_flow_scenario(
        args,
        OnlineClient=OnlineClient,
        OnlineConnectionError=OnlineConnectionError,
        wait_for_end=False,
    )


def run_end_match_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
) -> int:
    return run_match_flow_scenario(
        args,
        OnlineClient=OnlineClient,
        OnlineConnectionError=OnlineConnectionError,
        wait_for_end=True,
    )


def run_mid_match_leave_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
) -> int:
    return run_match_flow_scenario(
        args,
        OnlineClient=OnlineClient,
        OnlineConnectionError=OnlineConnectionError,
        wait_for_end=True,
        leave_during_match_role=args.leave_role,
    )


def run_match_flow_scenario(
    args,
    *,
    OnlineClient,
    OnlineConnectionError,
    wait_for_end: bool,
    leave_during_match_role: str | None = None,
) -> int:
    creator = OnlineClient()
    joiner = OnlineClient()
    creator_name, joiner_name, room_name = build_create_join_names(args.pseudo)

    try:
        print(
            f">>> start-match smoke vers {args.host}:{args.port} "
            f"avec {creator_name} puis {joiner_name}"
        )
        creator.connect(args.host, args.port, creator_name)
        creator_auth = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(creator_auth)
        if error is not None:
            print("Créateur interrompu:", error)
            return 1

        creator_login_pseudo = login_pseudo(creator_auth, creator_name)

        print(f">>> CREATE_ROOM {room_name}")
        creator.send(
            {
                "type": "CREATE_ROOM",
                "name": room_name,
                "max_players": args.max_players,
            }
        )
        created_messages = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_CREATED"},
        )
        error = disconnect_error(created_messages)
        if error is not None:
            print("Créateur interrompu après CREATE_ROOM:", error)
            return 1

        created_message = created_messages.get("ROOM_CREATED")
        if created_message is None:
            print("Le serveur n'a pas renvoyé ROOM_CREATED.")
            return 1

        room_id = str(created_message.get("room_id") or "").strip()
        if not room_id:
            print("ROOM_CREATED a été reçu sans room_id exploitable.")
            return 1

        creator_join = wait_for_messages(
            creator,
            timeout_seconds=min(args.timeout, 0.75),
            required_types={"JOINED", "ROOM_UPDATE"},
        )
        if "JOINED" not in creator_join or "ROOM_UPDATE" not in creator_join:
            print(f">>> JOIN_ROOM créateur {room_id}")
            creator.send({"type": "JOIN_ROOM", "room_id": room_id})
            creator_join = wait_for_messages(
                creator,
                timeout_seconds=args.timeout,
                required_types={"JOINED", "ROOM_UPDATE"},
            )

        error = disconnect_error(creator_join)
        if error is not None:
            print("Créateur interrompu après son JOIN_ROOM:", error)
            return 1

        joiner.connect(args.host, args.port, joiner_name)
        joiner_auth = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"WELCOME", "LOGIN_OK"},
        )
        error = disconnect_error(joiner_auth)
        if error is not None:
            print("Rejoignant interrompu:", error)
            return 1
        joiner_login_pseudo = login_pseudo(joiner_auth, joiner_name)

        listed_room = None
        for attempt in range(1, args.list_retries + 1):
            print(f">>> LIST_ROOMS tentative {attempt}/{args.list_retries}")
            joiner.send({"type": "LIST_ROOMS"})
            room_messages = wait_for_messages(
                joiner,
                timeout_seconds=args.timeout,
                required_types={"ROOMS"},
            )
            error = disconnect_error(room_messages)
            if error is not None:
                print("Rejoignant interrompu pendant LIST_ROOMS:", error)
                return 1

            listed_room = find_room_by_id(
                room_messages.get("ROOMS", {}).get("rooms", []),
                room_id,
            )
            if listed_room is not None:
                break

            time.sleep(args.list_retry_delay)

        if listed_room is None:
            print("Room absente de LIST_ROOMS pendant le test de lancement.")
            return 1

        print(f">>> JOIN_ROOM rejoignant {room_id}")
        joiner.send({"type": "JOIN_ROOM", "room_id": room_id})
        joiner_join = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"JOINED", "ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_join)
        if error is not None:
            print("Rejoignant interrompu après JOIN_ROOM:", error)
            return 1

        creator_followup = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(creator_followup)
        if error is not None:
            print("Créateur interrompu avant START_MATCH:", error)
            return 1

        print(">>> SET_READY créateur")
        creator.send({"type": "SET_READY", "ready": True})
        creator_ready = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(creator_ready)
        if error is not None:
            print("Créateur interrompu pendant SET_READY:", error)
            return 1

        joiner_ready_notice = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_ready_notice)
        if error is not None:
            print("Rejoignant interrompu après le prêt du créateur:", error)
            return 1

        print(">>> SET_READY rejoignant")
        joiner.send({"type": "SET_READY", "ready": True})
        joiner_ready = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_ready)
        if error is not None:
            print("Rejoignant interrompu pendant SET_READY:", error)
            return 1

        creator_ready_notice = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"ROOM_UPDATE"},
        )
        error = disconnect_error(creator_ready_notice)
        if error is not None:
            print("Créateur interrompu après le prêt du rejoignant:", error)
            return 1

        creator_ready_players = room_ready_players_from_messages(
            creator_ready_notice,
        )
        joiner_ready_players = room_ready_players_from_messages(joiner_ready)
        if (
            creator_login_pseudo not in creator_ready_players
            or joiner_login_pseudo not in creator_ready_players
        ):
            print("Etat prêt créateur incomplet:", creator_ready_players)
            return 1

        if (
            creator_login_pseudo not in joiner_ready_players
            or joiner_login_pseudo not in joiner_ready_players
        ):
            print("Etat prêt rejoignant incomplet:", joiner_ready_players)
            return 1

        print(">>> START_MATCH hôte")
        creator.send({"type": "START_MATCH"})

        creator_started = wait_for_messages(
            creator,
            timeout_seconds=args.timeout,
            required_types={"MATCH_STARTED", "START", "STATE", "ROOM_UPDATE"},
        )
        error = disconnect_error(creator_started)
        if error is not None:
            print("Créateur interrompu pendant START_MATCH:", error)
            return 1

        joiner_started = wait_for_messages(
            joiner,
            timeout_seconds=args.timeout,
            required_types={"MATCH_STARTED", "START", "STATE", "ROOM_UPDATE"},
        )
        error = disconnect_error(joiner_started)
        if error is not None:
            print("Rejoignant interrompu pendant START_MATCH:", error)
            return 1

        creator_state = room_state_from_messages(creator_started)
        joiner_state = room_state_from_messages(joiner_started)
        if creator_state != "in_game" or joiner_state != "in_game":
            print(
                "Etat de room inattendu après START_MATCH:",
                {
                    "creator": room_payload_from_messages(creator_started),
                    "joiner": room_payload_from_messages(joiner_started),
                },
            )
            return 1

        if not creator_started.get("STATE") or not joiner_started.get("STATE"):
            print("Le serveur n'a pas produit de STATE après START_MATCH.")
            return 1

        if room_host_pseudo(creator_started) != creator_login_pseudo:
            print(
                "L'hôte final est inattendu après START_MATCH:",
                room_payload_from_messages(creator_started),
            )
            return 1

        remaining_client = None
        remaining_login_pseudo = None

        if leave_during_match_role is not None:
            if leave_during_match_role == "host":
                print(f">>> départ en match de l'hôte {creator_login_pseudo}")
                creator.disconnect()
                remaining_client = joiner
                remaining_login_pseudo = joiner_login_pseudo
                remaining_expected_host = joiner_login_pseudo
                leave_required_types = {"HOST_CHANGED", "ROOM_UPDATE"}
            else:
                print(f">>> départ en match du rejoignant {joiner_login_pseudo}")
                joiner.disconnect()
                remaining_client = creator
                remaining_login_pseudo = creator_login_pseudo
                remaining_expected_host = creator_login_pseudo
                leave_required_types = {"ROOM_UPDATE"}

            remaining_after_leave = wait_for_messages(
                remaining_client,
                timeout_seconds=args.timeout,
                required_types=leave_required_types,
            )
            error = disconnect_error(remaining_after_leave)
            if error is not None:
                print(
                    "Client restant interrompu après le départ en match:",
                    error,
                )
                return 1

            if (
                leave_during_match_role == "host"
                and "HOST_CHANGED" not in remaining_after_leave
            ):
                print(
                    "HOST_CHANGED manquant après le départ de l'hôte:",
                    remaining_after_leave,
                )
                return 1

            if room_state_from_messages(remaining_after_leave) != "in_game":
                print(
                    ("Le salon n'est pas resté en in_game après le départ en match:"),
                    room_payload_from_messages(remaining_after_leave),
                )
                return 1

            remaining_players = room_players_from_messages(remaining_after_leave)
            if remaining_players != [remaining_login_pseudo]:
                print(
                    "Etat joueur inattendu après le départ en match:",
                    remaining_players,
                )
                return 1

            remaining_host = room_host_pseudo(remaining_after_leave)
            if remaining_host != remaining_expected_host:
                print(
                    "Hôte inattendu après le départ en match:",
                    room_payload_from_messages(remaining_after_leave),
                )
                return 1

        if wait_for_end:
            if leave_during_match_role is not None:
                remaining_reset = wait_for_post_match_reset(
                    remaining_client,
                    timeout_seconds=args.match_timeout,
                )
                error = disconnect_error(remaining_reset["messages"])
                if error is not None:
                    print("Client restant interrompu avant END:", error)
                    return 1

                if not remaining_reset["end_seen"]:
                    print(
                        (
                            "Le serveur n'a pas terminé la joute "
                            "après le départ en match."
                        )
                    )
                    return 1

                if not remaining_reset["lobby_update_seen"]:
                    print(
                        (
                            "Le salon n'est pas repassé en lobby "
                            "après le départ en match:"
                        ),
                        remaining_reset["messages"].get("ROOM_UPDATE"),
                    )
                    return 1

                if not remaining_reset["assignment_after_end"]:
                    print(
                        ("ASSIGN_SLOT n'a pas été renvoyé après départ en match."),
                        remaining_reset,
                    )
                    return 1

                final_players = room_players_from_messages(remaining_reset["messages"])
                if final_players != [remaining_login_pseudo]:
                    print(
                        "ROOM_UPDATE final restant inattendu:",
                        final_players,
                    )
                    return 1

                remaining_end = remaining_reset["messages"].get("END") or {}
                final_room_state = room_state_from_messages(remaining_reset["messages"])
                print("MID_MATCH_LEAVE_SMOKE_OK")
                print(
                    {
                        "leave_role": leave_during_match_role,
                        "room_id": room_id,
                        "room_name": room_name,
                        "remaining_player": remaining_login_pseudo,
                        "host_after_leave": remaining_expected_host,
                        "state": final_room_state,
                        "winner_text": remaining_end.get("winner_text"),
                        "team_a_score": remaining_end.get("team_a_score"),
                        "team_b_score": remaining_end.get("team_b_score"),
                    }
                )
                return 0

            creator_reset = wait_for_post_match_reset(
                creator,
                timeout_seconds=args.match_timeout,
            )
            error = disconnect_error(creator_reset["messages"])
            if error is not None:
                print("Créateur interrompu avant END:", error)
                return 1

            joiner_reset = wait_for_post_match_reset(
                joiner,
                timeout_seconds=args.match_timeout,
            )
            error = disconnect_error(joiner_reset["messages"])
            if error is not None:
                print("Rejoignant interrompu avant END:", error)
                return 1

            if not creator_reset["end_seen"] or not joiner_reset["end_seen"]:
                print("Le serveur n'a pas terminé la joute dans le délai prévu.")
                return 1

            if (
                not creator_reset["lobby_update_seen"]
                or not joiner_reset["lobby_update_seen"]
            ):
                print(
                    "Le salon n'est pas repassé en lobby après END:",
                    {
                        "creator": creator_reset["messages"].get("ROOM_UPDATE"),
                        "joiner": joiner_reset["messages"].get("ROOM_UPDATE"),
                    },
                )
                return 1

            if (
                not creator_reset["assignment_after_end"]
                or not joiner_reset["assignment_after_end"]
            ):
                print(
                    "ASSIGN_SLOT n'a pas été renvoyé après END.",
                    {
                        "creator": creator_reset,
                        "joiner": joiner_reset,
                    },
                )
                return 1

            creator_final_players = room_payload_from_messages(
                creator_reset["messages"]
            ).get("players", [])
            joiner_final_players = room_payload_from_messages(
                joiner_reset["messages"]
            ).get("players", [])
            if (
                creator_login_pseudo not in creator_final_players
                or joiner_login_pseudo not in creator_final_players
            ):
                print(
                    "ROOM_UPDATE final créateur incomplet:",
                    creator_final_players,
                )
                return 1

            if (
                creator_login_pseudo not in joiner_final_players
                or joiner_login_pseudo not in joiner_final_players
            ):
                print(
                    "ROOM_UPDATE final rejoignant incomplet:",
                    joiner_final_players,
                )
                return 1

            creator_end = creator_reset["messages"].get("END") or {}
            final_room_state = room_state_from_messages(creator_reset["messages"])
            print("END_MATCH_SMOKE_OK")
            print(
                {
                    "room_id": room_id,
                    "room_name": room_name,
                    "state": final_room_state,
                    "winner_text": creator_end.get("winner_text"),
                    "team_a_score": creator_end.get("team_a_score"),
                    "team_b_score": creator_end.get("team_b_score"),
                }
            )
            return 0

        print("START_MATCH_SMOKE_OK")
        print(
            {
                "room_id": room_id,
                "room_name": room_name,
                "state": creator_state,
                "host": creator_login_pseudo,
            }
        )
        return 0
    except OnlineConnectionError as error:
        print(f"Erreur online: {error}")
        return 1
    finally:
        creator.disconnect()
        joiner.disconnect()


def main() -> int:
    from ui.online_client import (
        DEFAULT_ONLINE_HOST,
        DEFAULT_ONLINE_PORT,
        OnlineClient,
        OnlineConnectionError,
    )

    parser = argparse.ArgumentParser(
        description="Teste le lobby online en mode simple ou create-join.",
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "basic",
            "create-join",
            "host-migration",
            "start-match",
            "end-match",
            "mid-match-leave",
        ),
        default="basic",
        help=(
            "basic = HELLO/LOGIN/LIST_ROOMS, "
            "create-join = scénario complet, "
            "host-migration = transfert d'hôte, "
            "start-match = départ réservé à l'hôte, "
            "end-match = attend END puis le retour en lobby, "
            "mid-match-leave = un joueur quitte pendant in_game."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_ONLINE_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_ONLINE_PORT)
    parser.add_argument("--pseudo", default="debug_online")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--match-timeout", type=float, default=12.0)
    parser.add_argument("--max-players", type=int, default=2)
    parser.add_argument("--list-retries", type=int, default=5)
    parser.add_argument("--list-retry-delay", type=float, default=1.0)
    parser.add_argument(
        "--leave-role",
        choices=("host", "joiner"),
        default="host",
        help="Pour mid-match-leave: joueur qui quitte pendant la joute.",
    )
    args = parser.parse_args()

    scenario_args = SimpleNamespace(
        host=args.host,
        port=args.port,
        pseudo=args.pseudo,
        timeout=args.timeout,
        match_timeout=max(args.timeout, args.match_timeout),
        max_players=args.max_players,
        list_retries=max(1, args.list_retries),
        list_retry_delay=max(0.0, args.list_retry_delay),
        leave_role=args.leave_role,
    )

    if args.scenario == "create-join":
        return run_create_join_scenario(
            scenario_args,
            OnlineClient=OnlineClient,
            OnlineConnectionError=OnlineConnectionError,
        )

    if args.scenario == "host-migration":
        return run_host_migration_scenario(
            scenario_args,
            OnlineClient=OnlineClient,
            OnlineConnectionError=OnlineConnectionError,
        )

    if args.scenario == "start-match":
        return run_start_match_scenario(
            scenario_args,
            OnlineClient=OnlineClient,
            OnlineConnectionError=OnlineConnectionError,
        )

    if args.scenario == "end-match":
        return run_end_match_scenario(
            scenario_args,
            OnlineClient=OnlineClient,
            OnlineConnectionError=OnlineConnectionError,
        )

    if args.scenario == "mid-match-leave":
        return run_mid_match_leave_scenario(
            scenario_args,
            OnlineClient=OnlineClient,
            OnlineConnectionError=OnlineConnectionError,
        )

    return run_basic_scenario(
        scenario_args,
        OnlineClient=OnlineClient,
        OnlineConnectionError=OnlineConnectionError,
    )


if __name__ == "__main__":
    raise SystemExit(main())
