// extension/content.js

console.log("Bilingual Subtitle Engine: Content script loaded!");

// 1. Create our custom overlay container
const overlay = document.createElement('div');
overlay.id = 'bilingual-subtitle-overlay';
overlay.style.position = 'absolute';
overlay.style.bottom = '10%';
overlay.style.width = '100%';
overlay.style.textAlign = 'center';
overlay.style.zIndex = '9999';
overlay.style.pointerEvents = 'none'; // Let clicks pass through to the video

// 2. Wait for the YouTube video player to load, then inject the overlay
const observer = new MutationObserver(() => {
    const videoContainer = document.querySelector('.html5-video-player');
    if (videoContainer && !document.getElementById('bilingual-subtitle-overlay')) {
        videoContainer.appendChild(overlay);
        console.log("Overlay injected into player!");
    }
});

observer.observe(document.body, { childList: true, subtree: true });

// 3. Listen for background script messages (we'll wire this up later)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'NEW_SUBTITLE') {
        // Render the processed subtitle data
        overlay.innerHTML = `<span style="background: rgba(0,0,0,0.7); color: white; padding: 5px; font-size: 24px;">${request.text}</span>`;
    }
});
