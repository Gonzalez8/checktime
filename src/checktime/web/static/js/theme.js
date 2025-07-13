/* CheckTime - Theme Management */

class ThemeManager {
    constructor() {
        this.themeToggle = document.getElementById('themeToggle');
        this.themeIcon = this.themeToggle?.querySelector('.theme-icon');
        this.currentTheme = this.getStoredTheme() || this.getSystemTheme();
        
        this.init();
    }

    init() {
        // Apply initial theme
        this.applyTheme(this.currentTheme);
        
        // Set up event listeners
        if (this.themeToggle) {
            this.themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Listen for system theme changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)')
                .addEventListener('change', (e) => {
                    if (!this.getStoredTheme()) {
                        this.applyTheme(e.matches ? 'dark' : 'light');
                    }
                });
        }
    }

    getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    setStoredTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    applyTheme(theme) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        
        if (this.themeToggle) {
            this.themeToggle.classList.toggle('dark', theme === 'dark');
            
            if (this.themeIcon) {
                this.themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
        }

        // Update Bootstrap components that need theme-specific classes
        this.updateBootstrapClasses(theme);
        
        // Dispatch custom event for other components to listen to
        document.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { theme } 
        }));
    }

    updateBootstrapClasses(theme) {
        // Update navbar
        const navbar = document.querySelector('.navbar-modern');
        if (navbar) {
            if (theme === 'dark') {
                navbar.classList.add('navbar-dark');
                navbar.classList.remove('navbar-light');
            } else {
                navbar.classList.add('navbar-light');
                navbar.classList.remove('navbar-dark');
            }
        }

        // Update modals
        const modals = document.querySelectorAll('.modal-content');
        modals.forEach(modal => {
            if (theme === 'dark') {
                modal.style.backgroundColor = 'var(--gray-800)';
                modal.style.color = 'var(--gray-200)';
            } else {
                modal.style.backgroundColor = '';
                modal.style.color = '';
            }
        });

        // Update dropdowns
        const dropdowns = document.querySelectorAll('.dropdown-menu');
        dropdowns.forEach(dropdown => {
            if (theme === 'dark') {
                dropdown.classList.add('dropdown-menu-dark');
            } else {
                dropdown.classList.remove('dropdown-menu-dark');
            }
        });
    }

    toggleTheme() {
        const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        this.applyTheme(newTheme);
        this.setStoredTheme(newTheme);
    }

    setTheme(theme) {
        this.applyTheme(theme);
        this.setStoredTheme(theme);
    }
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}