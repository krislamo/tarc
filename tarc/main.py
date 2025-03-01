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

import qbittorrent
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .models import Base, Client

# SCHEMA format is YYYYMMDDX
SCHEMA = 202410060

def init_db(engine):
    """
    Initialize database
    """
    # Create all tables first
    Base.metadata.create_all(engine)
    
    # Set the schema version using SQLAlchemy primitives
    @event.listens_for(engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA user_version = {SCHEMA}")
        cursor.close()


def list_tables(engine):
    """
    List all tables in database
    """
    return Base.metadata.tables.keys()


def add_client(session, name, endpoint, last_seen):
    """
    Add a new client endpoint to database
    """
    new_client = Client(
        uuid=str(uuid.uuid4()),
        name=name,
        endpoint=endpoint,
        last_seen=last_seen
    )
    session.add(new_client)
    session.commit()


def find_client(session, endpoint):
    """
    Find existing client
    """
    clients = session.query(Client.id, Client.name, Client.uuid).filter(Client.endpoint == endpoint).all()
    return clients


def list_clients(session):
    """
    List all stored clients
    """
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
            STORAGE = os.path.expanduser("~/.tarch.db")
        else:
            STORAGE = args.storage
        try:
            engine = create_engine(f"sqlite:///{STORAGE}")
            tables = list_tables(engine)
            Session = sessionmaker(bind=engine)
            session = Session()
        except Exception as e:
            print(f'[ERROR]: Database Error "{STORAGE}" ({str(e)})')
            sys.exit(1)
        if len(tables) == 0:
            print(f"[INFO]: Initializing database at {STORAGE}")
            init_db(engine)

        # Check schema version using SQLAlchemy primitives
        schema_found = None
        
        @event.listens_for(engine, 'connect')
        def get_sqlite_pragma(dbapi_connection, connection_record):
            nonlocal schema_found
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA user_version")
            schema_found = cursor.fetchone()[0]
            cursor.close()
        
        # Force a connection to trigger the event
        with engine.connect() as conn:
            pass
        
        if not SCHEMA == schema_found:
            print(f"[ERROR]: SCHEMA {schema_found}, expected {SCHEMA}")
            sys.exit(1)
        if not args.directory is None:
            print("[INFO]: --directory is not implemented")
            sys.exit(0)
        elif not args.endpoint is None:
            qb = qbittorrent.Client(args.endpoint)
            if args.username and args.password:
                qb.login(args.username, args.password)
            if qb.qbittorrent_version is None:
                print(f'[ERROR]: Couldn\'t find client version at "{args.endpoint}"')
                sys.exit(1)
            elif not re.match(r"^v?\d+(\.\d+)*$", qb.qbittorrent_version):
                print(f'[ERROR]: Invalid version found at "{args.endpoint}"')
                if args.debug:
                    print(f"[DEBUG]: {qb.qbittorrent_version}")
                sys.exit(1)
            else:
                print(
                    f'[INFO]: Found qbittorrent {qb.qbittorrent_version} at "{args.endpoint}"'
                )
            clients = find_client(session, args.endpoint)
            if args.confirm_add:
                if len(clients) == 0:
                    if not args.name is None:
                        now = datetime.now(timezone.utc)
                        add_client(session, args.name, args.endpoint, now)
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
                torrents = qb.torrents()
                print(f"[INFO]: There are {len(torrents)} torrents\n")
                
                for torrent in torrents[:2]:
                    files = qb.get_torrent_files(torrent["hash"])
                    trackers = qb.get_torrent_trackers(torrent["hash"])
                    print(f"[name]: {torrent['name']}")
                    print(f"[infohash_v1]: {torrent['infohash_v1']}")
                    print(f"[content_path]: {torrent['content_path']}")
                    print(f"[magent_uri]: {torrent['magnet_uri'][0:80]}")
                    print(f"[completed_on]: {torrent['completed']}")
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
