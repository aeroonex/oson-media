const db = require('./db');

const upsertUser = db.prepare(`
  INSERT INTO users (telegram_id, first_name, last_name, username)
  VALUES (@telegram_id, @first_name, @last_name, @username)
  ON CONFLICT(telegram_id) DO UPDATE SET
    first_name = @first_name,
    last_name = @last_name,
    username = @username,
    last_active = datetime('now')
`);

const getUser = db.prepare('SELECT * FROM users WHERE telegram_id = ?');
const getAllUsers = db.prepare('SELECT * FROM users ORDER BY created_at DESC');
const getUserCount = db.prepare('SELECT COUNT(*) as count FROM users');

const addDownload = db.prepare(`
  INSERT INTO downloads (user_id, type, title, url)
  VALUES (@user_id, @type, @title, @url)
`);

const getUserDownloads = db.prepare(`
  SELECT * FROM downloads WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
`);

const getDownloadCount = db.prepare('SELECT COUNT(*) as count FROM downloads WHERE user_id = ?');
const getTotalDownloads = db.prepare('SELECT COUNT(*) as count FROM downloads');

const addSearch = db.prepare(`
  INSERT INTO searches (user_id, query, results_count)
  VALUES (@user_id, @query, @results_count)
`);

const getUserSearches = db.prepare(`
  SELECT * FROM searches WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
`);

module.exports = {
  upsertUser,
  getUser,
  getAllUsers,
  getUserCount,
  addDownload,
  getUserDownloads,
  getDownloadCount,
  getTotalDownloads,
  addSearch,
  getUserSearches,
};
