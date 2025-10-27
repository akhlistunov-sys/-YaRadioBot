
const { Telegraf, Markup } = require('telegraf');

// Замените на ваш токен
const BOT_TOKEN = 'YaRadioBot';
const bot = new Telegraf(BOT_TOKEN);

// Данные радиостанций
const stations = [
    { id: 1, name: "Love Radio", listeners: 3200, price: 280, emoji: "❤️" },
    { id: 2, name: "Авторадио", listeners: 2800, price: 260, emoji: "🚗" },
    { id: 3, name: "Радио Дача", listeners: 3500, price: 240, emoji: "🏡" },
    { id: 4, name: "Радио Шансон", listeners: 2600, price: 250, emoji: "🎵" },
    { id: 5, name: "Ретро FM", listeners: 2900, price: 230, emoji: "📻" },
    { id: 6, name: "Юмор FM", listeners: 2100, price: 270, emoji: "😊" }
];

// Временные слоты
const timeSlots = [
    "06:00-07:00 🌅 Утро", "07:00-08:00 🚀 Пик", "08:00-09:00 📈 Трафик",
    "09:00-10:00 ☕ Работа", "10:00-11:00 📊 День", "11:00-12:00 ⏰ Обед",
    "12:00-13:00 🍽️ Перерыв", "13:00-14:00 📋 После обеда", "14:00-15:00 🔄 Работа",
    "15:00-16:00 📝 Вечер", "16:00-17:00 🏃 Выход", "17:00-18:00 🚀 Пик",
    "18:00-19:00 📈 Трафик", "19:00-20:00 🏠 Дом", "20:00-21:00 🌙 Отдых"
];

// Хранилище пользовательских данных
const userSessions = new Map();

// Команда старт
bot.start((ctx) => {
    const userId = ctx.from.id;
    userSessions.set(userId, {
        selectedStations: [],
        selectedSlots: [],
        campaignDays: 30,
        spotsPerDay: 5,
        step: 'main'
    });
    
    ctx.reply(
        `🎧 *Добро пожаловать в YA-RADIO!*\n\n` +
        `*Радио Тюменской области* - официальный вещатель в Ялуторовске и Заводоуковске\n\n` +
        `Я помогу вам заказать рекламу на наших радиостанциях:\n` +
        `• Love Radio ❤️\n• Авторадио 🚗\n• Радио Дача 🏡\n` +
        `• Радио Шансон 🎵\n• Ретро FM 📻\n• Юмор FM 😊\n\n` +
        `*Ключевые показатели:*\n` +
        `📊 18,500+ слушателей в день\n` +
        `👥 156,000+ контактов в месяц\n` +
        `🎯 52% доля рынка\n` +
        `💰 4₽/сек базовая цена\n` +
        `📍 Ялуторовск • Заводоуковск`,
        {
            parse_mode: 'Markdown',
            ...Markup.keyboard([
                ['🎯 Выбрать станции', '📊 Статистика'],
                ['💰 Калькулятор', '📞 Контакты'],
                ['ℹ️ О нас']
            ]).resize()
        }
    );
});

// Обработка текстовых сообщений
bot.hears('🎯 Выбрать станции', (ctx) => showStationsSelection(ctx));
bot.hears('📊 Статистика', (ctx) => showStatistics(ctx));
bot.hears('💰 Калькулятор', (ctx) => showCalculator(ctx));
bot.hears('📞 Контакты', (ctx) => showContacts(ctx));
bot.hears('ℹ️ О нас', (ctx) => showAbout(ctx));

// Показать выбор станций
function showStationsSelection(ctx) {
    const userId = ctx.from.id;
    const userSession = userSessions.get(userId) || {};
    userSession.step = 'selecting_stations';
    userSessions.set(userId, userSession);
    
    const selectedStationsText = userSession.selectedStations.length > 0 
        ? `\n✅ Выбрано: ${userSession.selectedStations.length} станций`
        : '';
    
    const keyboard = stations.map(station => [
        Markup.button.callback(
            `${userSession.selectedStations.includes(station.id) ? '✅ ' : ''}${station.emoji} ${station.name}`,
            `station_${station.id}`
        )
    ]);
    
    keyboard.push([
        Markup.button.callback('🚀 Далее к расписанию', 'next_to_slots'),
        Markup.button.callback('🔄 Сбросить', 'reset_stations')
    ]);
    
    ctx.reply(
        `*YA-RADIO - Выбор радиостанций*${selectedStationsText}\n\n` +
        stations.map(s => 
            `${s.emoji} *${s.name}*\n` +
            `👥 ${s.listeners} слушателей/день\n` +
            `💰 ${s.price}₽ за ролик\n` +
            `⏱ ${(s.price/30).toFixed(2)}₽/сек\n`
        ).join('\n'),
        {
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard(keyboard)
        }
    );
}

