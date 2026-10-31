/**
 * ==============================================================================
 * CodeFix AI — Client-Side Workspace Controller
 * ==============================================================================
 */

// Application State
const state = {
    currentMode: 'write',
    selectedLanguage: 'python',
    sessionId: null,
    latestCode: '',
    chatHistory: [],
    maxInputChars: 10000
};

// Preset Examples for Instant Demo
const PRESET_EXAMPLES = {
    calc: {
        mode: 'write',
        language: 'python',
        prompt: 'Create a Python calculator using functions that supports addition, subtraction, multiplication, and division. Include zero-division handling and a simple command-line loop.',
        code: '',
        error: ''
    },
    syntax_bug: {
        mode: 'debug',
        language: 'python',
        prompt: 'The function fails when running with empty lists and has a syntax issue in the condition.',
        code: 'def calculate_average(numbers):\n    total = 0\n    for n in numbers\n        total += n\n    return total / len(numbers)',
        error: 'SyntaxError: expected \':\' at line 3'
    },
    refactor: {
        mode: 'improve',
        language: 'python',
        prompt: 'Refactor this code to be more Pythonic and memory-efficient using list comprehension or generator expressions, and add type hints.',
        code: 'def get_even_squares(numbers):\n    result = []\n    for x in numbers:\n        if x % 2 == 0:\n            result.append(x * x)\n    return result',
        error: ''
    },
    explain_quick: {
        mode: 'explain',
        language: 'python',
        prompt: 'Explain how this memoized Fibonacci function works and analyze its time and space complexity compared to naive recursion.',
        code: 'def fibonacci(n, memo={}):\n    if n in memo:\n        return memo[n]\n    if n <= 1:\n        return n\n    memo[n] = fibonacci(n - 1, memo) + fibonacci(n - 2, memo)\n    return memo[n]',
        error: ''
    }
};

// Document Initialization
document.addEventListener('DOMContentLoaded', () => {
    initSession();
    initModeTabs();
    initLanguageSelector();
    initTextareaTabKey();
    initCharCounters();
    initSidebar();
    checkServiceStatus();
});

/**
 * Initialize or retrieve session ID
 */
function initSession() {
    const sessionInput = document.getElementById('session-id');
    if (sessionInput && sessionInput.value) {
        state.sessionId = sessionInput.value;
    } else {
        state.sessionId = 'sess_' + Math.random().toString(36).substring(2, 12);
        if (sessionInput) sessionInput.value = state.sessionId;
    }
}

/**
 * Setup mode tabs (Write, Debug, Improve, Explain)
 */
function initModeTabs() {
    const tabs = document.querySelectorAll('.mode-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const mode = tab.dataset.mode;
            setWorkspaceMode(mode);
        });
    });
}

/**
 * Change workspace mode and reconfigure form fields
 */
