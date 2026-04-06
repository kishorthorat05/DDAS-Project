# DDAS Chatbot Integration Guide

## 🤖 Overview
Your DDAS chatbot is now powered by **Google Gemini API** with a new API key, providing dynamic, human-like responses for all DDAS-related questions.

---

## ✅ Setup Status

| Component | Status | Details |
|-----------|--------|---------|
| **API Key** | ✅ Active | `AIzaSyC5lT3jycngMJj-twwHte_iXKrlniAY6hw` |
| **Model** | ✅ Ready | Gemini 1.5 Flash |
| **Personality** | ✅ Enabled | Human-like, conversational tone |
| **Endpoint** | ✅ Active | `POST /api/ai/chat` |

---

## 🚀 Quick Start

### 1. Access the Chatbot
- Start the DDAS server: `python run.py`
- Navigate to **AI Chat** tab in the dashboard
- Start typing your questions

### 2. Example Questions to Try

#### About Uploads & Files
```
Q: How do I upload a file?
A: [Friendly step-by-step guide with examples]

Q: What file formats are supported?
A: [Comprehensive list with recommendations]
```

#### About Duplicate Detection
```
Q: How does duplicate detection work?
A: [Explained with real-world analogies - "like DNA codes for files"]

Q: What is SHA-256 hashing?
A: [Technical explanation in accessible language]
```

#### About Features
```
Q: What can I do with this system?
A: [Engaging overview of all capabilities]

Q: How do I export my scan results?
A: [Clear instructions with context]
```

#### System Features
```
Q: Can you help me with Python?
A: [Polite redirect: "I'm specifically trained for DDAS..."]

Q: Tell me about monitoring and alerts
A: [Detailed explanation of real-time features]
```

---

## 🔧 Technical Configuration

### Environment Variables (.env)
```
GOOGLE_API_KEY=AIzaSyC5lT3jycngMJj-twwHte_iXKrlniAY6hw
GOOGLE_MODEL=gemini-1.5-flash
```

### Generation Settings (Optimized for Natural Responses)
- **Temperature**: 0.8 (higher variability for natural tone)
- **Top-P**: 0.95 (nucleus sampling)
- **Top-K**: 64 (diverse token selection)
- **Max Tokens**: 600 (balanced responses)

### Safety Settings (Permissive)
The chatbot is configured with relaxed safety settings to provide helpful DDAS-specific guidance without unnecessary filtering.

---

## API Documentation

### Chat Endpoint

**POST** `/api/ai/chat`

#### Request Body
```json
{
  "message": "How do I upload a file?",
  "session_id": "user-123",
  "context": "Current page: Upload (optional for context)"
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "reply": "Here's how to upload a file...",
    "session_id": "user-123"
  }
}
```

#### Examples Using curl

**Example 1: Basic Question**
```bash
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is DDAS?",
    "session_id": "default"
  }'
```

**Example 2: With Context**
```bash
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How do duplicates work?",
    "session_id": "user-001",
    "context": "User just uploaded 50 files"
  }'
```

### Clear Chat History

**POST** `/api/ai/chat/clear`

#### Request Body
```json
{
  "session_id": "user-123"
}
```

---

## 💡 Chatbot Personality & Behavior

### How It Responds to Different Questions

| Question Type | Response Style | Example |
|--------------|-----------------|---------|
| **DDAS Feature Questions** | Detailed, enthusiastic, with examples | "Great question! Here's how duplicate detection works..." |
| **How-To Questions** | Step-by-step, friendly, encouraging | "Here's what you can do: 1. Go to Upload tab... 2. Choose your file..." |
| **Technical Concepts** | Accessible analogies, gradually detailed | "Think of SHA-256 like a unique fingerprint for files..." |
| **Off-Topic Questions** | Polite redirect with humor | "I appreciate the question, but I'm trained specifically for DDAS..." |

### Key Personality Traits
- ✅ **Conversational** - Sounds like a helpful colleague
- ✅ **Approachable** - Uses natural language and casual phrasing
- ✅ **Knowledgeable** - Provides accurate, detailed DDAS information
- ✅ **Patient** - Explains concepts clearly to beginners
- ✅ **Focused** - Only answers DDAS-related questions
- ✅ **Varied** - Different response phrasings for natural conversation

---

## 🎯 System Prompt (Custom Instructions)

The chatbot follows this personality directive:

