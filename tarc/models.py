"""SQLAlchemy models for the tarc database."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SchemaVersion(Base):  # pylint: disable=too-few-public-methods
    """Database schema version tracking."""

    __tablename__ = "schema_version"
    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False)
    applied_at = Column(DateTime, nullable=False)


class Client(Base):  # pylint: disable=too-few-public-methods
    """BitTorrent client instance."""

    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    uuid = Column(String, nullable=False, unique=True)
    endpoint = Column(String, nullable=False)
    last_seen = Column(DateTime, nullable=False)


class Torrent(Base):  # pylint: disable=too-few-public-methods
    """BitTorrent metadata."""

    __tablename__ = "torrents"
    id = Column(Integer, primary_key=True)
    info_hash_v1 = Column(String, nullable=False, unique=True)
    info_hash_v2 = Column(String, unique=True)
    file_count = Column(Integer, nullable=False)
    completed_on = Column(DateTime, nullable=False)


class TorrentClient(Base):  # pylint: disable=too-few-public-methods
    """Association between torrents and clients."""

    __tablename__ = "torrent_clients"
    id = Column(Integer, primary_key=True)
    torrent_id = Column(Integer, ForeignKey("torrents.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String, nullable=False)
    content_path = Column(String, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("torrent_id", "client_id"),)


class Tracker(Base):  # pylint: disable=too-few-public-methods
    """BitTorrent tracker information."""

    __tablename__ = "trackers"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False, unique=True)
    last_seen = Column(DateTime, nullable=False)


class TorrentTracker(Base):  # pylint: disable=too-few-public-methods
    """Association between torrents and trackers."""

    __tablename__ = "torrent_trackers"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    torrent_id = Column(Integer, ForeignKey("torrents.id"), nullable=False)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    last_seen = Column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("client_id", "torrent_id", "tracker_id"),)


class File(Base):  # pylint: disable=too-few-public-methods
    """File metadata and hashes."""

    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    size = Column(Integer, nullable=False)
    oshash = Column(String, nullable=False, unique=True)
    hash = Column(String, unique=True)


class TorrentFile(Base):  # pylint: disable=too-few-public-methods
    """Association between torrents and files."""

    __tablename__ = "torrent_files"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    torrent_id = Column(Integer, ForeignKey("torrents.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    file_index = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    is_downloaded = Column(Boolean, nullable=False)
    last_checked = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("file_id", "torrent_id", "client_id", "file_index"),
    )