function setWorkspaceMode(mode) {
    state.currentMode = mode;
    document.getElementById('current-mode').value = mode;

    // Update active tab buttons
    document.querySelectorAll('.mode-tab').forEach(t => {
        const isActive = t.dataset.mode === mode;
        t.classList.toggle('active', isActive);
        t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    // Update sidebar menu items
    document.querySelectorAll('.sidebar-menu .menu-item').forEach(m => {
        m.classList.toggle('active', m.dataset.mode === mode);
    });

    // Elements
    const groupCode = document.getElementById('group-code');
    const groupError = document.getElementById('group-error');
    const groupPrompt = document.getElementById('group-prompt');
    const promptLabel = document.getElementById('prompt-label-text');
    const promptInput = document.getElementById('prompt-input');
    const codeRequiredStar = document.getElementById('code-required-star');
    const btnSubmit = document.getElementById('btn-submit');
    const btnSubmitText = document.getElementById('btn-submit-text');
    const btnAstCheck = document.getElementById('btn-ast-check');
    const inputPaneHeading = document.getElementById('input-pane-heading');

    // Configure fields according to mode
    if (mode === 'write') {
        inputPaneHeading.textContent = 'Task Prompt & Requirements';
        groupCode.classList.add('hidden');
        groupError.classList.add('hidden');
        promptLabel.textContent = 'Task Description';
        promptInput.placeholder = "Describe what you want the AI to create, e.g.: 'Create a Python calculator using functions that supports addition, subtraction, multiplication, and division.'";
        promptInput.required = true;
        btnSubmitText.textContent = 'Generate Code';
        btnAstCheck.classList.add('hidden');
    } else if (mode === 'debug') {
        inputPaneHeading.textContent = 'Code Debugging & Diagnostics';
        groupCode.classList.remove('hidden');
        groupError.classList.remove('hidden');
        promptLabel.textContent = 'Describe the Issue / Unexpected Behavior';
        promptInput.placeholder = 'Explain what unexpected behavior or wrong output occurs...';
        promptInput.required = false;
        codeRequiredStar.classList.remove('hidden');
        btnSubmitText.textContent = 'Debug & Fix Code';
        if (state.selectedLanguage === 'python') {
            btnAstCheck.classList.remove('hidden');
        } else {
            btnAstCheck.classList.add('hidden');
        }
    } else if (mode === 'improve') {
        inputPaneHeading.textContent = 'Code Improvement & Refactoring';
        groupCode.classList.remove('hidden');
        groupError.classList.add('hidden');
        promptLabel.textContent = 'Optimization / Refactoring Goals';
        promptInput.placeholder = 'Specify improvements (e.g., readability, performance, PEP 8, type hints, modern idioms)...';
        promptInput.required = false;
        codeRequiredStar.classList.remove('hidden');
        btnSubmitText.textContent = 'Improve Code';
        btnAstCheck.classList.add('hidden');
    } else if (mode === 'explain') {
        inputPaneHeading.textContent = 'Code Structure & Explanation';
        groupCode.classList.remove('hidden');
        groupError.classList.add('hidden');
        promptLabel.textContent = 'Specific Questions or Focus Areas (Optional)';
        promptInput.placeholder = 'Specify what you want explained (e.g., time complexity, memory footprint, algorithm walk)...';
        promptInput.required = false;
        codeRequiredStar.classList.remove('hidden');
        btnSubmitText.textContent = 'Explain Code';
        btnAstCheck.classList.add('hidden');
    }
}

function switchModeFromSidebar(mode) {
    setWorkspaceMode(mode);
}

/**
 * Language selector change handler
 */
function initLanguageSelector() {
    const langSelect = document.getElementById('language-select');
    if (langSelect) {
        langSelect.addEventListener('change', (e) => {
            state.selectedLanguage = e.target.value;
            const btnAstCheck = document.getElementById('btn-ast-check');
            if (state.currentMode === 'debug' && state.selectedLanguage === 'python') {
                btnAstCheck.classList.remove('hidden');
            } else {
                btnAstCheck.classList.add('hidden');
            }
        });
    }
}

/**
 * Support Tab key inside code textareas
 */
function initTextareaTabKey() {
    const textareas = document.querySelectorAll('.code-editor, .code-textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
                textarea.selectionStart = textarea.selectionEnd = start + 4;
                updateCharCounter();
            }
        });
    });
}

/**
 * Character counter update
 */
function initCharCounters() {
    const promptInput = document.getElementById('prompt-input');
    const codeInput = document.getElementById('code-input');
    const errorInput = document.getElementById('error-input');

    [promptInput, codeInput, errorInput].forEach(elem => {
        if (elem) elem.addEventListener('input', updateCharCounter);
    });
}

function updateCharCounter() {
    const promptLen = (document.getElementById('prompt-input')?.value || '').length;
    const codeLen = (document.getElementById('code-input')?.value || '').length;
    const errorLen = (document.getElementById('error-input')?.value || '').length;
    const total = promptLen + codeLen + errorLen;

    const counter = document.getElementById('char-counter');
    if (counter) {
        counter.textContent = `${total} / ${state.maxInputChars}`;
        if (total > state.maxInputChars) {
            counter.style.color = 'var(--danger)';
        } else {
            counter.style.color = 'var(--text-muted)';
        }
    }
}

/**
 * Load Preset Sample Prompt
 */
function loadPresetExample(presetKey) {
    if (!presetKey || !PRESET_EXAMPLES[presetKey]) return;
    const sample = PRESET_EXAMPLES[presetKey];

    // Select mode and language
    setWorkspaceMode(sample.mode);
    const langSelect = document.getElementById('language-select');
    if (langSelect) {
        langSelect.value = sample.language;
        state.selectedLanguage = sample.language;
    }

    // Set values
    const promptInput = document.getElementById('prompt-input');
    const codeInput = document.getElementById('code-input');
    const errorInput = document.getElementById('error-input');

    if (promptInput) promptInput.value = sample.prompt;
    if (codeInput) codeInput.value = sample.code;
    if (errorInput) errorInput.value = sample.error;

    updateCharCounter();
    showToast(`Loaded sample prompt: ${presetKey.replace('_', ' ')}`, 'info');
}

/**
 * Check Ollama and IBM Db2 Status via API
 */
