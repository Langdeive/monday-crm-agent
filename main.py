"""
Monday CRM Agent - Web Server
FastAPI + WebSocket + Telegram Bot
"""
import os
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from agent_v2 import get_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan do app."""
    print("[Monday] Iniciando...")
    yield
    print("[Monday] Desligando...")


app = FastAPI(title="Monday CRM Agent", lifespan=lifespan)


# WebSocket para web
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    import uuid
    session_id = str(uuid.uuid4())
    
    agent = get_agent()
    print(f"[Web] Cliente conectado: {session_id}")
    
    try:
        while True:
            message = await websocket.receive_text()
            print(f"[Web] {session_id[:8]}... recebeu: {message[:50]}")
            response = await agent.handle(session_id, "web", message)
            print(f"[Web] {session_id[:8]}... respondeu: {response[:50]}...")
            await websocket.send_text(response)
    except WebSocketDisconnect:
        print(f"[Web] Cliente desconectado: {session_id}")
    except Exception as e:
        print(f"[Web] Erro: {e}")


# Interface web
@app.get("/", response_class=HTMLResponse)
async def web_interface():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Monday CRM Agent</title>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; height: 100vh; display: flex; flex-direction: column; }
        .header { background: #1a73e8; color: white; padding: 1rem; text-align: center; }
        .chat { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
        .msg { max-width: 80%; padding: 0.75rem 1rem; border-radius: 1rem; word-wrap: break-word; }
        .user { align-self: flex-end; background: #1a73e8; color: white; }
        .bot { align-self: flex-start; background: white; }
        .input-area { background: white; padding: 1rem; border-top: 1px solid #ddd; display: flex; gap: 0.5rem; }
        input { flex: 1; padding: 0.75rem; border: 1px solid #ddd; border-radius: 1.5rem; outline: none; }
        button { padding: 0.75rem 1.5rem; background: #1a73e8; color: white; border: none; border-radius: 1.5rem; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Monday CRM Agent</h1>
    </div>
    <div class="chat" id="chat">
        <div class="msg bot">Olá! Como posso ajudar?</div>
    </div>
    <div class="input-area">
        <input type="text" id="msg" placeholder="Digite sua mensagem..." onkeypress="if(event.key==='Enter')send()">
        <button onclick="send()">Enviar</button>
    </div>
    
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws/chat`);
        const chat = document.getElementById('chat');
        const input = document.getElementById('msg');
        
        ws.onmessage = (e) => {
            const div = document.createElement('div');
            div.className = 'msg bot';
            div.textContent = e.data;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        };
        
        function send() {
            const text = input.value.trim();
            if (text) {
                const div = document.createElement('div');
                div.className = 'msg user';
                div.textContent = text;
                chat.appendChild(div);
                ws.send(text);
                input.value = '';
                chat.scrollTop = chat.scrollHeight;
            }
        }
    </script>
</body>
</html>
"""


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "monday"}


def main():
    """Entry point."""
    port = int(os.getenv("PORT", "8001"))
    
    # Inicia Telegram bot em paralelo se configurado
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        import threading
        def run_telegram():
            import asyncio
            from telegram import Update
            from telegram.ext import Application, MessageHandler, filters
            
            async def handle_tg(update: Update, context):
                agent = get_agent()
                user_id = str(update.effective_user.id)
                message = update.message.text
                response = await agent.handle(user_id, "telegram", message)
                await update.message.reply_text(response)
            
            app_tg = Application.builder().token(token).build()
            app_tg.add_handler(MessageHandler(filters.TEXT, handle_tg))
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(app_tg.run_polling())
        
        threading.Thread(target=run_telegram, daemon=True).start()
        print("[Monday] Telegram bot iniciado")
    
    # Inicia servidor web
    print(f"[Monday] Servidor web na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
