(function () {
    'use strict';

    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', function (e) {
            const targetSelector = this.getAttribute('href');
            const target = targetSelector ? document.querySelector(targetSelector) : null;
            if (!target) return;
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth' });
        });
    });

    const chatbot = document.getElementById('chatbot') || document.getElementById('chatbot-enhanced');
    if (chatbot) {
        const observer = new MutationObserver(() => {
            chatbot.scrollTop = chatbot.scrollHeight;
        });
        observer.observe(chatbot, { childList: true, subtree: true });
    }

    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            document.querySelector('#Generate, #send-btn')?.click();
        }

        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            document.querySelector('#search_chat, #search-input')?.focus();
        }
    });

    window.showToast = function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bg = type === 'success' ? '#4CAF50' : type === 'error' ? '#F44336' : '#2196F3';
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = [
            'position:fixed',
            'bottom:20px',
            'right:20px',
            'padding:15px 20px',
            `background:${bg}`,
            'color:#fff',
            'border-radius:8px',
            'box-shadow:0 4px 12px rgba(0,0,0,0.3)',
            'z-index:10000',
            'animation:slideIn 0.3s ease-out'
        ].join(';');
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    window.copyToClipboard = function copyToClipboard(text) {
        if (!navigator.clipboard) {
            window.showToast('Clipboard API unavailable', 'error');
            return;
        }
        navigator.clipboard.writeText(text)
            .then(() => window.showToast('Copied to clipboard!', 'success'))
            .catch(() => window.showToast('Copy failed', 'error'));
    };

    window.setLoading = function setLoading(element, isLoading) {
        if (!element) return;
        if (isLoading) {
            element.classList.add('generating');
            element.setAttribute('disabled', 'true');
        } else {
            element.classList.remove('generating');
            element.removeAttribute('disabled');
        }
    };
})();
