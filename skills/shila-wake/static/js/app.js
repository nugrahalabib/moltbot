/**
 * Shila Wake System - Main JavaScript
 */

// ===========================================
// Real-time Clock
// ===========================================
function updateClock() {
    const now = new Date();

    // Time
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${mins}:${secs}`;

    // Date
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };
    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
        dateEl.textContent = now.toLocaleDateString('id-ID', options);
    }
}

// Start clock
updateClock();
setInterval(updateClock, 1000);

// ===========================================
// Toast Notifications
// ===========================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: '✓',
        error: '✕',
        info: 'ℹ',
        warning: '⚠'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===========================================
// API Helpers
// ===========================================
async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(endpoint, options);
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Request failed');
        }

        return result;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ===========================================
// Sound Preview
// ===========================================
let currentAudio = null;

function playSound(soundPath) {
    // Stop current sound if playing
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    currentAudio = new Audio(soundPath);
    currentAudio.play().catch(e => {
        showToast('Failed to play sound', 'error');
    });

    // Auto stop after 5 seconds
    setTimeout(() => {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
    }, 5000);
}

function stopSound() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
}

// ===========================================
// Form Validation
// ===========================================
function validateAlarmForm(form) {
    const time = form.querySelector('[name="time"]').value;
    const date = form.querySelector('[name="date"]').value;

    if (!time) {
        showToast('Please set a time', 'warning');
        return false;
    }

    if (!date) {
        showToast('Please select a date', 'warning');
        return false;
    }

    return true;
}

// ===========================================
// Modal Management
// ===========================================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Close modal on background click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// ===========================================
// WebSocket Connection (for real-time updates)
// ===========================================
let ws = null;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/status`;

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('systemStatus').textContent = 'Active';
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            document.getElementById('systemStatus').textContent = 'Reconnecting...';
            setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

    } catch (error) {
        console.error('Failed to connect WebSocket:', error);
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'alarm_triggered':
            showToast(`Alarm: ${data.label || data.time}`, 'info');
            break;

        case 'device_update':
            updateDeviceStatus(data.device, data.state);
            break;

        case 'countdown_update':
            const countdownEl = document.getElementById('countdown');
            if (countdownEl) {
                countdownEl.textContent = data.countdown;
            }
            break;
    }
}

function updateDeviceStatus(device, state) {
    const btn = document.querySelector(`.smart-btn[onclick*="${device}"]`);
    if (btn) {
        if (state) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    }
}

// Connect WebSocket on page load
// connectWebSocket();  // Uncomment when WebSocket endpoint is ready

// ===========================================
// Initialize
// ===========================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('Shila Wake System initialized');
});