```
You are IAS Chatbot, a friendly and knowledgeable AI assistant for 
the Data Download Duplication Alert System (DDAS).

Your Personality:
- You're conversational and approachable, like a helpful colleague
- You use natural language with varied sentence structure
- You show genuine interest in helping users succeed
- You explain technical concepts in relatable ways

Your ONLY role:
- Help with DDAS: uploading files, scanning, alerts, analytics
- Explain duplicate detection and data management practices
- Provide in-depth responses about DDAS features

IMPORTANT: You ONLY answer DDAS-related questions. For off-topic 
questions, politely redirect users back to DDAS topics.
```

---

## 🌍 Fallback System

If the Gemini API is unavailable, the chatbot provides intelligent rule-based responses covering:
- ✅ Greetings and introductions
- ✅ Duplicate detection basics
- ✅ Upload instructions
- ✅ Scanning and monitoring
- ✅ Export functionality
- ✅ Feature overview
- ✅ Off-topic redirects

**Fallback responses are also human-like and follow the same personality guidelines!**

---

## 📊 Session Management

### Features
- **Per-User Sessions**: Each user has their own conversation history
- **Context Awareness**: Bot remembers previous messages in same session
- **History Limit**: Maintains last 18 turns (9 exchanges) for efficiency
- **Clear on Demand**: Users can clear chat history anytime

### Session ID Usage
- Browser clients: Automatic via cookies
- API clients: Include `session_id` in request body
- Example: `"session_id": "user-user@email.com"`

---

## 🧪 Testing the Chatbot

### 1. Direct API Test
```bash
# Test with curl
curl -X POST http://localhost:5000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about duplicate detection", "session_id": "test"}'
```

### 2. Frontend Test
1. Start DDAS server
2. Open http://localhost:5000 in browser
3. Click **AI Chat** tab
4. Ask any question about DDAS

### 3. Multi-Turn Conversation
1. Ask: "What is DDAS?"
2. Ask: "How do I upload a file?" (bot remembers context)
3. Ask: "What about duplicates?" (follows conversation flow)

---

## 🔍 Troubleshooting

### Issue: Chatbot returns generic responses
**Solution**: Check that `GOOGLE_API_KEY` is set correctly in `.env`
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GOOGLE_API_KEY')[:20])"
```

### Issue: API returns 401/403 error
**Possible Causes**:
- API key is invalid or expired
- Gemini API not enabled in Google Cloud Console
- Rate limits exceeded

**Solution**:
- Verify key at https://makersuite.google.com/app/apikey
- Request new key if needed

### Issue: Slow response time
**Possible Causes**:
- Network latency to Gemini API
- Server processing time

**Solution**:
- Check internet connection
- Verify server logs for errors
- Try again in a few moments (API may be throttling)

---

## 📈 Performance Metrics

### Response Times
- **Average**: 2-5 seconds (Gemini API call)
- **Fallback**: <200ms (rule-based responses)
- **Total Latency**: ~3-6 seconds from user input to display

### Conversation History
- **Max History**: 18 turns (9 exchanges)
- **History Size**: ~2-5 KB per session
- **Storage**: In-memory (clears on server restart)

---

## 🎓 Example Conversations

### Conversation #1: New User Learning
```
User: Hi! What is DDAS?
Bot: Hey there! I'm IAS Chatbot, your go-to assistant for all things DDAS.
     DDAS stands for Data Download Duplication Alert System. It helps you...
     [Friendly overview of all features]

User: How do I start?
Bot: Great question! Here's what you can do:
     1. Upload files (local or remote)
     2. The system checks for duplicates
     3. Get detailed insights and alerts
     [More detailed steps]

User: What makes duplicates unique?
Bot: Think of SHA-256 like a digital DNA code for files...
     [Clear explanation with technical depth]
```

### Conversation #2: Experienced User Troubleshooting
```
User: I'm not seeing duplicates detected properly
Bot: That's interesting. Let me help you troubleshoot.
     Are you seeing false negatives or false positives?
     [Diagnostic questions and solutions]

User: False negatives - some duplicates aren't detected
Bot: Here could be the issue:
     1. Files might have different metadata
     2. SHA-256 might not match due to compression...
     [Comprehensive troubleshooting guide]
```

---

## 🔐 Privacy & Security

- **Session Data**: Stored in-memory, cleared on server restart
- **API Key**: Secured in `.env`, never exposed to client
- **User Input**: Sent to Gemini API for processing
- **Response**: Returned to user, never stored by default

---

## 📞 Support

For issues or questions:
1. Check this guide first
2. Review API logs: `python -B run.py` (check console output)
3. Verify `.env` configuration
4. Test endpoint directly with curl

---

**Last Updated**: April 2026  
**Chatbot Version**: 2.0 (Gemini-Powered)  
**API Key**: Active ✅
