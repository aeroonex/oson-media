const ytdl = require('ytdl-core');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const { mainKeyboard } = require('../keyboards/main');
const { addDownload } = require('../database/userModel');
const { userSearchCache } = require('./search');

function setupDownloadHandlers(bot) {
  bot.action(/yt_(audio|video)_(\d+)_(\d+)/, async (ctx) => {
    const format = ctx.match[1];
    const page = parseInt(ctx.match[2]);
    const index = parseInt(ctx.match[3]);
    const cache = userSearchCache.get(ctx.from.id);
    if (!cache) return ctx.answerCbQuery('❌ Qidiruv topilmadi. Qayta qidiring.');

    const perPage = config.RESULTS_PER_PAGE;
    const video = cache.results[page * perPage + index];
    if (!video) return ctx.answerCbQuery('❌ Video topilmadi.');

    await ctx.editMessageText(`⏳ ${format === 'audio' ? '🎵 Audio' : '🎬 Video'} yuklanmoqda...\n\n${video.title}`);
    ctx.answerCbQuery();

    try {
      const fileName = `${format}_${Date.now()}.${format === 'audio' ? 'mp3' : 'mp4'}`;
      const filePath = path.join(config.DOWNLOAD_DIR, fileName);

      const options = format === 'audio'
        ? { quality: 'highestaudio', filter: 'audioonly' }
        : { quality: 'highest', filter: 'audioandvideo' };

      const stream = ytdl(video.url, options);
      const writeStream = fs.createWriteStream(filePath);
      stream.pipe(writeStream);

      await new Promise((resolve, reject) => {
        writeStream.on('finish', resolve);
        writeStream.on('error', reject);
        stream.on('error', reject);
      });

      if (format === 'audio') {
        await ctx.replyWithAudio(
          { source: filePath, filename: `${video.title}.mp3` },
          { caption: `🎵 ${video.title}\n⏱ ${video.duration}`, ...mainKeyboard }
        );
      } else {
        await ctx.replyWithVideo(
          { source: filePath },
          { caption: `🎬 ${video.title}\n⏱ ${video.duration}`, ...mainKeyboard }
        );
      }

      addDownload.run({
        user_id: ctx.from.id,
        type: format,
        title: video.title,
        url: video.url,
      });

      fs.unlink(filePath, () => {});
    } catch (err) {
      console.error('Yuklab olish xatosi:', err.message);
      ctx.reply('❌ Yuklab olishda xatolik yuz berdi. Qayta urinib ko\'ring.', mainKeyboard);
    }
  });

  bot.hears('📥 Yuklab olish', (ctx) => {
    ctx.reply(
      '📥 YouTube yoki Instagram havolasini yuboring:\n\n' +
      'Masalan:\n' +
      '▫️ https://youtu.be/xxxxx\n' +
      '▫️ https://www.instagram.com/reel/xxxxx',
      { reply_markup: { force_reply: true } }
    );
  });
}

module.exports = { setupDownloadHandlers };
