// Conductor Voice Agent - Mobile Web App
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentAudio = null;
let conversationId = localStorage.getItem('conductor_conversation_id');

const micButton = document.getElementById('micButton');
const status = document.getElementById('status');
const messages = document.getElementById('messages');
const recordingIndicator = document.getElementById('recordingIndicator');
const voiceSelect = document.getElementById('voiceSelect');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupMicrophone();
    setupTextChat();
    loadSettings();
});

// Setup text chat
function setupTextChat() {
    const textInput = document.getElementById('textInput');
    const sendButton = document.getElementById('sendButton');
    
    sendButton.addEventListener('click', () => {
        const text = textInput.value.trim();
        if (text) {
            sendTextMessage(text);
            textInput.value = '';
        }
    });
    
    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const text = textInput.value.trim();
            if (text) {
                sendTextMessage(text);
                textInput.value = '';
            }
        }
    });
}

// Send text message
async function sendTextMessage(text) {
    try {
        addMessage('user', text);
        showStatus('Thinking...', 'processing');
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: text,
                conversation_id: conversationId
            })
        });
        
        if (!response.ok) throw new Error('API request failed');
        
        const data = await response.json();
        rememberConversation(data.conversation_id);
        addMessage('assistant', data.response);
        
        if (data.sources && data.sources.length > 0) {
            addSources(data.sources);
        }
        
        showStatus('Type a message or tap 🎤 to talk', 'ready');
        
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
        console.error('Chat error:', error);
    }
}

// Pick a MIME type the browser actually supports. iOS Safari does NOT
// support webm — it needs mp4/m4a. We try webm first (Chrome/Firefox),
// then mp4 (Safari), then fall back to whatever the browser defaults to.
function pickAudioMimeType() {
    const candidates = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4;codecs=mp4a.40.2',
        'audio/mp4',
        'audio/ogg;codecs=opus',
    ];
    for (const t of candidates) {
        if (typeof MediaRecorder !== 'undefined' &&
            MediaRecorder.isTypeSupported &&
            MediaRecorder.isTypeSupported(t)) {
            return t;
        }
    }
    return '';
}

let recordingMimeType = '';
let recordingExtension = 'webm';

// Setup microphone
async function setupMicrophone() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recordingMimeType = pickAudioMimeType();
        recordingExtension = recordingMimeType.includes('mp4') ? 'm4a'
                          : recordingMimeType.includes('ogg') ? 'ogg'
                          : 'webm';

        mediaRecorder = recordingMimeType
            ? new MediaRecorder(stream, { mimeType: recordingMimeType })
            : new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const blobType = recordingMimeType || mediaRecorder.mimeType || 'audio/webm';
            const audioBlob = new Blob(audioChunks, { type: blobType });
            audioChunks = [];
            await sendVoiceMessage(audioBlob);
        };

        micButton.addEventListener('click', toggleRecording);

    } catch (error) {
        showStatus('Microphone access denied. Please allow microphone access.', 'error');
        console.error('Microphone error:', error);
    }
}

// Toggle recording
function toggleRecording() {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
}

// Start recording
function startRecording() {
    isRecording = true;
    audioChunks = [];
    
    micButton.classList.add('recording');
    recordingIndicator.classList.remove('hidden');
    showStatus('Listening...', 'recording');
    
    mediaRecorder.start();
}

// Stop recording
function stopRecording() {
    isRecording = false;
    
    micButton.classList.remove('recording');
    recordingIndicator.classList.add('hidden');
    showStatus('Processing...', 'processing');
    
    mediaRecorder.stop();
}

// Send voice message
async function sendVoiceMessage(audioBlob) {
    try {
        // Add user message placeholder
        addMessage('user', '🎤 Voice message...', true);
        
        // Create form data — use the extension matching whatever the
        // browser actually recorded (webm for Chrome, m4a for Safari).
        const formData = new FormData();
        formData.append('audio', audioBlob, `recording.${recordingExtension}`);
        if (conversationId) {
            formData.append('conversation_id', conversationId);
        }
        
        // Send to API
        const response = await fetch('/api/voice-chat', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('API request failed');
        }
        
        const data = await response.json();
        rememberConversation(data.conversation_id);
        
        // Update user message with transcription
        updateLastMessage('user', data.transcription);
        
        // Add assistant response
        addMessage('assistant', data.response);
        
        // Add sources if available
        if (data.sources && data.sources.length > 0) {
            addSources(data.sources);
        }
        
        // Play audio response
        if (data.audio_url) {
            await playAudio(data.audio_url);
        }
        
        showStatus('Ready to listen', 'ready');
        
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
        console.error('Voice chat error:', error);
    }
}

