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
// Give it some nice default styling for the text
overlay.style.fontSize = '24px';
overlay.style.color = 'white';
overlay.style.textShadow = '2px 2px 4px #000000'; 

// 2. Inject overlay into player
const playerObserver = new MutationObserver(() => {
    const videoContainer = document.querySelector('.html5-video-player');
    if (videoContainer && !document.getElementById('bilingual-subtitle-overlay')) {
        videoContainer.appendChild(overlay);
        console.log("Overlay injected into player!");
        
        // Once the player is there, start hunting for the native caption box
        startCaptionObserver();
    }
});
playerObserver.observe(document.body, { childList: true, subtree: true });

// 3. Spy on YouTube's native captions
let lastCaptionText = "";

function startCaptionObserver() {
    // Target the permanent parent container
    const captionContainer = document.querySelector('.ytp-caption-window-container'); 
    
    if (!captionContainer) {
        setTimeout(startCaptionObserver, 1000);
        return;
    }

    console.log("Persistent caption container found! Spying on subtitles...");

    const captionObserver = new MutationObserver(() => {
        const segments = document.querySelectorAll('.ytp-caption-segment');
        if (segments.length === 0) return;

        let currentText = Array.from(segments).map(span => span.innerText).join(' ').trim();

        if (currentText && currentText !== lastCaptionText) {
            lastCaptionText = currentText;
            console.log("Grabbed text:", currentText);
            overlay.innerHTML = `<span style="background: rgba(0,0,0,0.7); padding: 5px;">${currentText}</span>`;
        }
    });

    // Observe the parent container and all nested children
    captionObserver.observe(captionContainer, { childList: true, subtree: true, characterData: true });
}
