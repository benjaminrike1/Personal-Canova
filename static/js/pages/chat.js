// Coaching chat logic
let currentConversationId = null;
let sending = false;

document.addEventListener('DOMContentLoaded', async () => {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const newBtn = document.getElementById('new-chat');

    sendBtn.addEventListener('click', sendMessage);
    newBtn.addEventListener('click', startNewChat);

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    // Load most recent conversation or start new
    await loadConversations();
});

async function loadConversations() {
    try {
        const convs = await Coach.get('/chat/conversations');
        if (convs.length > 0) {
            await loadConversation(convs[0].id);
        }
    } catch (e) {
        console.error('Failed to load conversations:', e);
    }
}

async function loadConversation(id) {
    try {
        const conv = await Coach.get(`/chat/conversations/${id}`);
        currentConversationId = id;
        renderMessages(conv.messages || []);
    } catch (e) {
        console.error('Failed to load conversation:', e);
    }
}

async function startNewChat() {
    try {
        const conv = await Coach.post('/chat/conversations', {});
        currentConversationId = conv.id;
        renderMessages([]);
        document.getElementById('chat-input').focus();
    } catch (e) {
        console.error('Failed to create conversation:', e);
    }
}

async function sendMessage() {
    if (sending) return;

    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    // Create conversation if needed
    if (!currentConversationId) {
        try {
            const conv = await Coach.post('/chat/conversations', {});
            currentConversationId = conv.id;
        } catch (e) {
            console.error('Failed to create conversation:', e);
            return;
        }
    }

    // Show user message immediately
    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';

    // Show typing indicator
    const typingEl = appendMessage('assistant', '<div class="loading">Thinking</div>');

    sending = true;
    document.getElementById('chat-send').disabled = true;

    try {
        const result = await Coach.post(
            `/chat/conversations/${currentConversationId}/messages`,
            { content: text }
        );

        // Replace typing indicator with actual response
        typingEl.innerHTML = formatMarkdown(result.response);

        // Show notebook entries if any
        if (result.notebook_entries && result.notebook_entries.length > 0) {
            const noteHtml = result.notebook_entries.map(e =>
                `<span class="badge badge-blue">${e.category}</span> ${e.content}`
            ).join('<br>');
            typingEl.innerHTML += `<div class="mt-sm text-sm text-muted" style="border-top: 1px solid var(--border); padding-top: 8px;">
                <strong>Noted:</strong> ${noteHtml}
            </div>`;
        }

        // Show plan adjustments if any
        if (result.plan_adjustments && result.plan_adjustments.length > 0) {
            typingEl.innerHTML += `<div class="mt-sm text-sm" style="border-top: 1px solid var(--border); padding-top: 8px;">
                <span class="badge badge-yellow">Plan updated</span> ${result.plan_adjustments.length} change(s) applied
            </div>`;
        }
    } catch (e) {
        typingEl.innerHTML = '<span class="text-red">Failed to get response. Please try again.</span>';
        console.error('Chat error:', e);
    }

    sending = false;
    document.getElementById('chat-send').disabled = false;
    scrollToBottom();
}

function appendMessage(role, content) {
    const container = document.getElementById('chat-messages');

    // Remove placeholder if present
    const placeholder = container.querySelector('.text-muted');
    if (placeholder && !placeholder.closest('.chat-msg')) {
        placeholder.remove();
    }

    const msg = document.createElement('div');
    msg.className = `chat-msg chat-msg-${role}`;
    msg.innerHTML = role === 'user' ? escapeHtml(content) : content;
    container.appendChild(msg);
    scrollToBottom();
    return msg;
}

function renderMessages(messages) {
    const container = document.getElementById('chat-messages');
    if (messages.length === 0) {
        container.innerHTML = '<div class="text-muted" style="text-align:center; padding: 40px 0;">Start a conversation with your coach.</div>';
        return;
    }

    container.innerHTML = '';
    for (const msg of messages) {
        const el = document.createElement('div');
        el.className = `chat-msg chat-msg-${msg.role}`;
        el.innerHTML = msg.role === 'user' ? escapeHtml(msg.content) : formatMarkdown(msg.content);
        container.appendChild(el);
    }
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdown(text) {
    // Simple markdown-ish formatting
    return text
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}
