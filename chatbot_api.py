# chatbot_api.py
# Python Backend for the Chatbot System

from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import re
import os

# --- Configuration ---
# MySQL 
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'chatbot_db',
    'auth_plugin': 'mysql_native_password'
}

app = Flask(__name__)
# Enable CORS for the frontend (running on a different port/server)
CORS(app)

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def find_answer_by_keywords(user_message):
    """
    Core logic for the rule-based chatbot.
    Searches the database for a matching answer based on keywords.
    """
    # 1. Normalize the user message
    normalized_message = re.sub(r'[^\w\s]', '', user_message).lower()
    words = normalized_message.split()
    
    fallback_answer = "I'm sorry, I don't have information on that topic."

    # Define stop words to ignore in SQL search (but keep for scoring)
    STOP_WORDS = {'how', 'do', 'i', 'you', 'what', 'are', 'the', 'a', 'an', 'of', 'in', 'on', 'for', 'to', 'can', 'my'}
    search_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    if not search_words:
        # If query is only stop words (e.g. "How are you?"), search everything or fall back
        # For now, let's try to match exact phrases if possible, or just return fallback
        if len(words) > 0:
             search_words = words # Fallback to searching all words if no keywords found
        else:
             return fallback_answer

    # 3. Connect to the database
    conn = get_db_connection()
    if not conn:
        return "Sorry, I'm having trouble connecting to my knowledge base right now."

    cursor = conn.cursor(dictionary=True)
    
    # 4. Search for a match
    search_conditions = []
    search_params = []
    for word in search_words:
        search_conditions.append("keywords LIKE %s")
        search_params.append(f"%{word}%")
            
    # Fetch ALL potential matches
    sql_query = "SELECT id, question, answer, keywords FROM qa_pairs WHERE " + " OR ".join(search_conditions)
    
    try:
        cursor.execute(sql_query, search_params)
        results = cursor.fetchall()
        
        if not results:
            return fallback_answer

        # Scoring Logic: Find the best match
        best_answer = None
        max_score = 0

        for row in results:
            # --- Score Calculation ---
            
            # 1. Jaccard Similarity on Question Text
            # Intersection of words / Union of words
            # Use improved preprocessing with singularization
            row_q_words_set, _ = preprocess_text(row['question'])
            
            # Use the singularized user words for comparison
            user_words_singular = {singularize(w) for w in search_words} # search_words are already filtered
            
            intersection = user_words_singular.intersection(row_q_words_set)
            union = user_words_singular.union(row_q_words_set)
            
            jaccard_score = len(intersection) / len(union) if union else 0
            
            # Boost exact matches significantly (on original text)
            row_question_normalized = re.sub(r'[^\w\s]', '', row['question']).lower()
            if row_question_normalized == normalized_message:
                jaccard_score = 3.0 # Perfect match override
            
            # 2. Keyword Matching Score (Secondary)
            keyword_score = 0
            row_keywords = [k.strip().lower() for k in row['keywords'].split(',')]
            
            for keyword in row_keywords:
                if not keyword: continue
                
                # Check for phrase matches in the full message
                if keyword in normalized_message:
                    keyword_score += 5 
                    if keyword == normalized_message:
                        keyword_score += 2
                else:
                    # Partial matching with singularization support
                    # If keyword is "documents" and user has "document", we want a match
                    keyword_singular = singularize(keyword)
                    
                    # Check against user's original words
                    for word in words:
                        if word in STOP_WORDS: continue
                        word_singular = singularize(word)
                        
                        # Match if singular versions match
                        if keyword_singular == word_singular:
                             keyword_score += 3 # Good match
                        elif len(keyword) > 3 and keyword in word: # Substring match
                             keyword_score += 0.5

            # Final Weighted Score
            # Jaccard is 0-1. Keyword is integer. 
            # We increase Jaccard weight because it represents "semantic" understanding of the question structure
            final_score = (jaccard_score * 15) + keyword_score

            # Debug print
            # print(f"ID: {row['id']}, Jac: {jaccard_score:.2f}, Kw: {keyword_score}, Final: {final_score:.2f}, Q: {row['question']}")

            if final_score > max_score:
                max_score = final_score
                best_answer = row['answer']
        
        if best_answer and max_score > 2.0: # Increased threshold due to higher weights
            return best_answer
        else:
            return fallback_answer
            
    except mysql.connector.Error as err:
        print(f"SQL Error: {err}")
        return "An internal error occurred while searching for an answer."
        
    finally:
        cursor.close()
        conn.close()

