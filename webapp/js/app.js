// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;

// Инициализация приложения
function initApp() {
    console.log('🚀 RadioPlanner WebApp запущен');
    
    // Инициализация Telegram WebApp
    tg.expand();
    tg.enableClosingConfirmation();
    tg.BackButton.hide();
    
    console.log('👤 User data:', tg.initDataUnsafe.user);
}

// Демо-функции для тестирования
function showDemoAlert() {
    tg.showPopup({
        title: 'Функция в разработке',
        message: 'Этот раздел находится в активной разработке. Используйте демо-кнопку ниже для тестирования отправки заявки.',
        buttons: [{ type: 'ok' }]
    });
}

function submitDemoCampaign() {
    const demoData = {
        user_id: tg.initDataUnsafe.user?.id || 123456,
        radio_stations: ['LOVE RADIO', 'АВТОРАДИО'],
        start_date: '15.01.2025',
        end_date: '30.01.2025',
        campaign_days: 15,
        time_slots: [0, 1, 2],
        branded_section: 'auto',
        contact_name: 'Тестовый Пользователь',
        company: 'Тестовая компания',
        phone: '+79123456789',
        email: 'test@example.com',
        base_price: 15000,
        discount: 7500,
        final_price: 7500,
        actual_reach: 125000
    };
    
    console.log('📤 Отправка демо-данных:', demoData);
    
    tg.sendData(JSON.stringify(demoData));
    
    tg.showPopup({
        title: '✅ Заявка отправлена!',
        message: 'Тестовая заявка успешно отправлена в бота. Проверьте чат с ботом для подтверждения.',
        buttons: [{ type: 'ok' }]
    });
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', initApp);
