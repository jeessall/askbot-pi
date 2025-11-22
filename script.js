document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       1) CARROSSEL
       ===================================================== */
    const track = document.querySelector(".carousel-track");
    if (track) {
        const cards = Array.from(track.children);
        cards.forEach(card => track.appendChild(card.cloneNode(true)));
    }

    /* =====================================================
       2) ELEMENTOS DO CHAT
       ===================================================== */
    const heroIcon = document.getElementById("hero-icon-clickable");
    const chatWidget = document.getElementById("chat-widget-container");
    const chatOverlay = document.getElementById("chat-overlay");
    const chatClose = document.getElementById("chat-close-btn");
    const chatLog = document.getElementById("chat-log");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const suggestionBtns = document.querySelectorAll(".suggestion-btn");
    const micBtn = document.getElementById("mic-btn");

    const API_URL = "http://127.0.0.1:5000/ask";

    /* =====================================================
       3) DALTÔNICO
       ===================================================== */
    const btnDalton = document.getElementById("btn-daltonismo");
    const panelDalton = document.getElementById("colorblind-panel");
    const selectDalton = document.getElementById("colorblind-mode");

    btnDalton.addEventListener("click", () => {
        panelDalton.classList.toggle("hidden");
    });

    selectDalton.addEventListener("change", e => {
        toggleColorblindMode(e.target.value);
    });

    document.addEventListener("click", ev => {
        if (!panelDalton.contains(ev.target) && !btnDalton.contains(ev.target)) {
            panelDalton.classList.add("hidden");
        }
    });

    window.toggleColorblindMode = function (mode) {
        let filterValue = "none";
        if (mode === "protanopia") filterValue = "url(#protanopia-filter)";
        if (mode === "deuteranopia") filterValue = "url(#deuteranopia-filter)";
        if (mode === "tritanopia") filterValue = "url(#tritanopia-filter)";
        document.body.style.setProperty("--filter-colorblind", filterValue);
    };

    /* =====================================================
       4) TTS VOZ
       ===================================================== */
    const synth = window.speechSynthesis;

    function speak(text) {
        if (!synth) return;
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "pt-BR";
        synth.speak(u);
    }

    /* =====================================================
       5) MENSAGENS
       ===================================================== */
    const botSVG = `
    <svg stroke="currentColor" fill="none" width="22" viewBox="0 0 24 24" stroke-width="1.4">
        <path stroke-linecap="round" stroke-linejoin="round"
            d="M7.5 8.25h9m-9 3H12m-6.75 3h9m-9 3H12M3 3h18M3 12h18m-6 9h6M3 21h6"/>
    </svg>`;

    const userSVG = `
    <svg stroke="currentColor" fill="none" width="22" viewBox="0 0 24 24" stroke-width="1.4">
        <path stroke-linecap="round" stroke-linejoin="round"
            d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"/>
        <path stroke-linecap="round" stroke-linejoin="round"
            d="M4.5 20.1a7.5 7.5 0 0115 0A1.5 1.5 0 0118 21.75H6A1.5 1.5 0 014.5 20.1z"/>
    </svg>`;

    function addMessage(sender, text) {
        const wrapper = document.createElement("div");
        wrapper.className = "message-wrapper " + (sender === "user" ? "user-message" : "bot-message");

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.innerHTML = sender === "user" ? userSVG : botSVG;

        const bubble = document.createElement("div");
        bubble.className = "message-bubble " + (sender === "user" ? "user-bubble" : "bot-bubble");
        bubble.innerHTML = text;

        if (sender === "user") {
            wrapper.appendChild(bubble);
            wrapper.appendChild(avatar);
        } else {
            wrapper.appendChild(avatar);
            wrapper.appendChild(bubble);
        }

        chatLog.appendChild(wrapper);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function greet() {
        chatLog.innerHTML = "";
        const msg = "Olá! Sou o assistente do Jovem Programador. Como posso ajudar?";
        setTimeout(() => {
            addMessage("bot", msg);
            speak(msg);
        }, 200);
    }

    /* =====================================================
       6) ABRIR FECHAR CHAT
       ===================================================== */
    function openChat() {
        chatWidget.classList.remove("hidden");
        chatOverlay.classList.remove("hidden");
        greet();
    }

    function closeChat() {
        chatWidget.classList.add("hidden");
        chatOverlay.classList.add("hidden");
        if (synth) synth.cancel();
    }

    heroIcon.addEventListener("click", openChat);
    chatClose.addEventListener("click", closeChat);
    chatOverlay.addEventListener("click", closeChat);

    /* =====================================================
       7) MICROFONE
       ===================================================== */
    let recognition;
    if ("webkitSpeechRecognition" in window) {
        recognition = new webkitSpeechRecognition();
    }

    if (recognition) {
        recognition.lang = "pt-BR";
        recognition.continuous = false;

        micBtn.addEventListener("click", () => {
            recognition.start();
            micBtn.classList.add("recording");
        });

        recognition.onresult = e => {
            chatInput.value = e.results[0][0].transcript;
            chatForm.dispatchEvent(new Event("submit"));
        };

        recognition.onend = () => {
            micBtn.classList.remove("recording");
        };
    } else {
        micBtn.style.display = "none";
    }

    /* =====================================================
       8) ENVIAR MENSAGEM
       ===================================================== */
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const text = chatInput.value.trim();
        if (!text) return;

        addMessage("user", text);
        chatInput.value = "";

        try {
            const res = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: text })
            });

            const data = await res.json();
            addMessage("bot", data.answer);
            speak(data.answer);

        } catch {
            addMessage("bot", "Erro ao conectar ao servidor.");
        }
    });

    /* =====================================================
       9) SUGESTÕES
       ===================================================== */
    suggestionBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            chatInput.value = btn.textContent;
            chatForm.dispatchEvent(new Event("submit"));
        });
    });

});
