const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, '../../data/oson_media.db'));

db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    language TEXT DEFAULT 'uz',
    created_at TEXT DEFAULT (datetime('now')),
    last_active TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT,
    url TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
  );

  CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
  );
`);

module.exports = db;
