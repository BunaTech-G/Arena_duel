from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


MANIFEST_HASH_FIELD = "windows_installer_sha256"
HASH_CHUNK_SIZE = 1024 * 1024


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as file_handle:
        manifest_data = json.load(file_handle)

    if not isinstance(manifest_data, dict):
        raise ValueError("Le manifest doit etre un objet JSON.")

    return manifest_data


def update_manifest_installer_hash(
    manifest_path: Path,
    installer_path: Path,
    *,
    field_name: str = MANIFEST_HASH_FIELD,
) -> str:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest introuvable: {manifest_path}")

    if not installer_path.is_file():
        raise FileNotFoundError(f"Installateur introuvable: {installer_path}")

    manifest_data = load_manifest(manifest_path)
    installer_hash = compute_sha256(installer_path)
    manifest_data[field_name] = installer_hash

    with open(manifest_path, "w", encoding="utf-8") as file_handle:
        json.dump(manifest_data, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")

    return installer_hash


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Met a jour le hash de l installateur Windows dans version.json."),
    )
    parser.add_argument(
        "manifest_path",
        help="Chemin du manifest JSON a mettre a jour.",
    )
    parser.add_argument(
        "installer_path",
        help="Chemin du setup Windows dont il faut calculer le SHA-256.",
    )
    parser.add_argument(
        "--field-name",
        default=MANIFEST_HASH_FIELD,
        help="Nom du champ JSON a mettre a jour.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        installer_hash = update_manifest_installer_hash(
            Path(args.manifest_path),
            Path(args.installer_path),
            field_name=args.field_name,
        )
    except (
        FileNotFoundError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"[ERREUR] {exc}")
        return 1

    print(installer_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
