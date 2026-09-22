let activeCase = null;
let chatHistory = [
    { sender: 'bot', text: 'Welcome to Aegis. Please describe your symptoms, including their severity, duration, and if they were triggered by a specific event.' }
];
let savedCases = [];
let isListening = false;
let isSpeaking = false;
let synthUtterance = null;

const SVG_EYE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
const SVG_EYE_OFF = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>`;

document.addEventListener('DOMContentLoaded', () => {
    loadCasesFromStorage();
    initTheme();
    initSidebarToggle();

    document.querySelectorAll('.report-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => toggleReportPanel());
    });

    const closeBtn = document.getElementById('close-report-btn');
    if (closeBtn) closeBtn.addEventListener('click', () => toggleReportPanel(false));

    initResizeHandle();
    initSpeechSynthesis();
    initSpeechRecognition();
    initChatSubmit();
    initNewCaseBtn();

    toggleReportPanel(true);
});

function initResizeHandle() {
    const handle = document.getElementById('panel-resize-handle');
    const leftPanel = document.querySelector('.intake-panel');
    const rightPanel = document.querySelector('.report-panel');
    const grid = document.querySelector('.app-grid');

    if (!handle || !leftPanel || !rightPanel || !grid) return;

    let isDragging = false;

    handle.addEventListener('mousedown', (e) => {
        isDragging = true;
        document.body.style.cursor = 'col-resize';
        handle.classList.add('dragging');
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;

        const gridRect = grid.getBoundingClientRect();
        const leftWidth = e.clientX - gridRect.left;
        const gridWidth = gridRect.width;

        if (leftWidth >= 300 && (gridWidth - leftWidth) >= 300) {
            const leftPct = (leftWidth / gridWidth) * 100;
            leftPanel.style.flex = `${leftPct} 1 0%`;
            rightPanel.style.flex = `${100 - leftPct} 1 0%`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            document.body.style.cursor = '';
            handle.classList.remove('dragging');
        }
    });
}

function initTheme() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (!themeBtn) return;

    const sun = document.querySelector('.sun-icon');
    const moon = document.querySelector('.moon-icon');

    const updateTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        if (sun && moon) {
            sun.style.display = theme === 'dark' ? 'none' : 'block';
            moon.style.display = theme === 'dark' ? 'block' : 'none';
        }
    };

    updateTheme(localStorage.getItem('theme') || 'light');

    themeBtn.onclick = () => {
        updateTheme(
            document.documentElement.getAttribute('data-theme') === 'dark'
                ? 'light'
                : 'dark'
        );
    };
}

function initSidebarToggle() {
    const btn = document.getElementById('sidebar-toggle-btn');
    const layout = document.querySelector('.app-layout');

    if (btn && layout) {
        btn.onclick = () => layout.classList.toggle('sidebar-collapsed');
    }
}

function initSpeechRecognition() {
    const voiceBtn = document.getElementById('voice-btn');
    const voiceInd = document.getElementById('voice-indicator');
    const userInput = document.getElementById('user-input');

    if (!voiceBtn || !voiceInd || !userInput) return;

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        voiceBtn.style.display = 'none';
        return;
    }

    let recorder = null;
    let stream = null;
    let chunks = [];

    const mime =
        ['audio/webm;codecs=opus', 'audio/webm'].find(
            t => MediaRecorder.isTypeSupported(t)
        ) || '';

    voiceBtn.onclick = async () => {
        if (isListening) {
            recorder?.stop();
            return;
        }

        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            chunks = [];

            recorder = new MediaRecorder(
                stream,
                mime ? { mimeType: mime } : undefined
            );

            recorder.onstart = () => {
                isListening = true;
                console.log('Microphone recording started');
                voiceInd.style.display = 'block';
                voiceBtn.classList.add('active');
            };

            recorder.ondataavailable = e => {
                if (e.data.size) chunks.push(e.data);
            };

            recorder.onstop = async () => {
                isListening = false;
                voiceInd.style.display = 'none';
                voiceBtn.classList.remove('active');

                stream?.getTracks().forEach(t => t.stop());
                stream = null;

                try {
                    const blob = new Blob(chunks, {
                        type: recorder.mimeType || 'audio/webm'
                    });

                    const formData = new FormData();
                    formData.append('file', blob, 'recording.webm');

                    voiceInd.textContent = 'Processing...';
                    voiceInd.style.display = 'block';

                    const res = await fetch('/api/transcribe', {
                        method: 'POST',
                        body: formData
                    });

                    if (!res.ok) {
                        throw new Error(`Transcription failed: ${res.status}`);
                    }

                    const data = await res.json();

                    if (data.text?.trim()) {
                        userInput.value +=
                            (userInput.value ? ' ' : '') + data.text.trim();
                    } else {
                        alert('No speech was detected. Please try again.');
                    }

                    userInput.focus();
                } catch (err) {
                    console.error('Whisper transcription error:', err);
                    alert('Microphone transcription failed. Please try again.');
                } finally {
                    voiceInd.textContent = 'Listening...';
                    voiceInd.style.display = 'none';
                }
            };

            recorder.start();
        } catch (err) {
            console.error('Microphone error:', err);
            isListening = false;
            voiceInd.style.display = 'none';
            voiceBtn.classList.remove('active');
            alert('Microphone access failed. Please check browser microphone permission.');
        }
    };
}

function initSpeechSynthesis() {
    const btn = document.getElementById('read-aloud-btn');
    const explainDiv = document.getElementById('val-explainability');

    if (!btn || !explainDiv) return;

    btn.onclick = () => {
        if (isSpeaking) {
            window.speechSynthesis.cancel();
            isSpeaking = false;
            resetReadAloudButton();
        } else {
            const text = explainDiv.textContent || explainDiv.innerText;

            if (text && text.trim()) {
                window.speechSynthesis.cancel();

                synthUtterance = new SpeechSynthesisUtterance(text);

                synthUtterance.onend = synthUtterance.onerror = () => {
                    isSpeaking = false;
                    resetReadAloudButton();
                };

                isSpeaking = true;

                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/></svg> Stop Reading`;

                window.speechSynthesis.speak(synthUtterance);
            }
        }
    };
}