async function checkServiceStatus() {
    const ollamaDot = document.getElementById('ollama-dot');
    const modelBadge = document.getElementById('nav-model-name');
    
    try {
        const response = await fetch('/api/status');
        if (response.ok) {
            const data = await response.json();
            if (data.ollama_online) {
                ollamaDot.className = 'status-dot status-online';
                ollamaDot.parentElement.title = `Ollama Online (${data.model})`;
            } else {
                ollamaDot.className = 'status-dot status-offline';
                ollamaDot.parentElement.title = 'Ollama Service Offline (Run: ollama serve)';
            }
            if (modelBadge && data.model) {
                modelBadge.textContent = data.model;
            }
        } else {
            ollamaDot.className = 'status-dot status-offline';
        }
    } catch (err) {
        if (ollamaDot) ollamaDot.className = 'status-dot status-offline';
    }
}

/**
 * Form Submission (Primary Workspace Action)
 */
async function handleFormSubmit(event) {
    event.preventDefault();

    const mode = state.currentMode;
    const language = state.selectedLanguage;
    const prompt = document.getElementById('prompt-input').value.trim();
    const code = document.getElementById('code-input')?.value || '';
    const errorMsg = document.getElementById('error-input')?.value || '';

    // Validation
    if (mode === 'write' && !prompt) {
        showToast('Please provide a task description to generate code.', 'error');
        document.getElementById('prompt-input').focus();
        return;
    }
    if ((mode === 'debug' || mode === 'improve' || mode === 'explain') && !code.trim()) {
        showToast(`Please paste your existing ${language} source code.`, 'error');
        document.getElementById('code-input').focus();
        return;
    }

    // Determine target API endpoint
    let endpoint = '/generate';
    if (mode === 'debug') endpoint = '/analyze';
    else if (mode === 'improve') endpoint = '/improve';
    else if (mode === 'explain') endpoint = '/explain';

    const payload = {
        mode: mode,
        language: language,
        prompt: prompt,
        code: code,
        error_message: errorMsg,
        session_id: state.sessionId
    };

    setLoadingState(true, getLoadingMessage(mode));

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        setLoadingState(false);

        if (!res.ok) {
            const msg = data.error || data.message || `Request failed with status ${res.status}`;
            showToast(msg, 'error');
            renderErrorInOutput(msg, data.suggestions);
            return;
        }

        renderResult(data);
        showToast('Code generated successfully!', 'success');
    } catch (err) {
        setLoadingState(false);
        const errMsg = 'Network or server communication error. Please ensure the Flask app and Ollama are running.';
        showToast(errMsg, 'error');
        renderErrorInOutput(errMsg, [
            'Check that Ollama is running (`ollama serve`).',
            'Ensure model is downloaded (`ollama pull qwen2.5-coder:1.5b`).',
            'Check terminal for any backend exceptions.'
        ]);
    }
}

/**
 * Deterministic Python Static AST Check Only
 */
async function runStaticCheckOnly() {
    const code = document.getElementById('code-input')?.value || '';
    if (!code.trim()) {
        showToast('Paste Python code first to run static AST check.', 'error');
        return;
    }

    setLoadingState(true, 'Running deterministic Python AST static analyzer...');

    try {
        const res = await fetch('/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                mode: 'debug',
                language: 'python',
                code: code,
                prompt: 'Static syntax check request',
                static_only: true,
                session_id: state.sessionId
            })
        });

        const data = await res.json();
        setLoadingState(false);

        if (res.ok) {
            renderResult(data);
            showToast('Static AST check completed.', 'info');
        } else {
            showToast(data.error || 'Static check failed.', 'error');
        }
    } catch (e) {
        setLoadingState(false);
        showToast('Static check request failed.', 'error');
    }
}

/**
 * Handle Conversational Follow-Up Questions
 */
async function handleFollowUpSubmit(event) {
    event.preventDefault();
    const input = document.getElementById('followup-input');
    const message = input.value.trim();
    if (!message) return;

    // Append user bubble to thread
    appendChatBubble('user', message);
    input.value = '';

    const payload = {
        message: message,
        current_code: state.latestCode,
        language: state.selectedLanguage,
        session_id: state.sessionId,
        history: state.chatHistory
    };

    try {
        const btn = document.getElementById('btn-followup-submit');
        btn.disabled = true;

        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        btn.disabled = false;

        if (res.ok) {
            appendChatBubble('agent', data.reply || data.explanation);
            if (data.generated_code) {
                // Update code display if modified
                state.latestCode = data.generated_code;
                const codeBlock = document.getElementById('code-block');
                codeBlock.textContent = data.generated_code;
                Prism.highlightElement(codeBlock);
            }
            // Update local memory
            state.chatHistory.push({ role: 'user', content: message });
            state.chatHistory.push({ role: 'assistant', content: data.reply || data.explanation });
        } else {
            appendChatBubble('agent', `⚠️ ${data.error || 'Could not process follow-up.'}`);
        }
    } catch (err) {
        document.getElementById('btn-followup-submit').disabled = false;
        appendChatBubble('agent', '⚠️ Error contacting AI service.');
    }
}