// Обработка выбора станций
stations.forEach(station => {
    bot.action(`station_${station.id}`, (ctx) => {
        const userId = ctx.from.id;
        const userSession = userSessions.get(userId) || { selectedStations: [] };
        
        if (userSession.selectedStations.includes(station.id)) {
            userSession.selectedStations = userSession.selectedStations.filter(id => id !== station.id);
        } else {
            userSession.selectedStations.push(station.id);
        }
        
        userSessions.set(userId, userSession);
        ctx.answerCbQuery();
        showStationsSelection(ctx);
    });
});

// Сброс выбора станций
bot.action('reset_stations', (ctx) => {
    const userId = ctx.from.id;
    const userSession = userSessions.get(userId) || {};
    userSession.selectedStations = [];
    userSessions.set(userId, userSession);
    ctx.answerCbQuery('Выбор станций сброшен!');
    showStationsSelection(ctx);
});

// Переход к выбору времени
bot.action('next_to_slots', (ctx) => showTimeSlots(ctx));

// Показать выбор времени
function showTimeSlots(ctx) {
    const userId = ctx.from.id;
    const userSession = userSessions.get(userId) || {};
    
    if (userSession.selectedStations.length === 0) {
        return ctx.reply('❌ Сначала выберите хотя бы одну радиостанцию!');
    }
    
    userSession.step = 'selecting_slots';
    userSessions.set(userId, userSession);
    
    const keyboard = [];
    for (let i = 0; i < timeSlots.length; i += 2) {
        const row = [
            Markup.button.callback(
                `${userSession.selectedSlots.includes(timeSlots[i]) ? '✅ ' : ''}${timeSlots[i]}`,
                `slot_${i}`
            )
        ];
        if (timeSlots[i + 1]) {
            row.push(
                Markup.button.callback(
                    `${userSession.selectedSlots.includes(timeSlots[i + 1]) ? '✅ ' : ''}${timeSlots[i + 1]}`,
                    `slot_${i + 1}`
                )
            );
        }
        keyboard.push(row);
    }
    
    keyboard.push([
        Markup.button.callback('📝 Рассчитать стоимость', 'calculate_price'),
        Markup.button.callback('🔄 Сбросить время', 'reset_slots')
    ]);
    
    const selectedStationsNames = stations
        .filter(s => userSession.selectedStations.includes(s.id))
        .map(s => s.name)
        .join(', ');
    
    ctx.reply(
        `*YA-RADIO - Выбор времени эфира*\n\n` +
        `📻 *Выбранные станции:* ${selectedStationsNames}\n\n` +
        '*Доступные слоты:*\n' +
        '🌅 *Утренние* (+25%): 06:00-10:00\n' +
        '☀️ *Дневные*: 10:00-16:00\n' +
        '🌇 *Вечерние* (+20%): 16:00-21:00\n\n' +
        `✅ Выбрано слотов: ${userSession.selectedSlots.length}`,
        {
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard(keyboard)
        }
    );
}

// Обработка выбора слотов
timeSlots.forEach((slot, index) => {
    bot.action(`slot_${index}`, (ctx) => {
        const userId = ctx.from.id;
        const userSession = userSessions.get(userId) || { selectedSlots: [] };
        
        if (userSession.selectedSlots.includes(slot)) {
            userSession.selectedSlots = userSession.selectedSlots.filter(s => s !== slot);
        } else {
            userSession.selectedSlots.push(slot);
        }
        
        userSessions.set(userId, userSession);
        ctx.answerCbQuery();
        showTimeSlots(ctx);
    });
});

// Сброс выбора слотов
bot.action('reset_slots', (ctx) => {
    const userId = ctx.from.id;
    const userSession = userSessions.get(userId) || {};
    userSession.selectedSlots = [];
    userSessions.set(userId, userSession);
    ctx.answerCbQuery('Выбор времени сброшен!');
    showTimeSlots(ctx);
});

// Расчет стоимости
bot.action('calculate_price', (ctx) => showPriceCalculation(ctx));

