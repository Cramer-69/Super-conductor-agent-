// Conductor Voice Agent - Mobile Web App
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentAudio = null;

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
    loadConnectionStatus();
});

// Fetch /health and render the connection status strip
async function loadConnectionStatus() {
    const el = document.getElementById('connectionStatus');
    try {
        const response = await fetch('/health');
        const data = await response.json();

        const providers = data.providers && data.providers.length
            ? data.providers.join(', ')
            : 'none';
        const connectors = Object.entries(data.connectors || {})
            .map(([name, on]) => `${dot(on)}${name}`)
            .join(' ');

        el.innerHTML = `
            <span>${dot(data.providers && data.providers.length > 0)}LLM: ${providers}</span>
            <span>${dot(!!data.voice_configured)}Voice</span>
            ${connectors ? `<span>${connectors}</span>` : ''}
        `;
    } catch (error) {
        el.innerHTML = `<span>${dot(false)}Status unavailable</span>`;
        console.error('Health check failed:', error);
    }
}

function dot(isOn) {
    return `<span class="status-dot ${isOn ? 'on' : 'off'}"></span>`;
}

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
            body: JSON.stringify({ query: text })
        });
        
        if (!response.ok) throw new Error('API request failed');
        
        const data = await response.json();
        addMessage('assistant', data.response);
        
        if (data.sources && data.sources.length > 0) {
            const sourcesText = data.sources.slice(0, 2).map(s => 
                `📚 ${s.platform.toUpperCase()}: ${s.title}`
            ).join('\n');
            addMessage('system', sourcesText, true);
        }
        
        showStatus('Type a message or tap 🎤 to talk', 'ready');
        
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
        console.error('Chat error:', error);
    }
}

// Setup microphone
async function setupMicrophone() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm'
        });

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
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
    recordingIndicator.classList.add('flex');
    showStatus('Listening...', 'recording');
    
    mediaRecorder.start();
}

// Stop recording
function stopRecording() {
    isRecording = false;
    
    micButton.classList.remove('recording');
    recordingIndicator.classList.remove('flex');
    recordingIndicator.classList.add('hidden');
    showStatus('Processing...', 'processing');
    
    mediaRecorder.stop();
}

// Send voice message
async function sendVoiceMessage(audioBlob) {
    try {
        // Add user message placeholder
        addMessage('user', '🎤 Voice message...', true);
        
        // Create form data
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        // Send to API
        const response = await fetch('/api/voice-chat', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('API request failed');
        }
        
        const data = await response.json();
        
        // Update user message with transcription
        updateLastMessage('user', data.transcription);
        
        // Add assistant response
        addMessage('assistant', data.response);
        
        // Add sources if available
        if (data.sources && data.sources.length > 0) {
            const sourcesText = data.sources.slice(0, 2).map(s => 
                `📚 ${s.platform.toUpperCase()}: ${s.title}`
            ).join('\n');
            addMessage('system', sourcesText, true);
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

// Update last message
function updateLastMessage(role, text) {
    const lastMessage = messages.lastElementChild;
    if (lastMessage) {
        lastMessage.textContent = text;
    }
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