// Add message to conversation
function addMessage(role, text, small = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message p-4 rounded-2xl ${
        role === 'user' 
            ? 'bg-white/20 ml-8' 
            : role === 'assistant'
            ? 'bg-blue-500/30 mr-8'
            : 'bg-white/10 text-center'
    } ${small ? 'text-xs' : 'text-sm'} text-white`;
    
    messageDiv.textContent = text;
    messages.appendChild(messageDiv);
    
    // Scroll to bottom
    messages.parentElement.scrollTop = messages.parentElement.scrollHeight;
    
    return messageDiv;
}

function addSources(sources) {
    const sourceDiv = document.createElement('div');
    sourceDiv.className = 'message p-4 rounded-2xl bg-white/10 text-xs text-white';

    const heading = document.createElement('div');
    heading.textContent = '📚 Sources';
    heading.className = 'font-semibold mb-2';
    sourceDiv.appendChild(heading);

    sources.slice(0, 4).forEach((source) => {
        const row = document.createElement('div');
        const link = document.createElement('a');
        link.textContent = source.title || source.url || 'Source';
        link.href = source.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'underline break-words';
        row.appendChild(link);
        sourceDiv.appendChild(row);
    });

    messages.appendChild(sourceDiv);
    messages.parentElement.scrollTop = messages.parentElement.scrollHeight;
}

// Update last message
function updateLastMessage(role, text) {
    const lastMessage = messages.lastElementChild;
    if (lastMessage) {
        lastMessage.textContent = text;
    }
}

function rememberConversation(id) {
    if (!id) return;
    conversationId = id;
    localStorage.setItem('conductor_conversation_id', id);
}

function startNewConversation() {
    conversationId = null;
    localStorage.removeItem('conductor_conversation_id');
    messages.innerHTML = `
        <div class="text-white text-center opacity-75 py-8">
            <p class="text-lg mb-2">👋 New conversation</p>
            <p class="text-sm">Type a message or tap the microphone</p>
        </div>
    `;
    showStatus('New conversation started', 'ready');
}

// Play audio
async function playAudio(audioUrl) {
    return new Promise((resolve, reject) => {
        // Stop current audio if playing
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
        
        currentAudio = new Audio(audioUrl);
        currentAudio.onended = () => {
            currentAudio = null;
            resolve();
        };
        currentAudio.onerror = reject;
        
        showStatus('🔊 Playing response...', 'playing');
        currentAudio.play();
    });
}

// Show status
function showStatus(text, type = 'ready') {
    status.innerHTML = `<p class="text-sm opacity-75">${text}</p>`;
}

// Load/save settings
function loadSettings() {
    const savedVoice = localStorage.getItem('voice');
    if (savedVoice) {
        voiceSelect.value = savedVoice;
    }
    
    voiceSelect.addEventListener('change', () => {
        localStorage.setItem('voice', voiceSelect.value);
        saveVoiceSettings();
    });

    const newConversationButton = document.getElementById('newConversationButton');
    if (newConversationButton) {
        newConversationButton.addEventListener('click', startNewConversation);
    }
}

async function saveVoiceSettings() {
    try {
        await fetch('/api/settings/voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ voice: voiceSelect.value })
        });
    } catch (error) {
        console.error('Error saving voice settings:', error);
    }
}

// Install PWA prompt
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    
    // Show install button (optional)
    const installButton = document.createElement('button');
    installButton.textContent = '📱 Install App';
    installButton.className = 'glass text-white px-4 py-2 rounded-lg text-sm fixed bottom-4 right-4';
    installButton.addEventListener('click', async () => {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        deferredPrompt = null;
        installButton.remove();
    });
    document.body.appendChild(installButton);
});

// Service worker registration (PWA support)
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {
        // Service worker not critical
    });
}
