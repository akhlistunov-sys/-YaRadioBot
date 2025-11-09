// [file name]: frontend/js/app.js
// Конфигурация API - теперь фронтенд и бэкенд на одном домене
const API_BASE_URL = '/api';

// Глобальное состояние приложения
let appState = {
    currentStep: 1,
    selectedRadios: [],
    userData: {},
    calculation: null
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
        showLoading('radioStationsList', 'Загрузка радиостанций...');
        
        const response = await fetch(`${API_BASE_URL}/radio-stations`);
        const data = await response.json();
        
        if (data.stations) {
            renderRadioStations(data.stations);
        } else {
            showError('Не удалось загрузить список радиостанций');
        }
    } catch (error) {
        console.error('Ошибка загрузки радиостанций:', error);
        showError('Не удалось загрузить радиостанции. Проверьте подключение.');
    }
}

// Показать загрузку
function showLoading(elementId, message = 'Загрузка...') {
    const container = document.getElementById(elementId);
    container.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>${message}</p>
        </div>
    `;
}

// Отрисовка списка радиостанций
function renderRadioStations(stations) {
    const container = document.getElementById('radioStationsList');
    container.innerHTML = '';
    
    Object.entries(stations).forEach(([name, listeners]) => {
        const isSelected = appState.selectedRadios.includes(name);
        const stationElement = document.createElement('div');
        stationElement.className = `radio-station ${isSelected ? 'selected' : ''}`;
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
    
    // Временные данные для демонстрации (в реальном приложении - с API)
    const stationListeners = {
        'LOVE RADIO': 540,
        'АВТОРАДИО': 3250,
        'РАДИО ДАЧА': 3250,
        'РАДИО ШАНСОН': 2900,
        'РЕТРО FM': 3600,
        'ЮМОР FM': 1260
    };
    
    const totalListeners = appState.selectedRadios.reduce((total, radio) => {
        return total + (stationListeners[radio] || 0);
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
    
    // Специальные действия при переходе на шаг
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
        showLoading('calculationResult', 'Рассчитываем стоимость...');
        
        const response = await fetch(`${API_BASE_URL}/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                selected_radios: appState.selectedRadios,
                duration: 20, // стандартная длительность
                campaign_days: 30, // стандартный период
                selected_time_slots: [0, 1, 2], // демо-слоты
                branded_section: "auto" // демо-рубрика
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            appState.calculation = data.calculation;
            displayCalculationResult(data.calculation);
        } else {
            showError('Ошибка расчета: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Ошибка расчета:', error);
        showError('Не удалось рассчитать стоимость. Проверьте подключение.');
    }
}

// Отображение результатов расчета
function displayCalculationResult(calc) {
    const container = document.getElementById('calculationResult');
    
    container.innerHTML = `
        <div class="stats">
            <div class="stat-item">
                <span>Базовая стоимость:</span>
                <span>${formatNumber(calc.base_price)} ₽</span>
            </div>
            <div class="stat-item">
                <span>Скидка 50%:</span>
                <span style="color: #27ae60;">-${formatNumber(calc.discount)} ₽</span>
            </div>
            <div class="stat-item" style="font-weight: bold; font-size: 16px; border-top: 1px solid #ddd; padding-top: 10px;">
                <span>Итоговая стоимость:</span>
                <span style="color: #e74c3c;">${formatNumber(calc.final_price)} ₽</span>
            </div>
            <div class="stat-item">
                <span>Охват за период:</span>
                <span>~${formatNumber(calc.total_reach)} чел.</span>
            </div>
            <div class="stat-item">
                <span>Выходов в день:</span>
                <span>${calc.spots_per_day}</span>
            </div>
        </div>
    `;
    
    // Обновляем также основные цифры в шапке шага 2
    document.getElementById('basePrice').textContent = formatNumber(calc.base_price) + ' ₽';
    document.getElementById('discount').textContent = '-' + formatNumber(calc.discount) + ' ₽';
    document.getElementById('finalPrice').textContent = formatNumber(calc.final_price) + ' ₽';
}

// Показать ошибку
function showError(message) {
    // В реальном приложении можно использовать красивый toast
    alert('❌ ' + message);
}

// Тестовая функция для проверки API
async function testAPI() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        console.log('API Health:', data);
        return data.status === 'healthy';
    } catch (error) {
        console.error('API Test failed:', error);
        return false;
    }
}

// Инициализация приложения когда DOM загружен
document.addEventListener('DOMContentLoaded', function() {
    // Сначала проверяем API
    testAPI().then(apiHealthy => {
        if (apiHealthy) {
            initApp();
        } else {
            document.body.innerHTML = `
                <div style="color: white; text-align: center; padding: 50px 20px;">
                    <h1>😔 Сервис временно недоступен</h1>
                    <p>Попробуйте обновить страницу через несколько минут</p>
                    <button onclick="location.reload()" style="background: white; color: #667eea; border: none; padding: 10px 20px; border-radius: 10px; margin-top: 20px; cursor: pointer;">
                        Обновить страницу
                    </button>
                </div>
            `;
        }
    });
});