function applyQuickChip(promptText) {
    const input = document.getElementById('followup-input');
    if (input) {
        input.value = promptText;
        input.focus();
    }
}

function appendChatBubble(role, content) {
    const thread = document.getElementById('chat-thread');
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = content;
    thread.appendChild(bubble);
    thread.scrollTop = thread.scrollHeight;
}

/**
 * Render Structured Result
 */
function renderResult(data) {
    const emptyCard = document.getElementById('output-empty');
    const resultContainer = document.getElementById('output-result');

    emptyCard.classList.add('hidden');
    resultContainer.classList.remove('hidden');

    // Badges
    document.getElementById('res-mode-badge').textContent = (data.mode || state.currentMode).toUpperCase();
    document.getElementById('res-lang-badge').textContent = data.language || state.selectedLanguage;
    document.getElementById('res-model-badge').textContent = data.model_name || 'qwen2.5-coder:1.5b';

    // Diagnostics Panel
    const diagPanel = document.getElementById('diagnostics-panel');
    const diagContent = document.getElementById('diagnostics-content');
    if (data.diagnostics && data.diagnostics.length > 0) {
        diagPanel.classList.remove('hidden');
        diagContent.innerHTML = data.diagnostics.map(d => `<div class="diag-item"><i class="fa-solid fa-chevron-right"></i> ${escapeHtml(d)}</div>`).join('');
    } else {
        diagPanel.classList.add('hidden');
    }

    // Code Block
    const codeBlock = document.getElementById('code-block');
    const langTag = document.getElementById('code-lang-tag');
    const code = data.generated_code || data.code || '# No code output produced';
    state.latestCode = code;

    langTag.textContent = data.language || state.selectedLanguage;
    codeBlock.className = `language-${data.language || state.selectedLanguage}`;
    codeBlock.textContent = code;
    Prism.highlightElement(codeBlock);

    // Explanation
    const explanationContent = document.getElementById('explanation-content');
    explanationContent.innerHTML = formatMarkdown(data.explanation || 'No explanation provided.');

    // Suggestions / Next Steps
    const suggestionsPanel = document.getElementById('suggestions-panel');
    const suggestionsContent = document.getElementById('suggestions-content');
    if (data.suggestions && data.suggestions.length > 0) {
        suggestionsPanel.classList.remove('hidden');
        suggestionsContent.innerHTML = '<ul>' + data.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('') + '</ul>';
    } else {
        suggestionsPanel.classList.add('hidden');
    }

    // Scroll right pane to top
    document.querySelector('.output-pane').scrollTop = 0;
}

/**
 * Render Friendly Error in Result Card
 */
function renderErrorInOutput(errorMessage, suggestions) {
    const emptyCard = document.getElementById('output-empty');
    const resultContainer = document.getElementById('output-result');
    const diagPanel = document.getElementById('diagnostics-panel');
    const diagContent = document.getElementById('diagnostics-content');
    const codeBlock = document.getElementById('code-block');
    const explanationContent = document.getElementById('explanation-content');

    emptyCard.classList.add('hidden');
    resultContainer.classList.remove('hidden');

    diagPanel.classList.remove('hidden');
    diagContent.innerHTML = `<span class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(errorMessage)}</span>`;

    codeBlock.textContent = `# An error occurred while communicating with the AI service.\n# Details:\n# ${errorMessage}`;
    Prism.highlightElement(codeBlock);

    let html = `<p class="text-secondary">${escapeHtml(errorMessage)}</p>`;
    if (suggestions && suggestions.length > 0) {
        html += '<h5 class="mt-4"><i class="fa-solid fa-screwdriver-wrench"></i> Suggested Steps:</h5><ul>';
        html += suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('');
        html += '</ul>';
    }
    explanationContent.innerHTML = html;
}

/**
 * Loading State UI Management
 */
