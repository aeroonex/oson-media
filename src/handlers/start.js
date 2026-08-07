const { mainKeyboard } = require('../keyboards/main');
const { upsertUser } = require('../database/userModel');

function setupStartHandlers(bot) {
  bot.start((ctx) => {
    const user = ctx.from;
    upsertUser.run({
      telegram_id: user.id,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      username: user.username || '',
    });

    ctx.reply(
      `🎬 *Oson Media Bot* ga xush kelibsiz, ${user.first_name}\\!\n\n` +
      '🎵 *Musiqa qidirish* — qo\'shiq nomini qidiring\n' +
      '🎬 *Video qidirish* — YouTube dan qidiring\n' +
      '📥 *Yuklab olish* — havola orqali yuklab oling\n' +
      '👤 *Profil* — statistikangizni ko\'ring\n\n' +
      'Quyidagi tugmalardan foydalaning 👇',
      { parse_mode: 'MarkdownV2', ...mainKeyboard }
    );
  });

  bot.help((ctx) => {
    ctx.reply(
      '📋 *Qanday foydalanish:*\n\n' +
      '1️⃣ 🎵 *Musiqa qidirish* — qo\'shiq nomini yozing\n' +
      '2️⃣ 🎬 *Video qidirish* — YouTube dan qidiring\n' +
      '3️⃣ 📥 *Yuklab olish* — YouTube/Instagram havola yuboring\n' +
      '4️⃣ 👤 *Profil* — yuklanmalar tarixini ko\'ring\n\n' +
      'Istalgan vaqtda /start bosing\\!',
      { parse_mode: 'MarkdownV2', ...mainKeyboard }
    );
  });

  bot.hears('❓ Yordam', (ctx) => {
    ctx.reply(
      '📋 *Qanday foydalanish:*\n\n' +
      '🎵 *Musiqa* — tugmani bosing yoki nom yozing\n' +
      '🎬 *Video* — YouTube dan qidiring va yuklab oling\n' +
      '📥 *Yuklab olish* — to\'g\'ridan\\-to\'g\'ri havola yuboring\n' +
      '👤 *Profil* — statistikangiz\n\n' +
      'Muammo bo\'lsa /start bosing\\!',
      { parse_mode: 'MarkdownV2', ...mainKeyboard }
    );
  });
}

module.exports = { setupStartHandlers };
