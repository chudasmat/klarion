const noteContent = document.getElementById('note-content');
const pinBtn = document.getElementById('pin-btn');
const closeBtn = document.getElementById('close-btn');
const opacitySlider = document.getElementById('opacity-slider');
const container = document.querySelector('.note-container');

// State
let isPinned = false;

// Initialize
window.addEventListener('pywebviewready', () => {
    // Load saved note
    const savedNote = localStorage.getItem('sticky_note_content');
    if (savedNote) {
        noteContent.value = savedNote;
    }
});

// Pin Toggle
pinBtn.addEventListener('click', () => {
    isPinned = !isPinned;
    if (isPinned) {
        pinBtn.classList.add('active');
    } else {
        pinBtn.classList.remove('active');
    }

    // Call Python API
    if (window.pywebview) {
        window.pywebview.api.toggle_pin(isPinned);
    }
});

// Close App
closeBtn.addEventListener('click', () => {
    if (window.pywebview) {
        window.pywebview.api.close_app();
    }
});

// Transparency
opacitySlider.addEventListener('input', (e) => {
    const val = e.target.value;
    // Update CSS opacity
    container.style.backgroundColor = `rgba(30, 30, 30, ${val})`;

    // Optional: advise Python backend (mostly for logging or if native changes needed)
    if (window.pywebview) {
        window.pywebview.api.set_transparency(val);
    }
});

// Auto-save logic (Debounce)
let timeout;
noteContent.addEventListener('input', () => {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
        localStorage.setItem('sticky_note_content', noteContent.value);
    }, 500);
});