function setLoadingState(isLoading, message = 'Processing...') {
    const loadingElem = document.getElementById('output-loading');
    const emptyElem = document.getElementById('output-empty');
    const resultElem = document.getElementById('output-result');
    const btnSubmit = document.getElementById('btn-submit');
    const loadingSubtitle = document.getElementById('loading-subtitle');

    if (isLoading) {
        loadingElem.classList.remove('hidden');
        emptyElem.classList.add('hidden');
        resultElem.classList.add('hidden');
        if (loadingSubtitle) loadingSubtitle.textContent = message;
        if (btnSubmit) btnSubmit.disabled = true;
    } else {
        loadingElem.classList.add('hidden');
        if (btnSubmit) btnSubmit.disabled = false;
    }
}

function getLoadingMessage(mode) {
    switch (mode) {
        case 'write': return 'Formulating architecture & generating clean code with Ollama...';
        case 'debug': return 'Running Python AST static analyzer & generating root-cause fix...';
        case 'improve': return 'Analyzing algorithmic complexity & optimizing code structure...';
        case 'explain': return 'Walking abstract syntax tree and breaking down logic...';
        default: return 'Processing request with local AI model...';
    }
}

/**
 * Copy Generated Code to Clipboard
 */
function copyGeneratedCode() {
    if (!state.latestCode) {
        showToast('No code available to copy.', 'error');
        return;
    }
    navigator.clipboard.writeText(state.latestCode).then(() => {
        showToast('Code copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy code.', 'error');
    });
}

function copySnippetText(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy.', 'error');
    });
}

/**
 * Download Code Snippet as File
 */
function downloadCodeSnippet() {
    if (!state.latestCode) {
        showToast('No code to download.', 'error');
        return;
    }

    const extMap = {
        python: 'py',
        javascript: 'js',
        java: 'java',
        cpp: 'cpp'
    };
    const ext = extMap[state.selectedLanguage] || 'txt';
    const filename = `codefix_solution_${Date.now()}.${ext}`;

    const blob = new Blob([state.latestCode], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${filename}`, 'success');
}

/**
 * Clear Form Fields
 */
function resetForm() {
    document.getElementById('codefix-form').reset();
    document.getElementById('current-mode').value = state.currentMode;
    updateCharCounter();
    showToast('Workspace form cleared.', 'info');
}

function clearCodeField() {
    const codeInput = document.getElementById('code-input');
    if (codeInput) {
        codeInput.value = '';
        updateCharCounter();
    }
}

/**
 * Filter History Records on History Page
 */
function filterHistory() {
    const modeFilter = document.getElementById('filter-mode')?.value || 'all';
    const langFilter = document.getElementById('filter-lang')?.value || 'all';
    const searchTerm = (document.getElementById('history-search')?.value || '').toLowerCase();

    const cards = document.querySelectorAll('.history-card');
    let visibleCount = 0;

    cards.forEach(card => {
        const mode = card.dataset.mode;
        const lang = card.dataset.lang;
        const text = card.textContent.toLowerCase();

        const matchMode = modeFilter === 'all' || mode === modeFilter;
        const matchLang = langFilter === 'all' || lang === langFilter;
        const matchSearch = !searchTerm || text.includes(searchTerm);

        if (matchMode && matchLang && matchSearch) {
            card.classList.remove('hidden');
            visibleCount++;
        } else {
            card.classList.add('hidden');
        }
    });
}

/**
 * Delete History Record via API
 */
async function deleteHistoryItem(recordId) {
    if (!confirm('Are you sure you want to delete this saved history record?')) return;

    try {
        const res = await fetch(`/history/${recordId}/delete`, {
            method: 'POST',
            headers: { 'Accept': 'application/json' }
        });

        if (res.ok) {
            const card = document.getElementById(`record-card-${recordId}`);
            if (card) card.remove();
            showToast('Record deleted.', 'success');
        } else {
            showToast('Could not delete record.', 'error');
        }
    } catch (e) {
        showToast('Error deleting record.', 'error');
    }
}

/**
 * Toast Notification System
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    if (type === 'error') icon = 'fa-circle-exclamation';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/**
 * Mobile Sidebar Navigation
 */
function initSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('app-sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebar.classList.toggle('collapsed');
        });
    }
}

/**
 * Info Modal
 */
function showInfoModal() {
    document.getElementById('info-modal')?.classList.remove('hidden');
}

function closeInfoModal() {
    document.getElementById('info-modal')?.classList.add('hidden');
}

function closeModalOnBackdrop(e) {
    if (e.target.id === 'info-modal') {
        closeInfoModal();
    }
}

/**
 * Helper: Escape HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Helper: Minimal Markdown to HTML Converter
 */
function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4 class="mt-3">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 class="mt-3">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 class="mt-3">$1</h2>');

    // Bold & Italic
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline Code
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
}

