// [file name]: frontend/js/app.js
// Конфигурация API - теперь фронтенд и бэкенд на одном домене
const API_BASE_URL = '/api';

// Глобальное состояние приложения
let appState = {
    currentStep: 1,
    selectedRadios: [],
    selectedTimeSlots: [],
    userData: {
        contactName: '',
        contactPhone: '',
        contactEmail: '',
        contactCompany: '',
        duration: 20,
        campaignDays: 30,
        brandedSection: 'auto'
    },
    calculation: null,
    timeSlots: []
};

// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;

// Основная функция инициализации
async function initApp() {
    console.log('🚀 Инициализация Mini App...');
    
    // Расширяем приложение на весь экран
    tg.expand();
    
    // Загружаем начальные данные
    await Promise.all([
        loadRadioStations(),
        loadTimeSlots()
    ]);
    
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

// Загрузка временных слотов с API
async function loadTimeSlots() {
    try {
        const response = await fetch(`${API_BASE_URL}/time-slots`);
        const data = await response.json();
        
        if (data.success && data.time_slots) {
            appState.timeSlots = data.time_slots;
            renderTimeSlots(data.time_slots);
        }
    } catch (error) {
        console.error('Ошибка загрузки временных слотов:', error);
        // Используем демо-данные если API не доступно
        appState.timeSlots = [
            {"time": "06:00-07:00", "label": "Подъем, сборы", "premium": true, "coverage_percent": 6},
            {"time": "07:00-08:00", "label": "Утренние поездки", "premium": true, "coverage_percent": 10}
        ];
        renderTimeSlots(appState.timeSlots);
    }
}

// Показать загрузку
function showLoading(elementId, message = 'Загрузка...') {
    const container = document.getElementById(elementId);
    if (container) {
        container.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p>${message}</p>
            </div>
        `;
    }
}

// Отрисовка списка радиостанций
function renderRadioStations(stations) {
    const container = document.getElementById('radioStationsList');
    if (!container) return;
    
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

// Отрисовка временных слотов
function renderTimeSlots(slots) {
    const container = document.getElementById('timeSlotsList');
    if (!container) return;
    
    container.innerHTML = '';
    
    slots.forEach((slot, index) => {
        const isSelected = appState.selectedTimeSlots.includes(index);
        const slotElement = document.createElement('div');
        slotElement.className = `time-slot ${isSelected ? 'selected' : ''}`;
        slotElement.innerHTML = `
            <div class="slot-time">${slot.time}</div>
            <div class="slot-label">${slot.label} • ${slot.coverage_percent}% охвата</div>
        `;
        
        slotElement.addEventListener('click', () => toggleTimeSlot(index, slotElement));
        container.appendChild(slotElement);
    });
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

// Переключение выбора временного слота
function toggleTimeSlot(index, element) {
    const slotIndex = appState.selectedTimeSlots.indexOf(index);
    
    if (slotIndex === -1) {
        // Добавляем слот
        appState.selectedTimeSlots.push(index);
        element.classList.add('selected');
    } else {
        // Удаляем слот
        appState.selectedTimeSlots.splice(slotIndex, 1);
        element.classList.remove('selected');
    }
}

// Обновление статистики выбора
function updateSelectionStats() {
    const selectedCountElement = document.getElementById('selectedCount');
    const totalListenersElement = document.getElementById('totalListeners');
    
    if (selectedCountElement) {
        selectedCountElement.textContent = appState.selectedRadios.length;
    }
    
    // Временные данные для демонстрации
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
    
    if (totalListenersElement) {
        totalListenersElement.textContent = formatNumber(totalListeners);
    }
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
    const stepElement = document.getElementById(`step${stepNumber}`);
    if (stepElement) {
        stepElement.classList.remove('hidden');
    }
    
    appState.currentStep = stepNumber;
    
    // Специальные действия при переходе на шаг
    switch(stepNumber) {
        case 2:
            calculateCampaign();
            break;
        case 5:
            updateConfirmationData();
            break;
    }
    
    updateStepIndicator(stepNumber);
}

// Обновление индикатора шагов
function updateStepIndicator(currentStep) {
    const steps = document.querySelectorAll('.step');
    steps.forEach((step, index) => {
        const stepNumber = index + 1;
        step.classList.remove('active', 'completed');
        
        if (stepNumber === currentStep) {
            step.classList.add('active');
        } else if (stepNumber < currentStep) {
            step.classList.add('completed');
        }
    });
}

function nextStep(step) {
    // Валидация перед переходом
    switch(step) {
        case 2:
            if (appState.selectedRadios.length === 0) {
                showError('Выберите хотя бы одну радиостанцию');
                return;
            }
            break;
        case 3:
            if (appState.selectedTimeSlots.length === 0) {
                showError('Выберите хотя бы один временной слот');
                return;
            }
            break;
        case 4:
            // Валидация контактных данных
            if (!validateContactData()) {
                return;
            }
            break;
    }
    
    showStep(step);
}

function prevStep(step) {
    showStep(step);
}

// Валидация контактных данных
function validateContactData() {
    const name = document.getElementById('contactName').value.trim();
    const phone = document.getElementById('contactPhone').value.trim();
    
    if (!name) {
        showError('Введите ваше имя');
        return false;
    }
    
    if (!phone) {
        showError('Введите ваш телефон');
        return false;
    }
    
    // Сохраняем данные в состоянии
    appState.userData.contactName = name;
    appState.userData.contactPhone = phone;
    appState.userData.contactEmail = document.getElementById('contactEmail').value.trim();
    appState.userData.contactCompany = document.getElementById('contactCompany').value.trim();
    
    return true;
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
                selected_time_slots: appState.selectedTimeSlots,
                duration: appState.userData.duration,
                campaign_days: appState.userData.campaignDays,
                branded_section: appState.userData.brandedSection
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
    if (!container) return;
    
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
}

// Обновление данных подтверждения
function updateConfirmationData() {
    const stationsElement = document.getElementById('confirmStations');
    const priceElement = document.getElementById('confirmPrice');
    const reachElement = document.getElementById('confirmReach');
    
    if (stationsElement) {
        stationsElement.textContent = appState.selectedRadios.join(', ');
    }
    
    if (priceElement && appState.calculation) {
        priceElement.textContent = formatNumber(appState.calculation.final_price) + ' ₽';
    }
    
    if (reachElement && appState.calculation) {
        reachElement.textContent = '~' + formatNumber(appState.calculation.total_reach) + ' чел.';
    }
}

// Отправка заявки
async function submitCampaign() {
    try {
        const response = await fetch(`${API_BASE_URL}/create-campaign`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: tg.initDataUnsafe.user?.id || Date.now(),
                selected_radios: appState.selectedRadios,
                selected_time_slots: appState.selectedTimeSlots,
                contact_name: appState.userData.contactName,
                phone: appState.userData.contactPhone,
                email: appState.userData.contactEmail,
                company: appState.userData.contactCompany,
                duration: appState.userData.duration,
                campaign_days: appState.userData.campaignDays,
                branded_section: appState.userData.brandedSection,
                base_price: appState.calculation?.base_price || 0,
                discount: appState.calculation?.discount || 0,
                final_price: appState.calculation?.final_price || 0,
                total_reach: appState.calculation?.total_reach || 0
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess('Заявка успешно отправлена! С вами свяжутся в ближайшее время.');
            
            // Можно закрыть Mini App или показать успешное сообщение
            setTimeout(() => {
                tg.close();
            }, 3000);
            
        } else {
            showError('Ошибка отправки заявки: ' + (data.error || 'Попробуйте еще раз'));
        }
    } catch (error) {
        console.error('Ошибка отправки заявки:', error);
        showError('Не удалось отправить заявку. Проверьте подключение.');
    }
}

// Показать ошибку
function showError(message) {
    alert('❌ ' + message);
}

// Показать успех
function showSuccess(message) {
    alert('✅ ' + message);
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
