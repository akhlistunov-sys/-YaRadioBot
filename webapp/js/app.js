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
        production_cost: 0,
        base_price: 0,
        discount: 0,
        final_price: 0,
        actual_reach: 0
    }
};

// Данные из оригинального бота
const STATION_COVERAGE = {
    "LOVE RADIO": 540,
    "АВТОРАДИО": 3250,
    "РАДИО ДАЧА": 3250,
    "РАДИО ШАНСОН": 2900,
    "РЕТРО FM": 3600,
    "ЮМОР FM": 1260
};

const TIME_SLOTS_DATA = [
    {"time": "06:00-07:00", "label": "Подъем, сборы", "premium": true, "coverage_percent": 6},
    {"time": "07:00-08:00", "label": "Утренние поездки", "premium": true, "coverage_percent": 10},
    {"time": "08:00-09:00", "label": "Пик трафика", "premium": true, "coverage_percent": 12},
    {"time": "09:00-10:00", "label": "Начало работы", "premium": true, "coverage_percent": 8},
    {"time": "10:00-11:00", "label": "Рабочий процесс", "premium": true, "coverage_percent": 7},
    {"time": "11:00-12:00", "label": "Предобеденное время", "premium": true, "coverage_percent": 6},
    {"time": "12:00-13:00", "label": "Обеденный перерыв", "premium": true, "coverage_percent": 5},
    {"time": "13:00-14:00", "label": "После обеда", "premium": true, "coverage_percent": 5},
    {"time": "14:00-15:00", "label": "Вторая половина дня", "premium": true, "coverage_percent": 5},
    {"time": "15:00-16:00", "label": "Рабочий финиш", "premium": true, "coverage_percent": 6},
    {"time": "16:00-17:00", "label": "Конец рабочего дня", "premium": true, "coverage_percent": 7},
    {"time": "17:00-18:00", "label": "Вечерние поездки", "premium": true, "coverage_percent": 10},
    {"time": "18:00-19:00", "label": "Пик трафика", "premium": true, "coverage_percent": 8},
    {"time": "19:00-20:00", "label": "Домашний вечер", "premium": true, "coverage_percent": 4},
    {"time": "20:00-21:00", "label": "Вечерний отдых", "premium": true, "coverage_percent": 4}
];

const BRANDED_SECTION_PRICES = {
    "auto": 1.2,
    "realty": 1.15,
    "medical": 1.25,
    "custom": 1.3
};

