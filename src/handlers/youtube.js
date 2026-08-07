const ytdl = require('ytdl-core');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const { mainKeyboard } = require('../keyboards/main');
const { addDownload } = require('../database/userModel');

async function handleYoutubeLink(ctx, url) {
  const statusMsg = await ctx.reply('⏳ YouTube video yuklanmoqda...');

  try {
    const info = await ytdl.getInfo(url);
    const title = info.videoDetails.title;
    const duration = parseInt(info.videoDetails.lengthSeconds);

    if (duration > config.MAX_VIDEO_DURATION) {
      return ctx.reply('⚠️ Video 10 daqiqadan uzun. Qisqaroq video yuboring.', mainKeyboard);
    }

    const fileName = `yt_${Date.now()}.mp4`;
    const filePath = path.join(config.DOWNLOAD_DIR, fileName);

    const stream = ytdl(url, { quality: 'highest', filter: 'audioandvideo' });
    const writeStream = fs.createWriteStream(filePath);
    stream.pipe(writeStream);

    await new Promise((resolve, reject) => {
      writeStream.on('finish', resolve);
      writeStream.on('error', reject);
      stream.on('error', reject);
    });

    await ctx.replyWithVideo(
      { source: filePath },
      { caption: `🎬 ${title}`, ...mainKeyboard }
    );

    addDownload.run({
      user_id: ctx.from.id,
      type: 'video',
      title: title,
      url: url,
    });

    fs.unlink(filePath, () => {});
    ctx.deleteMessage(statusMsg.message_id).catch(() => {});
  } catch (err) {
    console.error('YouTube xatosi:', err.message);
    ctx.reply('❌ Videoni yuklab bo\'lmadi. Havolani tekshiring.', mainKeyboard);
  }
}

module.exports = { handleYoutubeLink };
