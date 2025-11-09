// Конфигурация API
const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:5000/api' 
    : 'https://yaradiobot.onrender.com/api';

// Глобальное состояние приложения
let appState = {
    currentStep: 1,
    selectedRadios: [],
    userData: {}
};

// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;

// Основная функция инициализации
async function initApp() {
    console.log('🚀 Инициализация Mini App...');
    
    // Расширяем приложение на весь экран
    tg.expand();
    
    // Загружаем радиостанции
    await loadRadioStations();
    
    // Показываем первый шаг
    showStep(1);
}

// Загрузка радиостанций с API
async function loadRadioStations() {
    try {
        const response = await fetch(`${API_BASE_URL}/radio-stations`);
        const data = await response.json();
        
        if (data.stations) {
            renderRadioStations(data.stations);
        }
    } catch (error) {
        console.error('Ошибка загрузки радиостанций:', error);
        showError('Не удалось загрузить радиостанции');
    }
}

// Отрисовка списка радиостанций
function renderRadioStations(stations) {
    const container = document.getElementById('radioStationsList');
    container.innerHTML = '';
    
    Object.entries(stations).forEach(([name, listeners]) => {
        const stationElement = document.createElement('div');
        stationElement.className = 'radio-station';
        stationElement.innerHTML = `
            <div class="radio-name">${name}</div>
            <div class="radio-listeners">~${formatNumber(listeners)} слушателей в день</div>
        `;
        
        stationElement.addEventListener('click', () => toggleRadioStation(name, stationElement));
        container.appendChild(stationElement);
    });
    
    updateSelectionStats();
}

// Переключение выбора радиостанции
function toggleRadioStation(name, element) {
    const index = appState.selectedRadios.indexOf(name);
    
    if (index === -1) {
        // Добавляем станцию
        appState.selectedRadios.push(name);
        element.classList.add('selected');
    } else {
        // Удаляем станцию
        appState.selectedRadios.splice(index, 1);
        element.classList.remove('selected');
    }
    
    updateSelectionStats();
}

// Обновление статистики выбора
function updateSelectionStats() {
    document.getElementById('selectedCount').textContent = appState.selectedRadios.length;
    
    const totalListeners = appState.selectedRadios.reduce((total, radio) => {
        // В реальном приложении здесь будет запрос к API для получения точных данных
        const listeners = {
            'LOVE RADIO': 540,
            'АВТОРАДИО': 3250,
            'РАДИО ДАЧА': 3250,
            'РАДИО ШАНСОН': 2900,
            'РЕТРО FM': 3600,
            'ЮМОР FM': 1260
        }[radio] || 0;
        
        return total + listeners;
    }, 0);
    
    document.getElementById('totalListeners').textContent = formatNumber(totalListeners);
}

// Форматирование чисел с пробелами
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

// Навигация по шагам
function showStep(stepNumber) {
    // Скрываем все шаги
    document.querySelectorAll('.step-content').forEach(step => {
        step.classList.add('hidden');
    });
    
    // Показываем нужный шаг
    document.getElementById(`step${stepNumber}`).classList.remove('hidden');
    appState.currentStep = stepNumber;
    
    // Если переходим на шаг расчета, делаем расчет
    if (stepNumber === 2) {
        calculateCampaign();
    }
}

function nextStep(step) {
    // Валидация перед переходом
    if (step === 2 && appState.selectedRadios.length === 0) {
        showError('Выберите хотя бы одну радиостанцию');
        return;
    }
    
    showStep(step);
}

function prevStep(step) {
    showStep(step);
}

// Расчет стоимости кампании
async function calculateCampaign() {
    try {
        const response = await fetch(`${API_BASE_URL}/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                selected_radios: appState.selectedRadios,
                duration: 20, // стандартная длительность
                campaign_days: 30 // стандартный период
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const calc = data.calculation;
            
            document.getElementById('basePrice').textContent = formatNumber(calc.base_price) + ' ₽';
            document.getElementById('discount').textContent = '-' + formatNumber(calc.discount) + ' ₽';
            document.getElementById('finalPrice').textContent = formatNumber(calc.final_price) + ' ₽';
        } else {
            showError('Ошибка расчета: ' + data.error);
        }
    } catch (error) {
        console.error('Ошибка расчета:', error);
        showError('Не удалось рассчитать стоимость');
    }
}

// Показать ошибку
function showError(message) {
    // В реальном приложении можно использовать красивый toast
    alert('❌ ' + message);
}

// Инициализация приложения когда DOM загружен
document.addEventListener('DOMContentLoaded', initApp);
