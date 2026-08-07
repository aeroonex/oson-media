const { Markup } = require('telegraf');

const mainKeyboard = Markup.keyboard([
  ['🎵 Musiqa qidirish', '🎬 Video qidirish'],
  ['📥 Yuklab olish', '👤 Profil'],
  ['❓ Yordam']
]).resize();

const cancelKeyboard = Markup.keyboard([
  ['❌ Bekor qilish']
]).resize();

function searchResultButtons(results, page, totalPages, type) {
  const buttons = [];

  const numberRow = results.map((_, i) => {
    const num = page * 4 + i + 1;
    return Markup.button.callback(`${num}`, `${type}_select_${page}_${i}`);
  });
  buttons.push(numberRow);

  const navRow = [];
  if (page > 0) {
    navRow.push(Markup.button.callback('◀️', `${type}_page_${page - 1}`));
  }
  navRow.push(Markup.button.callback('❌', `${type}_cancel`));
  if (page < totalPages - 1) {
    navRow.push(Markup.button.callback('▶️', `${type}_page_${page + 1}`));
  }
  buttons.push(navRow);

  return Markup.inlineKeyboard(buttons);
}

function downloadTypeButtons(index, page) {
  return Markup.inlineKeyboard([
    [
      Markup.button.callback('🎵 Audio', `yt_audio_${page}_${index}`),
      Markup.button.callback('🎬 Video', `yt_video_${page}_${index}`),
    ],
    [Markup.button.callback('⬅️ Orqaga', `yt_page_${page}`)],
  ]);
}

module.exports = {
  mainKeyboard,
  cancelKeyboard,
  searchResultButtons,
  downloadTypeButtons,
};
