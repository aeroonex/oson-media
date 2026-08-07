const instagramDl = require('instagram-url-direct');
const https = require('https');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const { mainKeyboard } = require('../keyboards/main');
const { addDownload } = require('../database/userModel');

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (response) => {
      if (response.statusCode === 301 || response.statusCode === 302) {
        file.close();
        fs.unlink(dest, () => {});
        return downloadFile(response.headers.location, dest).then(resolve).catch(reject);
      }
      response.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}

async function handleInstagram(ctx, url) {
  const statusMsg = await ctx.reply('⏳ Instagram video yuklanmoqda...');

  try {
    const result = await instagramDl(url);

    if (!result.url_list || result.url_list.length === 0) {
      return ctx.reply('❌ Bu postdan video topilmadi.', mainKeyboard);
    }

    const videoUrl = result.url_list[0];
    const fileName = `ig_${Date.now()}.mp4`;
    const filePath = path.join(config.DOWNLOAD_DIR, fileName);

    await downloadFile(videoUrl, filePath);

    await ctx.replyWithVideo(
      { source: filePath },
      { caption: '📸 Instagram video', ...mainKeyboard }
    );

    addDownload.run({
      user_id: ctx.from.id,
      type: 'video',
      title: 'Instagram video',
      url: url,
    });

    fs.unlink(filePath, () => {});
    ctx.deleteMessage(statusMsg.message_id).catch(() => {});
  } catch (err) {
    console.error('Instagram xatosi:', err.message);
    ctx.reply('❌ Videoni yuklab bo\'lmadi. Havolani tekshiring.', mainKeyboard);
  }
}

module.exports = { handleInstagram };
