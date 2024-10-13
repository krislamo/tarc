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
import sqlite3

from datetime import datetime, timezone

import qbittorrent

# SCHEMA format is YYYYMMDDX
SCHEMA = 202410060


def init_db(conn):
    """
    Initialize database
    """

    c = conn.cursor()
    c.executescript(
        f"""
        PRAGMA user_version = {SCHEMA};

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            uuid TEXT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            last_seen DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS torrents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            info_hash_v1 TEXT NOT NULL UNIQUE,
            info_hash_v2 TEXT UNIQUE,
            file_count INTEGER NOT NULL,
            completed_on DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS torrent_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            torrent_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            content_path TEXT NOT NULL,
            last_seen DATETIME NOT NULL,
            FOREIGN KEY (torrent_id) REFERENCES torrents(id),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            UNIQUE (torrent_id, client_id)
        );

        CREATE TABLE IF NOT EXISTS trackers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            last_seen DATETIME NOT NULL
        );

        CREATE TABLE IF NOT EXISTS torrent_trackers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            torrent_id INTEGER NOT NULL,
            tracker_id INTEGER NOT NULL,
            last_seen DATETIME NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (torrent_id) REFERENCES torrents(id),
            FOREIGN KEY (tracker_id) REFERENCES trackers(id),
            UNIQUE (client_id, torrent_id, tracker_id)
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            size INTEGER NOT NULL,
            oshash TEXT NOT NULL UNIQUE,
            hash TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS torrent_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            torrent_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            file_index INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            is_downloaded BOOLEAN NOT NULL,
            last_checked DATETIME NOT NULL,
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (torrent_id) REFERENCES torrents(id),
            FOREIGN KEY (client_id) REFERENCES clients(id),
            UNIQUE (file_id, torrent_id, client_id, file_index)
        );
        """
    )
    conn.commit()
    c.close()


def list_tables(conn):
    """
    List all tables in database
    """
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    table_list = c.fetchall()
    c.close()
    return [table[0] for table in table_list]


def add_client(conn, name, endpoint, last_seen):
    """
    Add a new client endpoint to database
    """
    c = conn.cursor()
    c.execute(
        f"""
        INSERT INTO clients (uuid, name, endpoint, last_seen)
        VALUES ("{uuid.uuid4()}", "{name}", "{endpoint}", "{last_seen}");
        """
    )
    conn.commit()
    c.close()


def find_client(conn, endpoint):
    """
    Find existing client
    """
    c = conn.cursor()
    c.execute(f'SELECT id, name, uuid FROM clients WHERE endpoint="{endpoint}";')
    response = c.fetchall()
    c.close()
    return response


def list_clients(conn):
    """
    List all stored clients
    """
    c = conn.cursor()
    c.execute("SELECT * FROM clients;")
    rows = c.fetchall()
    c.close()
    return rows


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
            sqlitedb = sqlite3.connect(STORAGE)
            tables = list_tables(sqlitedb)
        except sqlite3.DatabaseError as e:
            print(f'[ERROR]: Database Error "{STORAGE}" ({str(e)})')
            sys.exit(1)
        if len(tables) == 0:
            print(f"[INFO]: Initializing database at {STORAGE}")
            init_db(sqlitedb)
        cursor = sqlitedb.cursor()
        cursor.execute("PRAGMA user_version;")
        SCHEMA_FOUND = cursor.fetchone()[0]
        cursor.close()
        if not SCHEMA == SCHEMA_FOUND:
            print(f"[ERROR]: SCHEMA {SCHEMA_FOUND}, expected {SCHEMA}")
            sys.exit(1)
        if not args.directory is None:
            print("[INFO]: --directory is not implemented")
            sys.exit(0)
        elif not args.endpoint is None:
            qb = qbittorrent.Client(args.endpoint)
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
            clients = find_client(sqlitedb, args.endpoint)
            if args.confirm_add:
                if len(clients) == 0:
                    if not args.name is None:
                        now = datetime.now(timezone.utc).isoformat(
                            sep=" ", timespec="seconds"
                        )
                        add_client(sqlitedb, args.name, args.endpoint, now)
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
