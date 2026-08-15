document.addEventListener('DOMContentLoaded', () => {
    // Theme toggle
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }

    // Restore theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // AI Assistant Drawer Toggle
    const aiBtn = document.getElementById('ai-chat-trigger');
    const aiBox = document.getElementById('ai-chat-box');
    const aiClose = document.getElementById('ai-chat-close');
    const aiSend = document.getElementById('ai-send-btn');
    const aiInput = document.getElementById('ai-input');
    const aiMessages = document.getElementById('ai-messages');

    function openAiBox() {
        aiBox.hidden = false;
        aiBox.style.display = 'flex';
        aiBtn.setAttribute('aria-expanded', 'true');
        aiInput.focus();
    }
    function closeAiBox() {
        aiBox.hidden = true;
        aiBox.style.display = 'none';
        aiBtn.setAttribute('aria-expanded', 'false');
        aiBtn.focus();
    }

    if (aiBtn && aiBox) {
        aiBtn.addEventListener('click', () => {
            if (aiBox.style.display === 'flex') closeAiBox(); else openAiBox();
        });
        if (aiClose) {
            aiClose.addEventListener('click', closeAiBox);
        }
        aiBox.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeAiBox();
        });
    }

    if (aiSend && aiInput && aiMessages) {
        const handleSend = async () => {
            const query = aiInput.value.trim();
            if (!query) return;

            // Render User Message
            const uMsg = document.createElement('div');
            uMsg.className = 'chat-msg user';
            uMsg.textContent = query;
            aiMessages.appendChild(uMsg);
            aiInput.value = '';
            aiMessages.scrollTop = aiMessages.scrollHeight;

            // Call AI Endpoint
            try {
                const response = await fetch('/api/v1/ai/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: query })
                });
                const data = await response.json();

                const bMsg = document.createElement('div');
                bMsg.className = 'chat-msg bot';
                bMsg.textContent = data.response || "No response received";
                aiMessages.appendChild(bMsg);
                aiMessages.scrollTop = aiMessages.scrollHeight;
            } catch (err) {
                console.error(err);
            }
        };

        aiSend.addEventListener('click', handleSend);
        aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSend();
        });
    }

    // PWA Service Worker Registration
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/js/sw.js')
            .then(reg => console.log('PWA SW Registered', reg))
            .catch(err => console.error('PWA SW Error', err));
    }
});
