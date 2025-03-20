#!/usr/bin/env python3
"""
Torrent Archiver

Provides functionality for managing datasets distributed through BitTorrent.
It tracks files and reconciles hardlinks between download directories and
archival locations.

"""

import os
import sys
import re
import uuid
import argparse
from datetime import datetime, timezone

import qbittorrentapi
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from .models import Base, SchemaVersion, Client, Torrent, TorrentFile

# SCHEMA format is YYYYMMDDX
SCHEMA = 202503100


def init_db(engine):
    """
    Initialize database
    """
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        if not session.query(SchemaVersion).first():
            now = datetime.now(timezone.utc)
            version = SchemaVersion(version=SCHEMA, applied_at=now)
            session.add(version)
            session.commit()


def get_schema_version(engine):
    """
    Get current schema version from database
    """
    with Session(engine) as session:
        version = session.query(SchemaVersion).order_by(SchemaVersion.id.desc()).first()
        return version.version if version else None


def list_tables(engine):
    """
    List all tables in database
    """
    inspector = inspect(engine)
    return inspector.get_table_names()


def add_client(engine, name, endpoint, last_seen):
    """
    Add a new client endpoint to database
    """
    with Session(engine) as session:
        client = Client(
            uuid=str(uuid.uuid4()), name=name, endpoint=endpoint, last_seen=last_seen
        )
        session.add(client)
        session.commit()


def find_client(engine, name):
    """
    Find existing client
    """
    with Session(engine) as session:
        clients = session.query(Client).filter_by(name=name).all()
        return clients


def list_clients(engine):
    """
    List all stored clients
    """
    with Session(engine) as session:
        return session.query(Client).all()


def auth_qbittorrent(endpoint, username, password):
    """
    Authenticate with the qBittorrent client
    """
    qb = qbittorrentapi.Client(host=endpoint, username=username, password=password)
    try:
        qb.auth_log_in()
    except qbittorrentapi.LoginFailed as e:
        raise ValueError(f'Login failed for endpoint "{endpoint}"') from e
    except Exception as e:
        raise ValueError(f"An unexpected error occurred: {str(e)}") from e
    if not re.match(r"^v?\d+(\.\d+)*$", qb.app.version):
        raise ValueError(f'Invalid version "{qb.app.version}" found at "{endpoint}"')
    return qb


def scan_torrents(qb_client, engine):
    """
    Scan torrents using the provided qBittorrent client.
    """
    torrents = qb_client.torrents_info()

    with Session(engine) as session:
        for torrent in torrents:
            files = qb_client.torrents_files(torrent.hash)
            torrent_instance = (
                session.query(Torrent).filter_by(info_hash_v1=torrent.hash).first()
            )
            if not torrent_instance:
                completed_on = (
                    datetime.fromtimestamp(torrent.completed)
                    if torrent.completed
                    else None
                )
                torrent_instance = Torrent(
                    info_hash_v1=torrent.hash,
                    file_count=len(files),
                    completed_on=completed_on,
                )
                session.add(torrent_instance)
                session.commit()
                torrent_instance = (
                    session.query(Torrent).filter_by(info_hash_v1=torrent.hash).first()
                )
                if not torrent_instance:
                    print(f"[ERROR]: Can't find just added torrent {torrent.name}")
                    raise ValueError(f"Can't find {torrent.hash}")

            file_counter = 0
            for file in files:
                if (
                    not session.query(TorrentFile)
                    .filter_by(file_path=file.name)
                    .first()
                ):
                    torrent_file_instance = TorrentFile(
                        torrent_id=torrent_instance.id,
                        file_id=file.id,
                        client_id=1,
                        file_index=file.index,
                        file_path=file.name,
                        is_downloaded=file.progress == 1,
                        last_checked=datetime.now(timezone.utc),
                    )
                    session.add(torrent_file_instance)
                    file_counter += 1
            session.commit()
            if file_counter > 0:
                print(torrent.hash)
            else:
                print(f"[CHECKED]: {torrent.name}")


def scan(args, engine):
    """
    Scan command to authenticate with the qBittorrent client and scan torrents.
    """
    if args.name:
        clients = find_client(engine, args.name)
        if len(clients) == 1:
            client_info = clients[0]
            qb_client = auth_qbittorrent(
                client_info.endpoint, args.username, args.password
            )
            scan_torrents(qb_client, engine)
        elif len(clients) == 0:
            raise ValueError(
                f'Client with name "{args.name}" not found. '
                "Please use the 'client add' command to add a new client."
            )
        else:
            raise ValueError(f"Multiple clients with the same name: {args.name}")
    elif args.directory:
        print("[INFO]: --directory is not implemented")
    else:
        raise ValueError("Must specify directory OR client name")


def client_add(args, engine):
    """
    Add a new client to the database.
    """
    if args.name and args.endpoint and args.username:
        now = datetime.now(timezone.utc)
        add_client(engine, args.name, args.endpoint, now)
        print(f"[INFO]: Added client {args.name} ({args.endpoint})")
    else:
        raise ValueError(
            "Must specify --name, --endpoint, and --username to add a client"
        )


def client_list(engine):
    """
    List all stored clients.
    """
    clients = list_clients(engine)
    for client in clients:
        print(f"NAME: {client.name}")
        print(f"ENDPOINT: {client.endpoint}")
        print(f"SEEN: {client.last_seen}")
        print()


def main():
    """
    Parses command-line arguments and executes the corresponding command.
    """
    parser = argparse.ArgumentParser(description="Manage BT archives", prog="tarc")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan command")
    scan_parser.add_argument("-n", "--name", help="Name of client")
    scan_parser.add_argument("-d", "--directory", help="Directory to scan")
    scan_parser.add_argument("-u", "--username", required=True, help="Username")
    scan_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    scan_parser.add_argument(
        "-p", "--password", required=True, help="Password authentication"
    )

    # client command
    client_parser = subparsers.add_parser("client", help="Manage clients")
    client_subparsers = client_parser.add_subparsers(
        dest="client_command", required=True
    )

    # client add command
    client_add_parser = client_subparsers.add_parser("add", help="Add a new client")
    client_add_parser.add_argument("-n", "--name", required=True, help="Name of client")
    client_add_parser.add_argument("-u", "--username", required=True, help="Username")
    client_add_parser.add_argument(
        "-e", "--endpoint", required=True, help="Endpoint URL"
    )

    # client list command
    client_subparsers.add_parser("list", help="List all clients")

    args = parser.parse_args()

    # Check for valid subcommand for client
    if args.command == "client" and args.client_command is None:
        parser.error("The 'client' command requires a subcommand (add or list).")

    storage_path = os.path.expanduser("~/.tarc.db")
    engine = create_engine(f"sqlite:///{storage_path}")

    if not list_tables(engine):
        print(f"[INFO]: Initializing database at {storage_path}")
        init_db(engine)

    schema_found = get_schema_version(engine)
    if schema_found != SCHEMA:
        raise ValueError(f"SCHEMA {schema_found}, expected {SCHEMA}")

    try:
        if args.command == "scan":
            scan(args, engine)
        elif args.command == "client" and args.client_command == "add":
            client_add(args, engine)
        elif args.command == "client" and args.client_command == "list":
            client_list(engine)
    except ValueError as e:
        print(f"[ERROR]: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
