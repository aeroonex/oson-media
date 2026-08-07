const { getUser, getDownloadCount, getUserDownloads, getUserSearches } = require('../database/userModel');
const { mainKeyboard } = require('../keyboards/main');
const { Markup } = require('telegraf');

function setupProfileHandlers(bot) {
  bot.hears('👤 Profil', (ctx) => {
    const user = getUser.get(ctx.from.id);
    if (!user) {
      return ctx.reply('❌ Profil topilmadi. /start bosing.', mainKeyboard);
    }

    const downloads = getDownloadCount.get(ctx.from.id);
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ');

    ctx.reply(
      `👤 *Profil*\n\n` +
      `📛 Ism: *${name.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}*\n` +
      `🆔 ID: \`${user.telegram_id}\`\n` +
      `${user.username ? `👤 Username: @${user.username}\n` : ''}` +
      `📅 Ro'yxatdan o'tgan: ${user.created_at.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}\n` +
      `📥 Jami yuklanmalar: *${downloads.count}*\n`,
      {
        parse_mode: 'MarkdownV2',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📥 Yuklanmalar tarixi', 'profile_downloads')],
          [Markup.button.callback('🔍 Qidiruvlar tarixi', 'profile_searches')],
        ]),
      }
    );
  });

  bot.action('profile_downloads', (ctx) => {
    const downloads = getUserDownloads.all(ctx.from.id);
    if (downloads.length === 0) {
      ctx.answerCbQuery('Hali yuklanmalar yo\'q');
      return;
    }

    let text = '📥 *Oxirgi yuklanmalar:*\n\n';
    downloads.slice(0, 10).forEach((d, i) => {
      const icon = d.type === 'audio' ? '🎵' : '🎬';
      const title = (d.title || 'Nomsiz').replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
      text += `${i + 1}\\. ${icon} ${title}\n`;
    });

    ctx.editMessageText(text, {
      parse_mode: 'MarkdownV2',
      ...Markup.inlineKeyboard([[Markup.button.callback('⬅️ Orqaga', 'profile_back')]]),
    });
    ctx.answerCbQuery();
  });

  bot.action('profile_searches', (ctx) => {
    const searches = getUserSearches.all(ctx.from.id);
    if (searches.length === 0) {
      ctx.answerCbQuery('Hali qidiruvlar yo\'q');
      return;
    }

    let text = '🔍 *Oxirgi qidiruvlar:*\n\n';
    searches.slice(0, 10).forEach((s, i) => {
      const query = s.query.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&');
      text += `${i + 1}\\. ${query} \\(${s.results_count} natija\\)\n`;
    });

    ctx.editMessageText(text, {
      parse_mode: 'MarkdownV2',
      ...Markup.inlineKeyboard([[Markup.button.callback('⬅️ Orqaga', 'profile_back')]]),
    });
    ctx.answerCbQuery();
  });

  bot.action('profile_back', (ctx) => {
    const user = getUser.get(ctx.from.id);
    const downloads = getDownloadCount.get(ctx.from.id);
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ');

    ctx.editMessageText(
      `👤 *Profil*\n\n` +
      `📛 Ism: *${name.replace(/[_*[\]()~`>#+\-=|{}.!\\]/g, '\\$&')}*\n` +
      `🆔 ID: \`${user.telegram_id}\`\n` +
      `${user.username ? `👤 Username: @${user.username}\n` : ''}` +
      `📥 Jami yuklanmalar: *${downloads.count}*\n`,
      {
        parse_mode: 'MarkdownV2',
        ...Markup.inlineKeyboard([
          [Markup.button.callback('📥 Yuklanmalar tarixi', 'profile_downloads')],
          [Markup.button.callback('🔍 Qidiruvlar tarixi', 'profile_searches')],
        ]),
      }
    );
    ctx.answerCbQuery();
  });
}

module.exports = { setupProfileHandlers };
