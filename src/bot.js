require('dotenv').config();
const { Telegraf } = require('telegraf');
const config = require('./config');
const { mainKeyboard } = require('./keyboards/main');
const { upsertUser, addSearch } = require('./database/userModel');

const { setupStartHandlers } = require('./handlers/start');
const { setupSearchHandlers, searchYouTube, formatResultsPage, userSearchCache } = require('./handlers/search');
const { setupDownloadHandlers } = require('./handlers/download');
const { setupMusicHandlers, musicSearchCache, deezerSearch, formatMusicPage } = require('./handlers/music');
const { setupProfileHandlers } = require('./handlers/profile');
const { handleInstagram } = require('./handlers/instagram');
const { handleYoutubeLink } = require('./handlers/youtube');
const { searchResultButtons } = require('./keyboards/main');

const bot = new Telegraf(config.BOT_TOKEN);

bot.use((ctx, next) => {
  if (ctx.from) {
    upsertUser.run({
      telegram_id: ctx.from.id,
      first_name: ctx.from.first_name || '',
      last_name: ctx.from.last_name || '',
      username: ctx.from.username || '',
    });
  }
  return next();
});

setupStartHandlers(bot);
setupSearchHandlers(bot);
setupDownloadHandlers(bot);
setupMusicHandlers(bot);
setupProfileHandlers(bot);

const buttonTexts = ['🎵 Musiqa qidirish', '🎬 Video qidirish', '📥 Yuklab olish', '👤 Profil', '❓ Yordam', '❌ Bekor qilish'];

bot.on('text', async (ctx) => {
  const text = ctx.message.text;

  if (buttonTexts.includes(text)) return;

  if (text.includes('youtube.com') || text.includes('youtu.be')) {
    return handleYoutubeLink(ctx, text);
  }

  if (text.includes('instagram.com')) {
    return handleInstagram(ctx, text);
  }

  const replyText = ctx.message.reply_to_message?.text || '';

  if (replyText.includes('artist nomini') || replyText.includes('Qo\'shiq')) {
    const statusMsg = await ctx.reply('🔍 Deezer dan qidirilmoqda...');
    try {
      const data = await deezerSearch(text);
      const tracks = data.data || [];
      if (tracks.length === 0) {
        return ctx.reply('😕 Hech narsa topilmadi. Boshqa nom bilan qidiring.', mainKeyboard);
      }
      const { formatDuration } = require('./utils/format');
      const results = tracks.slice(0, 20).map(t => ({
        title: t.title,
        artist: t.artist.name,
        album: t.album.title,
        duration: formatDuration(t.duration),
        preview: t.preview,
      }));
      musicSearchCache.set(ctx.from.id, { results, page: 0, query: text });
      addSearch.run({ user_id: ctx.from.id, query: text, results_count: results.length });

      const { text: msg, pageResults, totalPages } = formatMusicPage(results, 0);
      await ctx.reply(msg, {
        parse_mode: 'MarkdownV2',
        ...searchResultButtons(pageResults, 0, totalPages, 'music'),
      });
      ctx.deleteMessage(statusMsg.message_id).catch(() => {});
    } catch (err) {
      console.error('Musiqa xatosi:', err.message);
      ctx.reply('❌ Xatolik yuz berdi. Qayta urinib ko\'ring.', mainKeyboard);
    }
    return;
  }

  if (replyText.includes('video nomini')) {
    const statusMsg = await ctx.reply('🔍 YouTube dan qidirilmoqda...');
    try {
      const results = await searchYouTube(text);
      if (results.length === 0) {
        return ctx.reply('😕 Hech narsa topilmadi.', mainKeyboard);
      }
      userSearchCache.set(ctx.from.id, { results, page: 0, query: text });
      addSearch.run({ user_id: ctx.from.id, query: text, results_count: results.length });

      const { text: msg, pageResults, totalPages } = formatResultsPage(results, 0);
      await ctx.reply(msg, {
        parse_mode: 'MarkdownV2',
        ...searchResultButtons(pageResults, 0, totalPages, 'yt'),
      });
      ctx.deleteMessage(statusMsg.message_id).catch(() => {});
    } catch (err) {
      console.error('YouTube qidiruv xatosi:', err.message);
      ctx.reply('❌ Xatolik yuz berdi. Qayta urinib ko\'ring.', mainKeyboard);
    }
    return;
  }

  ctx.reply(
    '🤔 Men bu xabarni tushunmadim.\n\nQuyidagi tugmalardan foydalaning yoki havola yuboring 👇',
    mainKeyboard
  );
});

bot.launch();
console.log('🤖 Oson Media Bot v2.0 ishga tushdi!');

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
