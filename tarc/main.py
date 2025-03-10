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
from sqlalchemy.exc import DatabaseError

from .models import Base, SchemaVersion, Client

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


def find_client(engine, endpoint):
    """
    Find existing client
    """
    with Session(engine) as session:
        clients = (
            session.query(Client.id, Client.name, Client.uuid)
            .filter_by(endpoint=endpoint)
            .all()
        )
        return clients


def list_clients(engine):
    """
    List all stored clients
    """
    with Session(engine) as session:
        return session.query(Client).all()


def main():
    """
    Entrypoint of the program.
    """

    parser = argparse.ArgumentParser(description="Manage BT archives", prog="tarc")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    scan_parser = subparsers.add_parser("scan", help="Scan command")
    scan_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    scan_parser.add_argument(
        "--confirm-add", action="store_true", help="Confirm adding a new client"
    )
    scan_parser.add_argument("-n", "--name", help="Name of client")
    scan_parser.add_argument("-d", "--directory", help="Directory to scan")
    scan_parser.add_argument("-t", "--type", help="Scan type")
    scan_parser.add_argument("-e", "--endpoint", help="Endpoint URL")
    scan_parser.add_argument("-u", "--username", help="Username")
    scan_parser.add_argument("-p", "--password", help="Password")
    scan_parser.add_argument("-s", "--storage", help="Path of sqlite3 database")

    args = parser.parse_args()

    if args.command == "scan":
        if args.storage is None:
            storage_path = os.path.expanduser("~/.tarc.db")
        else:
            storage_path = args.storage

        try:
            engine = create_engine(f"sqlite:///{storage_path}")
            tables = list_tables(engine)
        except DatabaseError as e:
            print(f'[ERROR]: Database Error "{storage_path}" ({str(e)})')
            sys.exit(1)

        if not tables:
            print(f"[INFO]: Initializing database at {storage_path}")
            init_db(engine)

        schema_found = get_schema_version(engine)
        if schema_found is None:
            print("[ERROR]: Could not determine schema version")
            sys.exit(1)
        if not SCHEMA == schema_found:
            print(f"[ERROR]: SCHEMA {schema_found}, expected {SCHEMA}")
            sys.exit(1)

        if args.directory is not None:
            print("[INFO]: --directory is not implemented")
            sys.exit(0)
        elif args.endpoint is not None:
            qb = qbittorrentapi.Client(host=args.endpoint,
                                       username=args.username, password=args.password)
            try:
                qb.auth_log_in()
            except qbittorrentapi.LoginFailed as e:
                print(f'[ERROR]: Login failed for endpoint "{args.endpoint}": {e}')
                sys.exit(1)
            if not re.match(r"^v?\d+(\.\d+)*$", qb.app.version):
                print(f'[ERROR]: Invalid version "{qb.app.version}" found at "{args.endpoint}"')
                sys.exit(1)
            else:
                print(f'[INFO]: Found qBittorrent {qb.app.version} at "{args.endpoint}"')

            clients = find_client(engine, args.endpoint)
            if args.confirm_add:
                if len(clients) == 0:
                    if args.name is not None:
                        now = datetime.now(timezone.utc)
                        add_client(engine, args.name, args.endpoint, now)
                        print(f"[INFO]: Added client {args.name} ({args.endpoint})")
                    else:
                        print("[ERROR]: Must specify --name for a new client")
                        sys.exit(1)
                elif len(clients) == 1:
                    print(f"[ERROR]: {clients[0][1]} ({clients[0][2]}) already exists")
                    sys.exit(1)
                else:
                    print(
                        f"[ERROR]: Multiple clients with the same endpoint: {args.endpoint}"
                    )
                    sys.exit(1)
            elif len(clients) == 0:
                print(f'[ERROR]: Client using endpoint "{args.endpoint}" not found')
                print("[ERROR]: Use --confirm-add to add a new endpoint")
                sys.exit(1)
            elif len(clients) == 1:
                torrents = qb.torrents_info()
                print(f"[INFO]: There are {len(torrents)} torrents\n")
                for torrent in torrents[:2]:
                    files = qb.torrents_files(torrent.hash)
                    trackers = qb.torrents_trackers(torrent.hash)
                    print(f"[name]: {torrent.name}")
                    print(f"[infohash_v1]: {torrent.hash}")
                    print(f"[content_path]: {torrent.content_path}")
                    print(f"[magnet_uri]: {torrent.magnet_uri[:80]}")
                    print(f"[completed_on]: {torrent.completed}\n")
                    print(f"[trackers]: {len(trackers)}")
                    print(f"[file_count]: {len(files)}\n")
                    if args.debug:
                        print(f"[DEBUG]: {repr(torrent)}")
                        for elem in trackers:
                            print(f"[DEBUG]: Tracker {repr(elem)}")
                        print("\n", end="")
            else:
                print(
                    f'[ERROR]: Multiple clients ({len(clients)}) using "{args.endpoint}"'
                )
                sys.exit(1)
        else:
            print("[ERROR]: Must specify directory OR client endpoint")
            sys.exit(1)


if __name__ == "__main__":
    main()
