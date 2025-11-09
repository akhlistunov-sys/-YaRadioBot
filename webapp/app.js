// Базовый JavaScript для веб-приложения
console.log("Radio App loaded");

// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Основные функции
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.style.display = 'none';
    });
    document.getElementById(screenId).style.display = 'block';
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    showScreen('main-menu');
});
