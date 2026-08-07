const YouTube = require('youtube-sr').default;
const { searchResultButtons, downloadTypeButtons, mainKeyboard } = require('../keyboards/main');
const { formatDuration } = require('../utils/format');
const { addSearch } = require('../database/userModel');
const config = require('../config');

const userSearchCache = new Map();

async function searchYouTube(query) {
  const results = await YouTube.search(query, { limit: 20, type: 'video' });
  return results.map(v => ({
    id: v.id,
    title: v.title,
    duration: v.duration ? formatDuration(Math.floor(v.duration / 1000)) : '0:00',
    durationSec: v.duration ? Math.floor(v.duration / 1000) : 0,
    channel: v.channel?.name || 'Noma\'lum',
    url: `https://www.youtube.com/watch?v=${v.id}`,
    thumbnail: v.thumbnail?.url || '',
  }));
}

function formatResultsPage(results, page) {
  const perPage = config.RESULTS_PER_PAGE;
  const pageResults = results.slice(page * perPage, (page + 1) * perPage);
  const totalPages = Math.ceil(results.length / perPage);

  let text = '🔍 *Natijalar:*\n\n';
  pageResults.forEach((r, i) => {
    const num = page * perPage + i + 1;
    text += `*${num}\\.* ${r.title.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}\n`;
    text += `⏱ ${r.duration}  📺 ${r.channel.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}\n\n`;
  });
  text += `📄 Sahifa ${page + 1}/${totalPages}`;

  return { text, pageResults, totalPages };
}

function setupSearchHandlers(bot) {
  bot.hears('🎬 Video qidirish', (ctx) => {
    ctx.reply('🔍 Qidirmoqchi bo\'lgan video nomini yozing:', {
      reply_markup: { force_reply: true },
    });
  });

  bot.action(/yt_page_(\d+)/, async (ctx) => {
    const page = parseInt(ctx.match[1]);
    const cache = userSearchCache.get(ctx.from.id);
    if (!cache) return ctx.answerCbQuery('❌ Qidiruv topilmadi. Qayta qidiring.');

    const { text, pageResults, totalPages } = formatResultsPage(cache.results, page);
    cache.page = page;

    await ctx.editMessageText(text, {
      parse_mode: 'MarkdownV2',
      ...searchResultButtons(pageResults, page, totalPages, 'yt'),
    });
    ctx.answerCbQuery();
  });

  bot.action(/yt_select_(\d+)_(\d+)/, async (ctx) => {
    const page = parseInt(ctx.match[1]);
    const index = parseInt(ctx.match[2]);
    const cache = userSearchCache.get(ctx.from.id);
    if (!cache) return ctx.answerCbQuery('❌ Qidiruv topilmadi.');

    const perPage = config.RESULTS_PER_PAGE;
    const video = cache.results[page * perPage + index];
    if (!video) return ctx.answerCbQuery('❌ Video topilmadi.');

    const title = video.title.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
    await ctx.editMessageText(
      `🎬 *${title}*\n⏱ ${video.duration}  📺 ${video.channel.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}\n\nQanday yuklab olmoqchisiz?`,
      { parse_mode: 'MarkdownV2', ...downloadTypeButtons(index, page) }
    );
    ctx.answerCbQuery();
  });

  bot.action('yt_cancel', async (ctx) => {
    userSearchCache.delete(ctx.from.id);
    await ctx.editMessageText('❌ Qidiruv bekor qilindi.');
    ctx.answerCbQuery();
  });

  return { searchYouTube, formatResultsPage, userSearchCache };
}

module.exports = { setupSearchHandlers, searchYouTube, formatResultsPage, userSearchCache };
