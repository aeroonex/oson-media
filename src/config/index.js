require('dotenv').config();

module.exports = {
  BOT_TOKEN: process.env.BOT_TOKEN,
  GENIUS_API_KEY: process.env.GENIUS_API_KEY,
  RESULTS_PER_PAGE: 4,
  MAX_VIDEO_DURATION: 600,
  DOWNLOAD_DIR: require('path').join(__dirname, '../../downloads'),
};