// Показать расчет стоимости
function showPriceCalculation(ctx) {
    const userId = ctx.from.id;
    const userSession = userSessions.get(userId) || {};
    
    if (userSession.selectedStations.length === 0) {
        return ctx.reply('❌ Сначала выберите радиостанции!');
    }
    
    const selectedStationsData = stations.filter(s => 
        userSession.selectedStations.includes(s.id)
    );
    
    const totalSpots = userSession.spotsPerDay * userSession.campaignDays;
    const totalCost = calculateTotalCost(userSession);
    
    const selectedStationsText = selectedStationsData.map(s => s.name).join(', ');
    const selectedSlotsText = userSession.selectedSlots.join('\n');
    
    const message = 
        `💰 *YA-RADIO - Расчет стоимости*\n\n` +
        `📻 *Станции:* ${selectedStationsText}\n` +
        `🕒 *Время эфира:*\n${selectedSlotsText}\n` +
        `📅 *Период:* ${userSession.campaignDays} дней\n` +
        `📊 *Роликов в день:* ${userSession.spotsPerDay}\n` +
        `🎬 *Всего роликов:* ${totalSpots}\n\n` +
        `💵 *Предварительная стоимость:*\n` +
        `*${Math.round(totalCost).toLocaleString('ru-RU')}₽*\n\n` +
        `_С учетом всех скидок и бонусов_`;
    
    ctx.reply(message, {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([
            [Markup.button.callback('📞 Связаться с менеджером', 'contact_manager')],
            [Markup.button.callback('🔄 Новый расчет', 'new_calculation')],
            [Markup.button.url('🌐 Посетить сайт', 'http://ya-radio.ru')]
        ])
    });
}

// Функция расчета стоимости
function calculateTotalCost(userSession) {
    const selectedStationsData = stations.filter(s => 
        userSession.selectedStations.includes(s.id)
    );
    
    let total = 0;
    const spotsPerStation = userSession.spotsPerDay / userSession.selectedStations.length;
    
    selectedStationsData.forEach(station => {
        let stationCost = station.price * spotsPerStation * userSession.campaignDays;
        
        // Учет премиальных слотов
        const premiumSlots = userSession.selectedSlots.filter(slot => 
            slot.includes('🌅') || slot.includes('🚀') || slot.includes('🌇')
        ).length;
        
        stationCost *= (1 + premiumSlots * 0.05);
        total += stationCost;
    });
    
    // Скидки за объем
    const totalSpots = userSession.spotsPerDay * userSession.campaignDays;
    let discount = 0;
    if (totalSpots >= 300) discount = 0.6;
    else if (totalSpots >= 200) discount = 0.5;
    else if (totalSpots >= 100) discount = 0.4;
    else if (totalSpots >= 50) discount = 0.2;
    
    // Бонус за multiple станций
    const stationBonus = userSession.selectedStations.length > 1 ? 0.1 : 0;
    
    return total * (1 - discount - stationBonus);
}

// Связь с менеджером
bot.action('contact_manager', (ctx) => {
    ctx.reply(
        `📞 *YA-RADIO - Контакты менеджера*\n\n` +
        `*Ваш персональный менеджер:*\n` +
        `👩 Надежда\n\n` +
        `*Контактные данные:*\n` +
        `📱 Телефон: +7 (34535) 5-01-51\n` +
        `📧 Email: aa@ya-radio.ru\n` +
        `🌐 Сайт: ya-radio.ru\n\n` +
        `*График работы:*\n` +
        `🕘 Пн-Пт: 9:00-18:00\n` +
        `🕙 Сб: 10:00-16:00\n` +
        `🚫 Вс: выходной`,
        {
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
                [Markup.button.url('📞 Позвонить', 'tel:+73453550151')],
                [Markup.button.url('📧 Написать', 'mailto:aa@ya-radio.ru')],
                [Markup.button.url('🌐 Сайт YA-RADIO', 'http://ya-radio.ru')]
            ])
        }
    );
});

// Показать статистику
function showStatistics(ctx) {
    ctx.reply(
        `📊 *YA-RADIO - Статистика охвата*\n\n` +
        `*География вещания:*\n` +
        `📍 Ялуторовск и район (~52,000 чел.)\n` +
        `📍 Заводоуковск и район (~46,500 чел.)\n\n` +
        `*Общие показатели:*\n` +
        `📊 Суточный охват: 18,500+ чел.\n` +
        `👥 Месячный охват: 156,000+ контактов\n` +
        `🎯 Доля рынка: 52%\n` +
        `💰 Базовая цена: 4₽/сек\n\n` +
        `*Возрастная структура:*\n` +
        `👨‍💼 35-45 лет: 36%\n` +
        `👨‍🔧 46-55 лет: 30%\n` +
        `👴 56-65 лет: 22%\n` +
        `👦 18-34 лет: 12%`,
        { parse_mode: 'Markdown' }
    );
}

