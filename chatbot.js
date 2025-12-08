// Chatbot frontend logic

document.addEventListener('DOMContentLoaded', function () {
    const toggleButton = document.getElementById('chatbot-toggle-button');
    const chatWindow = document.getElementById('chatbot-window');
    const closeButton = document.getElementById('chatbot-close-button');
    const messagesContainer = document.getElementById('chatbot-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    // Configuration
    // Python Flask server address
    const CHATBOT_API_URL = `http://${window.location.hostname}:5001/api/chatbot`;

    const notificationBadge = document.querySelector('.notification-badge');

    // UI toggle logic
    closeButton.addEventListener('click', function () {
        chatWindow.classList.add('hidden');
        // Clear chat history
        messagesContainer.innerHTML = '';
    });

    // Function to add initial welcome message
    function addWelcomeMessage() {
        if (messagesContainer.children.length === 0) {
            const welcomeMsg = `
                <div class="message bot-message">
                    Hello! I am the College Info Bot. How can I help you today?
                </div>
            `;
            messagesContainer.innerHTML = welcomeMsg;
        }
    }

    // Call on load
    addWelcomeMessage();

    // Also ensuring welcome message is there when opening
    toggleButton.addEventListener('click', function () {
        chatWindow.classList.toggle('hidden');
        if (!chatWindow.classList.contains('hidden')) {
            userInput.focus();
            // Hide badge when opened
            notificationBadge.classList.remove('show');
            // Ensure welcome message exists
            addWelcomeMessage();
        }
    });

    // Show notification badge after 5 seconds
    setTimeout(() => {
        if (chatWindow.classList.contains('hidden')) {
            notificationBadge.classList.add('show');
        }
    }, 5000);

    // Message sending logic
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Quick questions logic
    const quickButtons = document.querySelectorAll('.quick-btn');
    quickButtons.forEach(button => {
        button.addEventListener('click', function () {
            const question = this.getAttribute('data-question');
            userInput.value = question;
            sendMessage();
        });
    });
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        // Show user message
        appendMessage(message, 'user-message');
        userInput.value = '';
        const typingIndicator = appendMessage('...', 'bot-message', 'typing-indicator');

        fetch(CHATBOT_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
            .then(response => {
                typingIndicator.remove();

                if (!response.ok) {
                    throw new Error('Network response was not ok: ' + response.statusText);
                }
                return response.json();
            })
            .then(data => {
                // Show bot reply
                const reply = data.reply || "Sorry, I received an empty response from the server.";
                appendMessage(reply, 'bot-message');
            })
            .catch(error => {
                if (document.getElementById('typing-indicator')) {
                    document.getElementById('typing-indicator').remove();
                }
                console.error('Error:', error);
                appendMessage("Error: Could not connect to the chatbot server. Please check the Python backend.", 'bot-message');
            });
    }

    // Helper to display messages
    function appendMessage(text, className, id = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', className);
        messageElement.innerHTML = text;
        if (id) {
            messageElement.id = id;
        }
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return messageElement;
    }


});

