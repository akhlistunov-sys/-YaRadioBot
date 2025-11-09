// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;

// Состояние приложения
let appState = {
    currentScreen: 'main',
    userData: {},
    campaignData: {
        radio_stations: [],
        time_slots: [],
        start_date: '',
        end_date: '',
        campaign_days: 0,
        branded_section: '',
        campaign_text: '',
        production_option: '',
        contact_name: '',
        company: '',
        phone: '',
        email: '',
        duration: 20,
        base_price: 0,
        discount: 0,
        final_price: 0,
        actual_reach: 0
    }
};

// Инициализация приложения
function initApp() {
    console.log('🚀 RadioPlanner WebApp запущен');
    
    // Инициализация Telegram WebApp
    tg.expand();
    tg.enableClosingConfirmation();
    tg.BackButton.hide();
    
    // Получаем данные пользователя
    if (tg.initDataUnsafe.user) {
        appState.userData = {
            id: tg.initDataUnsafe.user.id,
            first_name: tg.initDataUnsafe.user.first_name,
            last_name: tg.initDataUnsafe.user.last_name,
            username: tg.initDataUnsafe.user.username
        };
        console.log('👤 User data:', appState.userData);
    }
    
    // Показываем главный экран
    showScreen('main');
}

// Навигация между экранами
function showScreen(screenName) {
    // Скрываем все экраны
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    // Показываем целевой экран
    const targetScreen = document.getElementById(screenName + 'Screen');
    if (targetScreen) {
        targetScreen.classList.add('active');
        appState.currentScreen = screenName;
        updateNavigation();
    } else {
        loadScreen(screenName);
    }
}

// Динамическая загрузка экранов
async function loadScreen(screenName) {
    try {
        const response = await fetch(`screens/${screenName}.html`);
        if (!response.ok) throw new Error('Screen not found');
        
        const html = await response.text();
        
        const screen = document.createElement('div');
        screen.className = 'screen';
        screen.id = screenName + 'Screen';
        screen.innerHTML = html;
        
        document.getElementById('screenContainer').appendChild(screen);
        screen.classList.add('active');
        appState.currentScreen = screenName;
        
        updateNavigation();
        
        // Инициализация загруженного экрана
        initScreen(screenName);
        
    } catch (error) {
        console.error('❌ Error loading screen:', error);
        showError('Ошибка загрузки страницы');
    }
}

// Инициализация конкретного экрана
function initScreen(screenName) {
    switch(screenName) {
        case 'radio-selection':
            initRadioSelection();
            break;
        case 'campaign-dates':
            initCampaignDates();
            break;
        // Добавьте другие экраны по мере необходимости
    }
}

// Обновление навигации (кнопка назад)
function updateNavigation() {
    if (appState.currentScreen !== 'main') {
        tg.BackButton.show();
        tg.BackButton.onClick(goBack);
    } else {
        tg.BackButton.hide();
    }
}

// Навигация назад
function goBack() {
    const screens = ['main', 'radio-selection', 'campaign-dates', 'time-slots', 
                    'branded-sections', 'campaign-creator', 'production-option', 
                    'contact-info', 'confirmation'];
    
    const currentIndex = screens.indexOf(appState.currentScreen);
    if (currentIndex > 0) {
        showScreen(screens[currentIndex - 1]);
    }
}

// Навигация (alias для совместимости)
function navigateTo(screenName) {
    showScreen(screenName);
}

// Показ ошибок
function showError(message) {
    tg.showPopup({
        title: 'Ошибка',
        message: message,
        buttons: [{ type: 'ok' }]
    });
}

// Показ успеха
function showSuccess(message) {
    tg.showPopup({
        title: 'Успех',
        message: message,
        buttons: [{ type: 'ok' }]
    });
}

// Форматирование чисел
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

// Расчет стоимости кампании (упрощенная версия)
function calculateCampaignPrice() {
    // Здесь будет ваша логика расчета из bot.py
    const basePrice = appState.campaignData.radio_stations.length * 10000;
    const discount = basePrice * 0.5;
    const finalPrice = Math.max(basePrice - discount, 7000);
    
    appState.campaignData.base_price = basePrice;
    appState.campaignData.discount = discount;
    appState.campaignData.final_price = finalPrice;
    appState.campaignData.actual_reach = basePrice * 10; // Упрощенный расчет
    
    return finalPrice;
}

// Отправка данных в бот
function submitCampaign() {
    try {
        const campaignData = {
            ...appState.campaignData,
            user_id: appState.userData.id,
            timestamp: new Date().toISOString()
        };
        
        console.log('📤 Sending campaign data:', campaignData);
        
        tg.sendData(JSON.stringify(campaignData));
        showSuccess('Заявка успешно отправлена! Менеджер свяжется с вами в ближайшее время.');
        
        // Закрываем WebApp через 2 секунды
        setTimeout(() => {
            tg.close();
        }, 2000);
        
    } catch (error) {
        console.error('❌ Error submitting campaign:', error);
        showError('Ошибка отправки заявки. Попробуйте еще раз.');
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', initApp);
