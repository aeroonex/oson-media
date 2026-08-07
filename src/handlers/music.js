const https = require('https');
const ytdl = require('ytdl-core');
const YouTube = require('youtube-sr').default;
const fs = require('fs');
const path = require('path');
const { searchResultButtons, mainKeyboard } = require('../keyboards/main');
const { addSearch, addDownload } = require('../database/userModel');
const config = require('../config');
const { formatDuration } = require('../utils/format');

function deezerSearch(query) {
  return new Promise((resolve, reject) => {
    const url = `https://api.deezer.com/search?q=${encodeURIComponent(query)}&limit=20`;
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

function formatMusicPage(results, page) {
  const perPage = config.RESULTS_PER_PAGE;
  const pageResults = results.slice(page * perPage, (page + 1) * perPage);
  const totalPages = Math.ceil(results.length / perPage);

  let text = '🎵 *Natijalar:*\n\n';
  pageResults.forEach((r, i) => {
    const num = page * perPage + i + 1;
    const title = r.title.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
    const artist = r.artist.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
    text += `*${num}\\.* ${title}\n`;
    text += `🎤 ${artist}  ⏱ ${r.duration}\n\n`;
  });
  text += `📄 Sahifa ${page + 1}/${totalPages}`;

  return { text, pageResults, totalPages };
}

const musicSearchCache = new Map();

function setupMusicHandlers(bot) {
  bot.hears('🎵 Musiqa qidirish', (ctx) => {
    ctx.reply('🎵 Qo\'shiq yoki artist nomini yozing:\n\nMasalan: *Otajonov* yoki *Timeless*', {
      parse_mode: 'Markdown',
      reply_markup: { force_reply: true },
    });
  });

  bot.action(/music_page_(\d+)/, async (ctx) => {
    const page = parseInt(ctx.match[1]);
    const cache = musicSearchCache.get(ctx.from.id);
    if (!cache) return ctx.answerCbQuery('❌ Qidiruv topilmadi.');

    const { text, pageResults, totalPages } = formatMusicPage(cache.results, page);
    cache.page = page;

    await ctx.editMessageText(text, {
      parse_mode: 'MarkdownV2',
      ...searchResultButtons(pageResults, page, totalPages, 'music'),
    });
    ctx.answerCbQuery();
  });

  bot.action(/music_select_(\d+)_(\d+)/, async (ctx) => {
    const page = parseInt(ctx.match[1]);
    const index = parseInt(ctx.match[2]);
    const cache = musicSearchCache.get(ctx.from.id);
    if (!cache) return ctx.answerCbQuery('❌ Qidiruv topilmadi.');

    const perPage = config.RESULTS_PER_PAGE;
    const song = cache.results[page * perPage + index];
    if (!song) return ctx.answerCbQuery('❌ Qo\'shiq topilmadi.');

    const esc = (s) => s.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
    await ctx.editMessageText(
      `⏳ 🎵 *${esc(song.title)}*\n🎤 ${esc(song.artist)}\n\nYuklanmoqda\\.\\.\\.`,
      { parse_mode: 'MarkdownV2' }
    );
    ctx.answerCbQuery();

    try {
      const query = `${song.title} ${song.artist}`;
      const videos = await YouTube.search(query, { limit: 1, type: 'video' });

      if (!videos.length) {
        return ctx.editMessageText('❌ Audio topilmadi. Boshqa qo\'shiqni tanlang.');
      }

      const video = videos[0];
      const videoUrl = `https://www.youtube.com/watch?v=${video.id}`;
      const fileName = `music_${Date.now()}.mp3`;
      const filePath = path.join(config.DOWNLOAD_DIR, fileName);

      const stream = ytdl(videoUrl, { quality: 'highestaudio', filter: 'audioonly' });
      const writeStream = fs.createWriteStream(filePath);
      stream.pipe(writeStream);

      await new Promise((resolve, reject) => {
        writeStream.on('finish', resolve);
        writeStream.on('error', reject);
        stream.on('error', reject);
      });

      await ctx.replyWithAudio(
        { source: filePath, filename: `${song.title} - ${song.artist}.mp3` },
        {
          title: song.title,
          performer: song.artist,
          caption: `🎵 ${song.title}\n🎤 ${song.artist}\n💽 ${song.album}`,
          ...mainKeyboard,
        }
      );

      addDownload.run({
        user_id: ctx.from.id,
        type: 'audio',
        title: `${song.title} - ${song.artist}`,
        url: videoUrl,
      });

      ctx.deleteMessage().catch(() => {});
      fs.unlink(filePath, () => {});
    } catch (err) {
      console.error('Musiqa yuklab olish xatosi:', err.message);
      ctx.reply('❌ Audio yuklab olishda xatolik. Qayta urinib ko\'ring.', mainKeyboard);
    }
  });

  bot.action('music_cancel', async (ctx) => {
    musicSearchCache.delete(ctx.from.id);
    await ctx.editMessageText('❌ Qidiruv bekor qilindi.');
    ctx.answerCbQuery();
  });
}

module.exports = { setupMusicHandlers, musicSearchCache, deezerSearch, formatMusicPage };
