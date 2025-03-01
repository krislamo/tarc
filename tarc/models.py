#!/usr/bin/env python3
"""
Database models for Torrent Archiver
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Client(Base):
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    uuid = Column(String, nullable=False, unique=True)
    endpoint = Column(String, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    
    torrent_clients = relationship("TorrentClient", back_populates="client")
    torrent_trackers = relationship("TorrentTracker", back_populates="client")
    torrent_files = relationship("TorrentFile", back_populates="client")


class Torrent(Base):
    __tablename__ = 'torrents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    info_hash_v1 = Column(String, nullable=False, unique=True)
    info_hash_v2 = Column(String, unique=True)
    file_count = Column(Integer, nullable=False)
    completed_on = Column(DateTime, nullable=False)
    
    torrent_clients = relationship("TorrentClient", back_populates="torrent")
    torrent_trackers = relationship("TorrentTracker", back_populates="torrent")
    torrent_files = relationship("TorrentFile", back_populates="torrent")


class TorrentClient(Base):
    __tablename__ = 'torrent_clients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    torrent_id = Column(Integer, ForeignKey('torrents.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    name = Column(String, nullable=False)
    content_path = Column(String, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    
    torrent = relationship("Torrent", back_populates="torrent_clients")
    client = relationship("Client", back_populates="torrent_clients")
    
    __table_args__ = (UniqueConstraint('torrent_id', 'client_id'),)


class Tracker(Base):
    __tablename__ = 'trackers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False, unique=True)
    last_seen = Column(DateTime, nullable=False)
    
    torrent_trackers = relationship("TorrentTracker", back_populates="tracker")


class TorrentTracker(Base):
    __tablename__ = 'torrent_trackers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    torrent_id = Column(Integer, ForeignKey('torrents.id'), nullable=False)
    tracker_id = Column(Integer, ForeignKey('trackers.id'), nullable=False)
    last_seen = Column(DateTime, nullable=False)
    
    client = relationship("Client", back_populates="torrent_trackers")
    torrent = relationship("Torrent", back_populates="torrent_trackers")
    tracker = relationship("Tracker", back_populates="torrent_trackers")
    
    __table_args__ = (UniqueConstraint('client_id', 'torrent_id', 'tracker_id'),)


class File(Base):
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    size = Column(Integer, nullable=False)
    oshash = Column(String, nullable=False, unique=True)
    hash = Column(String, unique=True)
    
    torrent_files = relationship("TorrentFile", back_populates="file")


class TorrentFile(Base):
    __tablename__ = 'torrent_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    torrent_id = Column(Integer, ForeignKey('torrents.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    file_index = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    is_downloaded = Column(Boolean, nullable=False)
    last_checked = Column(DateTime, nullable=False)
    
    file = relationship("File", back_populates="torrent_files")
    torrent = relationship("Torrent", back_populates="torrent_files")
    client = relationship("Client", back_populates="torrent_files")
    
    __table_args__ = (UniqueConstraint('file_id', 'torrent_id', 'client_id', 'file_index'),) 