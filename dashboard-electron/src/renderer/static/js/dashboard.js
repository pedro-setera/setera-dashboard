// Dashboard JavaScript - Search and Launch Functionality (Electron Version)

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeKeyboardShortcuts();
    // Note: Auto-shutdown removed - not needed in Electron desktop app
});

// Search Functionality
function initializeSearch() {
    const searchBox = document.getElementById('searchBox');
    if (searchBox) {
        searchBox.addEventListener('input', performSearch);
        searchBox.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                searchBox.value = '';
                performSearch();
                searchBox.blur();
            }
        });
    }
}

function performSearch() {
    const searchTerm = document.getElementById('searchBox').value.toLowerCase().trim();
    const allCards = document.querySelectorAll('.app-card');
    const allSections = document.querySelectorAll('.category-section');

    if (searchTerm === '') {
        // Show all cards and sections
        allCards.forEach(card => {
            card.classList.remove('hidden');
            card.classList.remove('filtered-in');
        });
        allSections.forEach(section => {
            section.style.display = '';
        });
        return;
    }

    // Filter cards based on search term
    allSections.forEach(section => {
        let hasVisibleCards = false;
        const cards = section.querySelectorAll('.app-card');

        cards.forEach(card => {
            const searchData = card.getAttribute('data-search').toLowerCase();
            if (searchData.includes(searchTerm)) {
                card.classList.remove('hidden');
                card.classList.add('filtered-in');
                hasVisibleCards = true;
            } else {
                card.classList.add('hidden');
                card.classList.remove('filtered-in');
            }
        });

        // Hide/show section based on whether it has visible cards
        if (hasVisibleCards) {
            section.style.display = '';
        } else {
            section.style.display = 'none';
        }
    });
}

// Launch Application (adapted for Electron)
async function launchApp(appPath) {
    // Show loading overlay
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');

    try {
        // Send request to Express backend to launch the app
        const response = await fetch('/launch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                app_path: appPath
            })
        });

        const result = await response.json();

        if (result.success) {
            // Success feedback - shorter timeout for better UX
            setTimeout(() => {
                overlay.classList.remove('active');
            }, 800);
        } else {
            // Error handling
            overlay.classList.remove('active');
            alert(`Erro ao abrir aplicação: ${result.error}`);
        }
    } catch (error) {
        overlay.classList.remove('active');
        alert(`Erro de conexão: ${error.message}\nVerifique se o servidor interno está funcionando.`);
    }
}

// Launch STM32 Cube Programmer
async function launchSTM32Programmer() {
    // Show loading overlay
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');

    try {
        // Send request to Express backend to launch STM32 Cube Programmer
        const response = await fetch('/launch-stm32', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (result.success) {
            // Success feedback - shorter timeout for better UX
            setTimeout(() => {
                overlay.classList.remove('active');
            }, 800);
        } else {
            // Error handling
            overlay.classList.remove('active');
            alert(`Erro ao abrir STM32 Cube Programmer: ${result.error}`);
        }
    } catch (error) {
        overlay.classList.remove('active');
        alert(`Erro de conexão: ${error.message}\nVerifique se o servidor interno está funcionando.`);
    }
}

// Keyboard Shortcuts
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+F or F3 for search
        if ((e.ctrlKey && e.key === 'f') || e.key === 'F3') {
            e.preventDefault();
            const searchBox = document.getElementById('searchBox');
            searchBox.focus();
            searchBox.select();
        }

        // Escape to clear search
        if (e.key === 'Escape') {
            const searchBox = document.getElementById('searchBox');
            if (document.activeElement === searchBox) {
                searchBox.value = '';
                performSearch();
                searchBox.blur();
            }
        }

        // F11 for fullscreen (handled by Electron)
        if (e.key === 'F11') {
            e.preventDefault();
            toggleFullscreen();
        }
    });
}

// Toggle Fullscreen Mode
function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            console.log(`Error attempting to enable fullscreen: ${err.message}`);
        });
    } else {
        document.exitFullscreen();
    }
}

// Auto-hide loading overlay if stuck
setTimeout(() => {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay && overlay.classList.contains('active')) {
        overlay.classList.remove('active');
    }
}, 5000);

// Add visual feedback for app card clicks
document.querySelectorAll('.app-card').forEach(card => {
    card.addEventListener('click', function() {
        // Add visual feedback for clicking
        this.style.transform = 'translateY(-4px) scale(0.98)';
        setTimeout(() => {
            this.style.transform = '';
        }, 150);
    });
});

// Category animation on page load
window.addEventListener('load', function() {
    const sections = document.querySelectorAll('.category-section');
    sections.forEach((section, index) => {
        section.style.animationDelay = `${index * 0.1}s`;
    });
});

// Add hover effects
function addHoverEffects() {
    const cards = document.querySelectorAll('.app-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            // Visual feedback is handled by CSS
            // Simple hover effect without modal
        });
    });
}

// Initialize hover effects
addHoverEffects();

// Console welcome message (Electron version)
console.log('%c SETERA Ferramentas v1.4 - Desktop App ', 'background: #0984e3; color: white; font-size: 16px; padding: 5px 10px; border-radius: 5px;');
console.log('%c Dashboard Electron carregado com sucesso! ', 'color: #74b9ff; font-size: 12px;');
console.log('%c Atalhos: Ctrl+F (busca), F11 (tela cheia) ', 'color: #a0a0a0; font-size: 10px;');
console.log('%c Desktop app - nenhum servidor externo necessário ', 'color: #00b894; font-size: 10px;');