const PRODUCTION_OPTIONS = {
    "standard": {"price": 2000, "name": "СТАНДАРТНЫЙ РОЛИК", "desc": "Профессиональная озвучка, музыкальное оформление, срок: 2-3 дня"},
    "premium": {"price": 5000, "name": "ПРЕМИУМ РОЛИК", "desc": "Озвучка 2-мя голосами, индивидуальная музыка, срочное производство 1 день"}
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
        case 'time-slots':
            initTimeSlots();
            break;
        case 'branded-sections':
            initBrandedSections();
            break;
        case 'campaign-creator':
            initCampaignCreator();
            break;
        case 'production-option':
            initProductionOption();
            break;
        case 'contact-info':
            initContactInfo();
            break;
        case 'confirmation':
            initConfirmation();
            break;
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

// Основные функции навигации
function startNewCampaign() {
    // Сбрасываем данные кампании
    appState.campaignData = {
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
        production_cost: 0,
        base_price: 0,
        discount: 0,
        final_price: 0,
        actual_reach: 0
    };
    
    showScreen('radio-selection');
}

function showStatistics() {
    tg.showPopup({
        title: '📊 ВОЗРАСТНАЯ СТРУКТУРА',
        message: 'Раздел в разработке. В полной версии будет доступна детальная аналитика аудитории.',
        buttons: [{ type: 'ok' }]
    });
}

function showAbout() {
    tg.showPopup({
        title: '🏆 О НАС',
        message: '10 лет на рынке радиорекламы. 6 федеральных станций. 40 000+ слушателей.',
        buttons: [{ type: 'ok' }]
    });
}

function showPersonalCabinet() {
    tg.showPopup({
        title: '📋 ЛИЧНЫЙ КАБИНЕТ',
        message: 'Раздел в разработке. В полной версии будет доступна история заявок и статистика.',
        buttons: [{ type: 'ok' }]
    });
}

// Вспомогательные функции
function showError(message) {
    tg.showPopup({
        title: 'Ошибка',
        message: message,
        buttons: [{ type: 'ok' }]
    });
}

function showSuccess(message) {
    tg.showPopup({
        title: 'Успех',
        message: message,
        buttons: [{ type: 'ok' }]
    });
}

function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

// Расчет стоимости кампании (упрощенная версия)
function calculateCampaignPrice() {
    const baseDuration = appState.campaignData.duration || 20;
    const campaignDays = appState.campaignData.campaign_days || 30;
    const selectedRadios = appState.campaignData.radio_stations || [];
    const selectedTimeSlots = appState.campaignData.time_slots || [];
    
    if (!selectedRadios.length || !selectedTimeSlots.length) {
        return { base_price: 0, discount: 0, final_price: 7000, actual_reach: 0 };
    }
    
    const numStations = selectedRadios.length;
    const spotsPerDay = selectedTimeSlots.length * numStations;
    
    // Базовый расчет (упрощенный)
    const BASE_PRICE_PER_SECOND = 2.0;
    const costPerSpot = baseDuration * BASE_PRICE_PER_SECOND;
    const baseAirCost = costPerSpot * spotsPerDay * campaignDays;
    
    // Множители
    let timeMultiplier = 1.0;
    selectedTimeSlots.forEach(slotIndex => {
        if (TIME_SLOTS_DATA[slotIndex]?.premium) {
            timeMultiplier = Math.max(timeMultiplier, 1.1);
        }
    });
    
    let brandedMultiplier = 1.0;
    if (appState.campaignData.branded_section in BRANDED_SECTION_PRICES) {
        brandedMultiplier = BRANDED_SECTION_PRICES[appState.campaignData.branded_section];
    }
    
    const productionCost = appState.campaignData.production_cost || 0;
    const airCost = baseAirCost * timeMultiplier * brandedMultiplier;
    const basePrice = airCost + productionCost;
    
    const discount = basePrice * 0.5;
    const finalPrice = Math.max(basePrice - discount, 7000);
    
    // Расчет охвата
    const totalListeners = selectedRadios.reduce((sum, radio) => sum + (STATION_COVERAGE[radio] || 0), 0);
    const totalCoveragePercent = selectedTimeSlots.reduce((sum, slotIndex) => 
        sum + (TIME_SLOTS_DATA[slotIndex]?.coverage_percent || 0), 0);
    
    const uniqueDailyCoverage = totalListeners * 0.7 * (totalCoveragePercent / 100);
    const totalReach = uniqueDailyCoverage * campaignDays;
    
    return {
        base_price: Math.round(basePrice),
        discount: Math.round(discount),
        final_price: Math.round(finalPrice),
        actual_reach: Math.round(totalReach),
        daily_coverage: Math.round(uniqueDailyCoverage),
        spots_per_day: spotsPerDay,
        total_coverage_percent: totalCoveragePercent
    };
}

// Отправка данных в бот
function submitCampaign() {
    try {
        // Расчет финальной стоимости
        const priceData = calculateCampaignPrice();
        
        const campaignData = {
            ...appState.campaignData,
            ...priceData,
            user_id: appState.userData.id,
            timestamp: new Date().toISOString()
        };
        
        console.log('📤 Отправка данных кампании:', campaignData);
        
        tg.sendData(JSON.stringify(campaignData));
        
        showSuccess('Заявка успешно отправлена! Менеджер свяжется с вами в ближайшее время.');
        
    } catch (error) {
        console.error('❌ Ошибка отправки заявки:', error);
        showError('Ошибка отправки заявки. Попробуйте еще раз.');
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', initApp);