def singularize(word):
    """Simple helper to remove trailing 's' for basic singularization."""
    if word.endswith('s') and len(word) > 3:
        return word[:-1]
    return word

def preprocess_text(text):
    """Normalize text and return a set of singularized base words."""
    # 1. Lowercase and remove punctuation
    text = re.sub(r'[^\w\s]', '', text).lower()
    # 2. Split into words
    words = text.split()
    # 3. Remove stop words and singularize
    STOP_WORDS = {'how', 'do', 'i', 'you', 'what', 'are', 'the', 'a', 'an', 'of', 'in', 'on', 'for', 'to', 'can', 'my', 'is', 'please', 'required'}
    processed_words = set()
    for w in words:
        if w not in STOP_WORDS and len(w) > 1:
            processed_words.add(singularize(w))
    return processed_words, words # Return set for comparison, list for phrase matching

@app.route('/')
def index():
    """Root endpoint to guide users to the frontend."""
    # Get the host (IP:PORT) from the request
    host = request.host.split(':')[0]
    frontend_url = f"http://{host}/Rulebasedchatbot/"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chatbot API Status | Active</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #4f46e5;
                --primary-hover: #4338ca;
                --bg: #f3f4f6;
                --card-bg: #ffffff;
                --text: #1f2937;
                --text-light: #6b7280;
                --success: #10b981;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Inter', sans-serif;
                background: var(--bg);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--text);
            }}
            .card {{
                background: var(--card-bg);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
                text-align: center;
                max-width: 450px;
                width: 90%;
                animation: float 6s ease-in-out infinite;
                position: relative;
                overflow: hidden;
            }}
            @keyframes float {{
                0% {{ transform: translateY(0px); }}
                50% {{ transform: translateY(-10px); }}
                100% {{ transform: translateY(0px); }}
            }}
            .status-indicator {{
                width: 80px;
                height: 80px;
                background: rgba(16, 185, 129, 0.1);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 24px;
                position: relative;
            }}
            .dot {{
                width: 20px;
                height: 20px;
                background: var(--success);
                border-radius: 50%;
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 20px rgba(16, 185, 129, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
            }}
            h1 {{
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 12px;
            }}
            p {{
                color: var(--text-light);
                line-height: 1.6;
                margin-bottom: 32px;
            }}
            .btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: var(--primary);
                color: white;
                text-decoration: none;
                padding: 12px 28px;
                border-radius: 12px;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);
            }}
            .btn:hover {{
                background: var(--primary-hover);
                transform: translateY(-2px);
                box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
            }}
            .footer {{
                margin-top: 24px;
                font-size: 12px;
                color: var(--text-light);
                opacity: 0.7;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="status-indicator">
                <div class="dot"></div>
            </div>
            <h1>System Operational</h1>
            <p>The Chatbot Backend API is running smoothly. To interact with the bot, please visit the frontend interface.</p>
            <a href="{frontend_url}" class="btn">Launch Interface</a>
            <div class="footer">Version 2.0 • Active</div>
        </div>
    </body>
    </html>
    """
    return html_content


@app.route('/api/contact', methods=['POST'])
def contact_endpoint():
    """Endpoint to handle contact form submissions."""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    subject = data.get('subject')
    message = data.get('message')

    if not all([name, email, subject, message]):
        return jsonify({'error': 'All fields are required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO contact_messages (name, email, subject, message) VALUES (%s, %s, %s, %s)",
            (name, email, subject, message)
        )
        conn.commit()
        return jsonify({'message': 'Message sent successfully!'}), 200
    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Failed to save message.'}), 500
    finally:
        conn.close()

@app.route('/api/chatbot', methods=['POST'])
def chatbot_endpoint():
    """The main API endpoint for the chatbot."""
    # 1. Get the JSON data sent from the frontend
    data = request.get_json()
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'reply': 'Please provide a message.'}), 400

    # 2. Process the message and get the answer
    chatbot_reply = find_answer_by_keywords(user_message)
    
    # 3. Return the answer as a JSON response
    return jsonify({'reply': chatbot_reply})

# --- Run the application ---
if __name__ == '__main__':
    # Run on port 5000, which is a common port for development APIs
    # The frontend will need to know this address (e.g., http://localhost:5000)
    app.run(host='0.0.0.0', debug=False, port=5001)
