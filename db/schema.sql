-- schema.sql

CREATE TABLE customers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT
);

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE,
  password_hash TEXT,
  role TEXT,
  customer_id INTEGER
);

CREATE TABLE cameras (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  rtsp TEXT,
  customer_id INTEGER
);

CREATE TABLE user_cameras (
  user_id INTEGER,
  camera_id INTEGER
);
