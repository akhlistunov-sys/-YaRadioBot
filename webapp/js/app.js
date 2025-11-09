// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Состояние приложения
let appState = {
    userData: {},
    campaignData: {}
};

// Навигация
function navigateTo(screen) {
    // Скрываем все экраны
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    // Показываем целевой экран
    const targetScreen = document.getElementById(screen + 'Screen');
    if (targetScreen) {
        targetScreen.classList.add('active');
    } else {
        loadScreen(screen);
    }
}

// Загрузка экранов
async function loadScreen(screenName) {
    try {
        const response = await fetch(`screens/${screenName}.html`);
        const html = await response.text();
        
        const screen = document.createElement('div');
        screen.className = 'screen';
        screen.id = screenName + 'Screen';
        screen.innerHTML = html;
        
        document.getElementById('app').appendChild(screen);
        screen.classList.add('active');
        
    } catch (error) {
        console.error('Error loading screen:', error);
    }
}

// Отправка данных в бот
function submitCampaign(campaignData) {
    const data = {
        user_id: tg.initDataUnsafe.user.id,
        campaign_data: campaignData,
        timestamp: new Date().toISOString()
    };
    
    tg.sendData(JSON.stringify(data));
    tg.close();
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    console.log('RadioPlanner WebApp started');
});