function resetReadAloudButton() {
    const btn = document.getElementById('read-aloud-btn');

    if (btn) {
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Read Aloud`;
    }
}

function initChatSubmit() {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');

    if (!sendBtn || !userInput) return;

    sendBtn.addEventListener('click', () => submitUserSymptoms());

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitUserSymptoms();
        }
    });

    const toastViewBtn = document.getElementById('toast-view-btn');
    const toastCloseBtn = document.getElementById('toast-close-btn');
    const toastBanner = document.getElementById('toast-notification-banner');

    if (toastViewBtn && toastBanner) {
        toastViewBtn.addEventListener('click', () => {
            toastBanner.style.display = 'none';
            toggleReportPanel(true);

            const reportViewport = document.getElementById('report-viewport');

            if (reportViewport) {
                reportViewport.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }

    if (toastCloseBtn && toastBanner) {
        toastCloseBtn.addEventListener('click', () => {
            toastBanner.style.display = 'none';
        });
    }
}

function submitUserSymptoms() {
    const userInput = document.getElementById('user-input');

    if (!userInput) return;

    const text = userInput.value.trim();

    const validChars = /^[A-Za-z0-9\s.,!?'-]+$/.test(text);
    const hasJoinedAlphaNumeric = /[A-Za-z]\d|\d[A-Za-z]/.test(text);
    const hasLetter = /[A-Za-z]/.test(text);

    if (!text || !validChars || hasJoinedAlphaNumeric || !hasLetter) {
        alert('Please enter a valid symptom description.');
        userInput.focus();
        return;
    }

    userInput.value = '';
    handleSend(text);
}

async function handleSend(text) {
    if (!text) return;

    appendMessage('user', text);

    const indicator = document.getElementById('chat-typing-indicator');

    if (indicator) indicator.style.display = 'flex';

    scrollToBottom('chat-container');

    const historyRef = chatHistory;
    const caseRef = activeCase;

    const sameSession = () =>
        chatHistory === historyRef && activeCase === caseRef;

    const wireHistory = historyRef.slice(0, -1).map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
    }));

    try {
        if (caseRef) {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    chat_history: wireHistory,
                    report_data: caseRef
                })
            });

            const data = await res.json();

            sameSession() &&
                indicator &&
                (indicator.style.display = 'none');

            if (!sameSession()) {
                historyRef.push({
                    sender: 'bot',
                    text: data.response
                });

                saveReplyIntoOwnSession(caseRef, historyRef);
                return;
            }

            appendMessage('bot', data.response);
            updateActiveSessionInStore();
        } else {
            const res = await fetch('/api/intake', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    chat_history: wireHistory
                })
            });

            const data = await res.json();

            sameSession() &&
                indicator &&
                (indicator.style.display = 'none');

            if (!sameSession()) {
                if (data.status === 'interviewing') {
                    historyRef.push({
                        sender: 'bot',
                        text: data.question
                    });
                } else if (data.status === 'ready') {
                    historyRef.push({
                        sender: 'bot',
                        text: 'Clinical interview complete. Your symptoms are being processed by the multi-agent triage pipeline...'
                    });
                }

                saveReplyIntoOwnSession(null, historyRef);
                return;
            }

            if (data.status === 'interviewing') {
                appendMessage('bot', data.question);
            } else if (data.status === 'ready') {
                appendMessage(
                    'bot',
                    'Clinical interview complete. Your symptoms are being processed by the multi-agent triage pipeline...'
                );

                toggleReportPanel(true);
                triggerTriagePipeline(data.summary);
            }
        }
    } catch (err) {
        console.error('Chat error:', err);

        sameSession() &&
            indicator &&
            (indicator.style.display = 'none');

        if (sameSession()) {
            appendMessage(
                'bot',
                'I encountered an issue reaching the clinical backend. Please try resending your message.'
            );
        }
    }
}

function saveReplyIntoOwnSession(caseAtRequestStart, sessionChatHistory) {
    if (!caseAtRequestStart || !caseAtRequestStart.case_id) return;

    const session = savedCases.find(
        c => c.case_id === caseAtRequestStart.case_id
    );

    if (session) {
        session.chatHistory = sessionChatHistory;
        localStorage.setItem('aegis_cases', JSON.stringify(savedCases));
    }
}

function appendMessage(sender, text) {
    chatHistory.push({ sender, text });

    const container = document.getElementById('chat-container');
    const indicator = document.getElementById('chat-typing-indicator');

    appendMessageUI(sender, text, indicator, container);
}

function appendMessageUI(sender, text, indicator, container) {
    if (!container) return;

    const msgDiv = document.createElement('div');

    msgDiv.className =
        `message ${sender === 'user' ? 'user-message' : 'bot-message'}`;

    const p = document.createElement('p');
    p.textContent = text;

    msgDiv.appendChild(p);

    indicator
        ? container.insertBefore(msgDiv, indicator)
        : container.appendChild(msgDiv);

    scrollToBottom('chat-container');
}

function scrollToBottom(containerId) {
    const el = document.getElementById(containerId);

    if (el) el.scrollTop = el.scrollHeight;
}

function triggerTriagePipeline(summary) {
    if (isSpeaking) {
        window.speechSynthesis.cancel();
        isSpeaking = false;
        resetReadAloudButton();
    }

    toggleReportPanel(true);

    const emptyState = document.getElementById('empty-state');
    const progressContainer = document.getElementById('progress-container');
    const agentGridContainer = document.getElementById('agent-grid-container');
    const skeletonLoader = document.getElementById('skeleton-loader-container');
    const reportContent = document.getElementById('report-content');
    const emergencyBox = document.getElementById('emergency-alert-box');

    if (emptyState) emptyState.style.display = 'none';
    if (reportContent) reportContent.style.display = 'none';
    if (emergencyBox) emergencyBox.style.display = 'none';
    if (progressContainer) progressContainer.style.display = 'block';
    if (agentGridContainer) agentGridContainer.style.display = 'block';
    if (skeletonLoader) skeletonLoader.style.display = 'block';

    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');

    if (progressFill) progressFill.style.width = '5%';
    if (progressPercent) progressPercent.textContent = '5%';

    const nodes = [1, 2, 3, 4].map(
        i => document.getElementById(`node-agent-${i}`)
    );

    nodes.forEach(n => {
        if (n) n.className = 'agent-node';
    });

    setNodeState(nodes[0], 'status-running');

    const streamChatHistoryRef = chatHistory;
    const streamActiveCaseAtStart = activeCase;

    function stillOnThisSession() {
        return (
            chatHistory === streamChatHistoryRef &&
            activeCase === streamActiveCaseAtStart
        );
    }

    function applyProgress(pct, msg) {
        if (progressFill) progressFill.style.width = `${pct}%`;
        if (progressPercent) progressPercent.textContent = `${pct}%`;
        if (progressText && msg) progressText.textContent = msg;

        if (pct < 30) {
            setNodeState(nodes[0], 'status-running');
        } else if (pct < 55) {
            setNodeState(nodes[0], 'status-completed');
            setNodeState(nodes[1], 'status-running');
        } else if (pct < 95) {
            setNodeState(nodes[1], 'status-completed');
            setNodeState(nodes[2], 'status-running');
        } else {
            setNodeState(nodes[2], 'status-completed');
            setNodeState(nodes[3], 'status-running');
        }
    }

    const eventSource =
        new EventSource(
            `/api/triage/stream?complaint=${encodeURIComponent(summary)}`
        );

    eventSource.addEventListener('status', (e) => {
        if (!stillOnThisSession()) return;

        const data = JSON.parse(e.data);
        applyProgress(data.pct, data.msg);
    });

    eventSource.addEventListener('complete', (e) => {
        const data = JSON.parse(e.data);

        eventSource.close();

        if (!stillOnThisSession()) {
            saveCompletedCaseInBackground(
                streamChatHistoryRef,
                data
            );
            return;
        }

        setNodeState(nodes[3], 'status-completed');
        finishTriageRender(data);
    });

    eventSource.onerror = (err) => {
        console.error('SSE stream error, switching to REST POST...', err);

        eventSource.close();

        if (!stillOnThisSession()) return;

        if (progressText) {
            progressText.textContent =
                'Processing clinical evaluation...';
        }

        fetchTriageFallback(
            summary,
            streamChatHistoryRef,
            stillOnThisSession,
            nodes
        );
    };
}

async function fetchTriageFallback(
    summary,
    streamChatHistoryRef,
    stillOnThisSession,
    nodes
) {
    try {
        const res = await fetch('/api/triage', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ complaint: summary })
        });

        const data = await res.json();

        if (
            stillOnThisSession &&
            !stillOnThisSession()
        ) {
            saveCompletedCaseInBackground(
                streamChatHistoryRef,
                data
            );
            return;
        }

        if (nodes) {
            nodes.forEach(
                n => setNodeState(n, 'status-completed')
            );
        }

        finishTriageRender(data);
    } catch (e) {
        console.error('REST triage execution error:', e);

        if (
            stillOnThisSession &&
            !stillOnThisSession()
        ) {
            return;
        }

        const progressText =
            document.getElementById('progress-text');

        if (progressText) {
            progressText.textContent =
                'Triage evaluation failed. Please check local server logs.';
        }
    }
}

function finishTriageRender(data) {
    const progressContainer =
        document.getElementById('progress-container');

    const skeletonLoader =
        document.getElementById('skeleton-loader-container');

    if (progressContainer) {
        progressContainer.style.display = 'none';
    }

    if (skeletonLoader) {
        skeletonLoader.style.display = 'none';
    }

    activeCase = {
        ...data,
        chatHistory: [...chatHistory]
    };

    applyReportData(activeCase);
    saveCaseToHistory(activeCase);
    renderSidebarCases();

    showToast(
        `Triage Report ${activeCase.case_id} is ready!`
    );
}

function saveCompletedCaseInBackground(
    originalChatHistory,
    data
) {
    const summaryLine = {
        sender: 'bot',
        text:
            `Attending Physician Triage Compiled. Case ID: ${data.case_id}. Risk Level: ${data.risk_level}.`
    };

    const alreadyHasSummary =
        originalChatHistory.some(
            m =>
                m.text &&
                m.text.includes(`Case ID: ${data.case_id}`)
        );

    const fullHistory =
        alreadyHasSummary
            ? originalChatHistory
            : [...originalChatHistory, summaryLine];

    const caseRecord = {
        ...data,
        chatHistory: fullHistory
    };

    savedCases =
        savedCases.filter(
            c => c.case_id !== data.case_id
        );

    savedCases.unshift(caseRecord);

    if (savedCases.length > 30) {
        savedCases.pop();
    }

    localStorage.setItem(
        'aegis_cases',
        JSON.stringify(savedCases)
    );

    renderSidebarCases();
}

function setNodeState(node, stateClass) {
    if (node) {
        node.className =
            `agent-node ${stateClass}`;
    }
}

function applyReportData(report) {
    const riskBadge =
        document.getElementById('risk-badge');

    const reportContent =
        document.getElementById('report-content');

    const emergencyBox =
        document.getElementById('emergency-alert-box');

    const risk =
        (report.risk_level || 'LOW').toUpperCase();

    if (riskBadge) {
        riskBadge.textContent = risk;
        riskBadge.className = 'badge';

        if (risk === 'EMERGENCY') {
            riskBadge.classList.add('badge-danger');
        } else if (risk === 'HIGH') {
            riskBadge.classList.add('badge-warning');
        } else if (risk === 'MEDIUM') {
            riskBadge.classList.add('badge-info');
        } else {
            riskBadge.classList.add('badge-success');
        }
    }

    if (risk === 'EMERGENCY') {
        if (reportContent) {
            reportContent.style.display = 'none';
        }

        if (emergencyBox) {
            emergencyBox.style.display = 'flex';

            const msgEl =
                document.getElementById(
                    'emergency-alert-message'
                );

            const idEl =
                document.getElementById(
                    'emergency-alert-caseid'
                );

            if (msgEl) {
                msgEl.textContent =
                    report.explainability ||
                    'This looks like it could be a medical emergency.';
            }

            if (idEl) {
                idEl.textContent =
                    report.case_id || '';
            }
        }

        return;
    }

    if (emergencyBox) {
        emergencyBox.style.display = 'none';
    }

    if (reportContent) {
        reportContent.style.display = 'block';
    }

    const setText = (id, val) => {
        const el = document.getElementById(id);

        if (el) {
            el.textContent =
                val == null ? '' : String(val);
        }
    };

    setText(
        'val-confidence',
        `${((report.confidence_score || 0) * 100).toFixed(1)}%`
    );

    setText(
        'val-case-id',
        report.case_id || 'N/A'
    );

    setText(
        'val-consensus',
        report.consensus || ''
    );

    setText(
        'val-explainability',
        report.explainability || ''
    );

    setText(
        'val-pharmacist',
        report.pharmacist_review || ''
    );

    const pharmacistSection =
        document.getElementById(
            'pharmacist-section'
        );

    if (pharmacistSection) {
        pharmacistSection.style.display =
            report.pharmacist_review
                ? 'block'
                : 'none';
    }

    const specialists =
        document.getElementById(
            'specialist-responses'
        );

    if (specialists) {
        const entries =
            Object.entries(
                report.specialists || {}
            );

        specialists.innerHTML =
            entries
                .map(
                    ([title, body]) => `
                    <div class="specialist-card">
                        <div class="specialist-card-title">${escapeHtml(title)}</div>
                        <div class="specialist-card-body">${escapeHtml(body)}</div>
                    </div>
                `
                )
                .join('');
    }

    const citations =
        document.getElementById(
            'val-citations'
        );

    if (citations) {
        const cites =
            report.citations || [];

        citations.innerHTML =
            cites.length
                ? cites
                    .map(
                        c =>
                            `<div class="citation-item">&bull; [${escapeHtml(c.doc_id || '')}] ${escapeHtml(c.title || '')} (Similarity: ${((c.score || 0) * 100).toFixed(1)}%)</div>`
                    )
                    .join('')
                : '<div class="citation-item">No retrieval citations for this case.</div>';
    }

    renderRagTreatment(report);

    setupDownloadHandler(report);
}

function renderRagTreatment(report) {
    const remediesBox =
        document.querySelector('.remedies-box');

    if (!remediesBox) return;

    const treatmentRemedies =
        report.treatment_remedies || {};

    const pharmacistReview =
        report.pharmacist_review || '';

    const tablets =
        Array.isArray(treatmentRemedies.tablets)
            ? treatmentRemedies.tablets
            : [];

    const precautions =
        Array.isArray(treatmentRemedies.precautions)
            ? treatmentRemedies.precautions
            : [];

    let content = '';

    if (pharmacistReview.trim()) {
        content += `
            <div class="rag-treatment-content">
                ${escapeHtml(pharmacistReview).replace(/\n/g, '<br>')}
            </div>
        `;
    }

    if (tablets.length) {
        content += `
            <div class="remedies-subtitle">Recommended Medications &amp; Remedies</div>
            <div class="table-responsive">
                <table class="remedies-table">
                    <thead>
                        <tr>
                            <th>Remedy/Tablet</th>
                            <th>Dosage</th>
                            <th>Frequency</th>
                            <th>Purpose</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tablets.map(tab => `
                            <tr>
                                <td><strong>${escapeHtml(tab.name || '')}</strong></td>
                                <td>${escapeHtml(tab.dosage || '')}</td>
                                <td>${escapeHtml(tab.frequency || '')}</td>
                                <td>${escapeHtml(tab.purpose || '')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    if (precautions.length) {
        content += `
            <div class="remedies-subtitle">Lifestyle &amp; Clinical Precautions</div>
            <ul class="precautions-list">
                ${precautions.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
            </ul>
        `;
    }

    if (!content) {
        content = `
            <div class="citation-item">
                No treatment information was returned from the retrieved clinical evidence.
            </div>
        `;
    }

    remediesBox.innerHTML = content;
}

function escapeHtml(str) {
    const div = document.createElement('div');

    div.textContent =
        str == null ? '' : String(str);

    return div.innerHTML;
}

function setupDownloadHandler(report) {
    const downloadBtn =
        document.getElementById(
            'download-pdf-btn'
        );

    if (!downloadBtn) return;

    downloadBtn.href =
        report.pdf_url || '#';

    downloadBtn.onclick = null;
}

function loadCasesFromStorage() {
    try {
        savedCases =
            JSON.parse(
                localStorage.getItem(
                    'aegis_cases'
                ) || '[]'
            );

        renderSidebarCases();
    } catch (e) {
        console.error(
            'Error loading cases',
            e
        );

        savedCases = [];
    }
}

function saveCaseToHistory(reportCase) {
    const existingIndex =
        savedCases.findIndex(
            c => c.case_id === reportCase.case_id
        );

    if (existingIndex !== -1) {
        savedCases[existingIndex] =
            reportCase;
    } else {
        savedCases.unshift(
            reportCase
        );
    }

    if (savedCases.length > 30) {
        savedCases.pop();
    }

    localStorage.setItem(
        'aegis_cases',
        JSON.stringify(savedCases)
    );
}

function updateActiveSessionInStore() {
    if (!activeCase || !activeCase.case_id) {
        return;
    }

    const session =
        savedCases.find(
            c => c.case_id === activeCase.case_id
        );

    if (session) {
        session.chatHistory =
            chatHistory;

        localStorage.setItem(
            'aegis_cases',
            JSON.stringify(savedCases)
        );
    }
}

function renderSidebarCases() {
    const listContainer =
        document.getElementById(
            'sidebar-cases'
        );

    if (!listContainer) return;

    listContainer.innerHTML = '';

    if (savedCases.length === 0) {
        listContainer.innerHTML =
            '<div class="sidebar-empty">No saved sessions</div>';
        return;
    }

    savedCases.forEach(c => {
        const item =
            document.createElement('div');

        item.className =
            `sidebar-item ${
                activeCase &&
                activeCase.case_id === c.case_id
                    ? 'active'
                    : ''
            }`;

        item.addEventListener(
            'click',
            (e) => {
                if (
                    e.target.closest(
                        '.sidebar-btn'
                    )
                ) {
                    return;
                }

                selectCase(
                    c.case_id
                );
            }
        );

        const symptomText =
            c.patient_complaint || '';

        const symptomSnippet =
            symptomText.length > 20
                ? symptomText.slice(0, 20) + '...'
                : symptomText;

        const info =
            document.createElement('div');

        info.style.overflow =
            'hidden';

        info.innerHTML = `
            <div style="font-weight:700;">${escapeHtml(c.case_id)}</div>
            <div style="font-size:11px; opacity:0.8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(symptomSnippet)}</div>
        `;

        const actions =
            document.createElement('div');

        actions.className =
            'sidebar-actions';

        const delBtn =
            document.createElement('button');

        delBtn.className =
            'sidebar-btn';

        delBtn.title =
            'Delete Session';

        delBtn.innerHTML =
            `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`;

        delBtn.onclick =
            () =>
                deleteCaseFromHistory(
                    c.case_id
                );

        actions.appendChild(
            delBtn
        );

        item.appendChild(
            info
        );

        item.appendChild(
            actions
        );

        listContainer.appendChild(
            item
        );
    });
}

function selectCase(caseId) {
    const selected =
        savedCases.find(
            c => c.case_id === caseId
        );

    if (!selected) return;

    const indicator =
        document.getElementById(
            'chat-typing-indicator'
        );

    if (indicator) {
        indicator.style.display =
            'none';
    }

    activeCase =
        selected;

    chatHistory =
        [...selected.chatHistory];

    const container =
        document.getElementById(
            'chat-container'
        );

    if (container) {
        container
            .querySelectorAll(
                '.message:not(.typing-indicator)'
            )
            .forEach(
                m => m.remove()
            );

        chatHistory.forEach(
            h =>
                appendMessageUI(
                    h.sender,
                    h.text,
                    indicator,
                    container
                )
        );
    }

    const emptyState =
        document.getElementById(
            'empty-state'
        );

    const progressContainer =
        document.getElementById(
            'progress-container'
        );

    const agentGridContainer =
        document.getElementById(
            'agent-grid-container'
        );

    const skeletonLoader =
        document.getElementById(
            'skeleton-loader-container'
        );

    const reportContent =
        document.getElementById(
            'report-content'
        );

    if (emptyState) {
        emptyState.style.display =
            'none';
    }

    if (progressContainer) {
        progressContainer.style.display =
            'none';
    }

    if (agentGridContainer) {
        agentGridContainer.style.display =
            'none';
    }

    if (skeletonLoader) {
        skeletonLoader.style.display =
            'none';
    }

    if (reportContent) {
        reportContent.style.display =
            'block';
    }

    applyReportData(
        selected
    );

    toggleReportPanel(true);
    renderSidebarCases();
}

function deleteCaseFromHistory(caseId) {
    savedCases =
        savedCases.filter(
            c => c.case_id !== caseId
        );

    localStorage.setItem(
        'aegis_cases',
        JSON.stringify(savedCases)
    );

    if (
        activeCase &&
        activeCase.case_id === caseId
    ) {
        resetTriageSession();
    } else {
        renderSidebarCases();
    }
}

function initNewCaseBtn() {
    const newCaseBtn =
        document.getElementById(
            'new-case-btn'
        );

    if (newCaseBtn) {
        newCaseBtn.onclick =
            resetTriageSession;
    }
}

function resetTriageSession() {
    if (isSpeaking) {
        window.speechSynthesis.cancel();
        isSpeaking = false;
        resetReadAloudButton();
    }

    const indicator =
        document.getElementById(
            'chat-typing-indicator'
        );

    if (indicator) {
        indicator.style.display =
            'none';
    }

    activeCase = null;

    chatHistory = [
        {
            sender: 'bot',
            text: 'Welcome to Aegis. Please describe your symptoms, including their severity, duration, and if they were triggered by a specific event.'
        }
    ];

    const container =
        document.getElementById(
            'chat-container'
        );

    if (container) {
        container
            .querySelectorAll(
                '.message:not(.typing-indicator)'
            )
            .forEach(
                m => m.remove()
            );

        appendMessageUI(
            'bot',
            chatHistory[0].text,
            indicator,
            container
        );

        chatHistory.pop();
    }

    const emptyState =
        document.getElementById(
            'empty-state'
        );

    const progressContainer =
        document.getElementById(
            'progress-container'
        );

    const agentGridContainer =
        document.getElementById(
            'agent-grid-container'
        );

    const skeletonLoader =
        document.getElementById(
            'skeleton-loader-container'
        );

    const reportContent =
        document.getElementById(
            'report-content'
        );

    const emergencyBox =
        document.getElementById(
            'emergency-alert-box'
        );

    if (emptyState) {
        emptyState.style.display =
            'flex';
    }

    if (progressContainer) {
        progressContainer.style.display =
            'none';
    }

    if (agentGridContainer) {
        agentGridContainer.style.display =
            'none';
    }

    if (skeletonLoader) {
        skeletonLoader.style.display =
            'none';
    }

    if (reportContent) {
        reportContent.style.display =
            'none';
    }

    if (emergencyBox) {
        emergencyBox.style.display =
            'none';
    }

    const riskBadge =
        document.getElementById(
            'risk-badge'
        );

    if (riskBadge) {
        riskBadge.textContent =
            'Awaiting Intake';

        riskBadge.className =
            'badge';
    }

    renderSidebarCases();
}

function showToast(message) {
    const toast =
        document.getElementById(
            'toast-notification-banner'
        );

    const toastMsg =
        document.getElementById(
            'toast-message'
        );

    if (!toast || !toastMsg) return;

    toastMsg.textContent =
        message;

    toast.style.display =
        'flex';

    setTimeout(() => {
        toast.style.display =
            'none';
    }, 6000);
}