// Показать калькулятор
function showCalculator(ctx) {
    ctx.reply(
        `💰 *YA-RADIO - Калькулятор стоимости*\n\n` +
        `*Базовая цена:* 4₽ за секунду\n` +
        `*Стандартный ролик 30 сек:* 120₽\n\n` +
        `*Система скидок:*\n` +
        `🥉 50-99 роликов: -20%\n` +
        `🥈 100-199 роликов: -40%\n` +
        `🥇 200-299 роликов: -50%\n` +
        `💎 300+ роликов: -60%\n\n` +
        `*Дополнительные бонусы:*\n` +
        `📻 +5% за каждую доп. станцию\n` +
        `📅 +10% за размещение от 3 месяцев\n\n` +
        `Для точного расчета нажмите "🎯 Выбрать станции"`,
        { 
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
                [Markup.button.callback('🎯 Выбрать станции', 'goto_stations')]
            ])
        }
    );
}

// Переход к выбору станций из калькулятора
bot.action('goto_stations', (ctx) => {
    ctx.answerCbQuery();
    showStationsSelection(ctx);
});

// Показать контакты
function showContacts(ctx) {
    ctx.reply(
        `📞 *YA-RADIO - Контакты*\n\n` +
        `*Радио Тюменской области*\n` +
        `Официальный вещатель в Ялуторовске и Заводоуковске\n\n` +
        `*Контактные данные:*\n` +
        `📱 Телефон: +7 (34535) 5-01-51\n` +
        `📧 Email:a.khlistunov@gmail.com \n` +
        `🌐 Сайт: ya-radio.ru\n\n` +
        `*Рекламный отдел:*\n` +
        `👩 Менеджер: Надежда\n` +
        `🕘 График: Пн-Пт 9:00-18:00`,
        {
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
                [Markup.button.url('📞 Позвонить', 'tel:+73453550151')],
                [Markup.button.url('📧 Написать', 'mailto:a.khlistunov@gmail.com')],
                [Markup.button.url('🌐 Сайт YA-RADIO', 'http://ya-radio.ru')]
            ])
        }
    );
}

// Показать информацию о нас
function showAbout(ctx) {
    ctx.reply(
        `ℹ️ *YA-RADIO - О нас*\n\n` +
        `*Радио Тюменской области* - ведущий радио-холдинг в Ялуторовске и Заводоуковске\n\n` +
        `*Наши радиостанции:*\n` +
        `❤️ Love Radio - музыка и настроение\n` +
        `🚗 Авторадио - для тех, кто в пути\n` +
        `🏡 Радио Дача - уют и домашняя атмосфера\n` +
        `🎵 Радио Шансон - честные истории\n` +
        `📻 Ретро FM - хиты прошлых лет\n` +
        `😊 Юмор FM - позитив и смех\n\n` +
        `*Почему выбирают нас:*\n` +
        `✅ Максимальный охват аудитории\n` +
        `✅ Профессиональный подход\n` +
        `✅ Гибкая система скидок\n` +
        `✅ Индивидуальные решения\n\n` +
        `*Наша миссия:*\n` +
        `Создавать эффективные рекламные кампании, которые работают на результат!`,
        { 
            parse_mode: 'Markdown',
            ...Markup.inlineKeyboard([
                [Markup.button.callback('🎯 Начать заказ', 'goto_stations')],
                [Markup.button.url('🌐 Сайт YA-RADIO', 'http://ya-radio.ru')]
            ])
        }
    );
}

// Новый расчет
bot.action('new_calculation', (ctx) => {
    const userId = ctx.from.id;
    userSessions.delete(userId);
    ctx.answerCbQuery('Начинаем новый расчет!');
    showStationsSelection(ctx);
});

// Обработка неизвестных команд
bot.on('text', (ctx) => {
    ctx.reply(
        `*YA-RADIO - Главное меню*\n\n` +
        `Используйте кнопки ниже для навигации:\n\n` +
        `🎯 *Выбрать станции* - подбор радиостанций и расчет\n` +
        `💰 *Калькулятор* - быстрый расчет стоимости\n` +
        `📊 *Статистика* - данные по охвату аудитории\n` +
        `📞 *Контакты* - связь с нашим менеджером\n` +
        `ℹ️ *О нас* - информация о наших радиостанциях`,
        {
            parse_mode: 'Markdown',
            ...Markup.keyboard([
                ['🎯 Выбрать станции', '📊 Статистика'],
                ['💰 Калькулятор', '📞 Контакты'],
                ['ℹ️ О нас']
            ]).resize()
        }
    );
});

// Запуск бота
bot.launch().then(() => {
    console.log('🤖 Бот YA-RADIO запущен!');
    console.log('🌐 Сайт: http://ya-radio.ru');
    console.log('📞 Телефон: +7 (34535) 5-01-51');
});

// Graceful shutdown
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
