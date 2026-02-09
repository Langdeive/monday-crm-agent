"""
Monday - Assistente CRM
Arquivo principal consolidado.
"""
import os
import json
from dotenv import load_dotenv
load_dotenv()
import re
from typing import Dict, Any, Optional
from datetime import datetime

# Config
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
TWENTY_URL = os.getenv("TWENTY_API_URL", "")
TWENTY_KEY = os.getenv("TWENTY_API_KEY", os.getenv("TWENTY_KEY", ""))


class GeminiClient:
    """Cliente Gemini simples."""
    
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
    
    async def complete(self, messages: list, temperature: float = 0.3) -> str:
        # Converte para formato Gemini
        conversation = []
        system_msg = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "assistant":
                conversation.append({"role": "model", "parts": [msg["content"]]})
            else:
                content = msg["content"]
                if system_msg and not conversation:
                    content = f"{system_msg}\n\n{content}"
                conversation.append({"role": "user", "parts": [content]})
        
        chat = self.model.start_chat(history=conversation[:-1] if len(conversation) > 1 else [])
        last = conversation[-1]["parts"][0] if conversation else ""
        
        resp = chat.send_message(
            last,
            generation_config={"temperature": temperature, "max_output_tokens": 800}
        )
        return resp.text


class TwentyAPI:
    """API Twenty simplificada."""
    
    async def request(self, method: str, endpoint: str, data: dict = None) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {TWENTY_KEY}"}
            if method != "GET":
                headers["Content-Type"] = "application/json"
            
            url = f"{TWENTY_URL}{endpoint}"
            if method == "GET":
                resp = await client.get(url, headers=headers, timeout=30)
            elif method == "POST":
                # Alguns endpoints usam {data: ...}, outros não
                resp = await client.post(url, headers=headers, json=data, timeout=30)
            else:
                resp = await client.request(method, url, headers=headers, json=data, timeout=30)
            
            resp.raise_for_status()
            return resp.json() if resp.status_code != 204 else {}
    
    async def list_people(self) -> list:
        r = await self.request("GET", "/people?limit=60")
        return r.get("data", {}).get("people", r.get("data", []))
    
    async def create_person(self, name: str, email: str = None, phone: str = None) -> dict:
        data = {"name": name}
        if email:
            data["emails"] = {"primaryEmail": email}
        if phone:
            data["phones"] = {"primaryPhoneNumber": phone}
        return await self.request("POST", "/people", {"data": data})
    
    async def list_tasks(self) -> list:
        r = await self.request("GET", "/tasks?limit=60")
        return r.get("data", {}).get("tasks", r.get("data", []))
    
    async def create_task(self, title: str) -> dict:
        # Tasks não usam wrapper {data: ...}
        return await self.request("POST", "/tasks", {"title": title, "status": "TODO"})


class Memory:
    """Memória SQLite simples."""
    
    def __init__(self, db_path: str = "./data/monday.db"):
        from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON
        from sqlalchemy.orm import declarative_base, sessionmaker
        
        self.Base = declarative_base()
        
        class Conversation(self.Base):
            __tablename__ = "conversations"
            user_id = Column(String, primary_key=True)
            channel = Column(String, primary_key=True)
            current_intent = Column(String)
            current_data = Column(JSON, default=dict)
            updated_at = Column(DateTime)
        
        class Preference(self.Base):
            __tablename__ = "preferences"
            user_id = Column(String, primary_key=True)
            channel = Column(String)
            name = Column(String)
            
        self.Conversation = Conversation
        self.Preference = Preference
        
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_context(self, user_id: str, channel: str) -> dict:
        session = self.Session()
        try:
            conv = session.query(self.Conversation).filter_by(user_id=user_id, channel=channel).first()
            if conv:
                return {
                    "intent": conv.current_intent or "",
                    "data": conv.current_data or {}
                }
            return {"intent": "", "data": {}}
        finally:
            session.close()
    
    def set_context(self, user_id: str, channel: str, intent: str = None, data: dict = None):
        session = self.Session()
        try:
            conv = session.query(self.Conversation).filter_by(user_id=user_id, channel=channel).first()
            if not conv:
                conv = self.Conversation(user_id=user_id, channel=channel)
                session.add(conv)
            
            if intent is not None:
                conv.current_intent = intent
            if data is not None:
                conv.current_data = data
            conv.updated_at = datetime.now()
            
            session.commit()
        finally:
            session.close()
    
    def clear_context(self, user_id: str, channel: str):
        self.set_context(user_id, channel, "", {})


class MondayAgent:
    """Agente Monday - núcleo do sistema."""
    
    def __init__(self):
        self.gemini = GeminiClient()
        self.twenty = TwentyAPI()
        self.memory = Memory()
    
    async def handle(self, user_id: str, channel: str, message: str) -> str:
        # 1. Pega contexto atual
        ctx = self.memory.get_context(user_id, channel)
        
        # 2. Se tem intent em andamento, continua coletando dados
        if ctx["intent"]:
            return await self._continue_action(user_id, channel, message, ctx)
        
        # 3. Nova ação - entende o que usuário quer
        return await self._start_action(user_id, channel, message)
    
    async def _start_action(self, user_id: str, channel: str, message: str) -> str:
        # Usa Gemini para entender
        prompt = f"""Você é Monday, assistente CRM sarcástico.

Analise a mensagem e responda JSON:
{{"intent": "list_people|search_people|search_by_field|create_person|create_task|chat", "params": {{}}, "need_more": false, "thought": ""}}

Mensagem: "{message}"

Intents:
- list_people: listar todos os contatos
- search_people: buscar pessoa por nome (extraia o nome em params.nome)
- search_by_field: buscar quem tem um campo específico preenchido (instagram, linkedin, email, telefone)
- create_person: criar novo contato (precisa nome + email/telefone)
- create_task: criar tarefa (precisa título)
- chat: conversa casual

Exemplos:
"listar pessoas" -> {{"intent": "list_people", "params": {{}}, "need_more": false}}
"tem alguma helena?" -> {{"intent": "search_people", "params": {{"nome": "helena"}}, "need_more": false}}
"quem tem instagram?" -> {{"intent": "search_by_field", "params": {{"campo": "instagram"}}, "need_more": false}}
"tem alguém com linkedin?" -> {{"intent": "search_by_field", "params": {{"campo": "linkedin"}}, "need_more": false}}
"criar tarefa Comprar pão" -> {{"intent": "create_task", "params": {{"titulo": "Comprar pão"}}, "need_more": false}}
"criar pessoa João" -> {{"intent": "create_person", "params": {{"nome": "João"}}, "need_more": true, "thought": "Preciso do email ou telefone"}}
"oi" -> {{"intent": "chat", "params": {{}}, "need_more": false}}

Responda APENAS o JSON, sem markdown."""
        
        try:
            resp = await self.gemini.complete([{"role": "user", "content": prompt}], temperature=0.2)
            parsed = json.loads(resp.strip())
            
            intent = parsed.get("intent", "chat")
            params = parsed.get("params", {})
            need_more = parsed.get("need_more", False)
            
            if intent == "chat":
                return await self._chat(message)
            
            if not need_more:
                # Executa imediatamente
                result = await self._execute(intent, params)
                return result
            else:
                # Salva contexto e pergunta o que falta
                self.memory.set_context(user_id, channel, intent, params)
                thought = parsed.get("thought", "Preciso de mais informações")
                return f"{thought}. Pode me falar?"
        
        except Exception as e:
            return f"Buguei aqui: {str(e)[:100]}. Tenta de novo?"
    
    def _extract_json(self, text: str) -> dict:
        """Extrai JSON de resposta do LLM (pode vir com markdown)."""
        # Tenta extrair JSON de bloco markdown
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        # Fallback: tenta parsear direto
        try:
            return json.loads(text.strip())
        except:
            return {}
    
    async def _continue_action(self, user_id: str, channel: str, message: str, ctx: dict) -> str:
        # Extrai novos dados da mensagem
        prompt = f"""Contexto: estamos executando '{ctx['intent']}'.
Dados já coletados: {json.dumps(ctx['data'])}
Nova mensagem do usuário: "{message}"

Extraia os novos dados mencionados na mensagem e retorne em JSON no formato: {{"novos": {{"campo": "valor"}}}}

Se for criar tarefa e o usuário disser apenas o título (ex: "Comprar pão"), extraia: {{"novos": {{"titulo": "Comprar pão"}}}}
Se for criar pessoa e o usuário disser "joao@teste.com", extraia: {{"novos": {{"email": "joao@teste.com"}}}}

Responda APENAS com o JSON."""
        
        try:
            resp = await self.gemini.complete([{"role": "user", "content": prompt}], temperature=0.1)
            parsed = self._extract_json(resp)
            novos = parsed.get("novos", {})
            
            # Junta dados
            all_data = {**ctx["data"], **novos}
            
            # Verifica se agora tem tudo
            prompt_check = f"""Ação: {ctx['intent']}
Dados: {json.dumps(all_data)}

Tem todos os dados necessários? Responda apenas SIM ou NÃO."""
            
            check = await self.gemini.complete([{"role": "user", "content": prompt_check}], temperature=0.1)
            
            if "SIM" in check.upper():
                # Executa!
                result = await self._execute(ctx["intent"], all_data)
                self.memory.clear_context(user_id, channel)
                return result
            else:
                # Ainda falta
                self.memory.set_context(user_id, channel, ctx["intent"], all_data)
                return "Ainda preciso de mais informações. Qual é?"
        
        except Exception as e:
            return f"Erro: {str(e)[:100]}. Vamos tentar de novo?"
    
    async def _execute(self, intent: str, params: dict) -> str:
        """Executa ação no CRM."""
        try:
            if intent == "list_people":
                people = await self.twenty.list_people()
                if not people:
                    return "Não tem ninguém cadastrado ainda."
                formatted = [self._format_person(p) for p in people[:5]]
                return "Achei esses contatos:\n\n" + "\n\n".join(formatted)
            
            elif intent == "search_people":
                name = params.get("nome", "")
                all_people = await self.twenty.list_people()
                filtered = [p for p in all_people if name.lower() in str(p.get("name", "")).lower()]
                if not filtered:
                    return f"Não achei ninguém com '{name}'."
                formatted = [self._format_person(p) for p in filtered[:5]]
                return f"Resultados para '{name}':\n\n" + "\n\n".join(formatted)
            
            elif intent == "search_by_field":
                campo = params.get("campo", "")
                all_people = await self.twenty.list_people()
                
                # Mapeia nomes comuns para campos da API
                field_map = {
                    "instagram": "instagram",
                    "linkedin": "linkedinLink",
                    "linked": "linkedinLink",
                    "twitter": "xLink",
                    "x": "xLink",
                    "email": "emails",
                    "telefone": "phones",
                    "whatsapp": "phones",
                    "telefone": "phones",
                }
                
                api_field = field_map.get(campo.lower(), campo)
                
                # Filtra pessoas que têm o campo preenchido
                filtered = []
                for p in all_people:
                    field_data = p.get(api_field, {})
                    if isinstance(field_data, dict):
                        # Campos complexos (instagram, linkedin, etc)
                        if field_data.get("primaryLinkUrl") or field_data.get("primaryEmail") or field_data.get("primaryPhoneNumber"):
                            filtered.append(p)
                
                if not filtered:
                    return f"Não achei ninguém com '{campo}' cadastrado."
                
                formatted = [self._format_person(p) for p in filtered[:5]]
                return f"Contatos com {campo}:\n\n" + "\n\n".join(formatted)
            
            elif intent == "create_person":
                name = params.get("nome")
                email = params.get("email")
                phone = params.get("telefone") or params.get("phone")
                await self.twenty.create_person(name, email, phone)
                return f"✅ Contato criado: {name}"
            
            elif intent == "create_task":
                title = params.get("titulo") or params.get("title")
                await self.twenty.create_task(title)
                return f"✅ Tarefa criada: {title}"
            
            else:
                return f"Ação '{intent}' não implementada ainda."
        
        except Exception as e:
            return f"❌ Erro: {str(e)[:150]}"
    
    async def _chat(self, message: str) -> str:
        """Resposta conversacional."""
        prompt = f"""Você é Monday, assistente CRM sarcástico e direto.
Responda de forma natural, como um amigo.

Usuário: {message}

Monday:"""
        
        try:
            resp = await self.gemini.complete([{"role": "user", "content": prompt}], temperature=0.6)
            return resp.strip()
        except:
            return "E aí! O que vamos fazer no CRM hoje?"
    
    def _format_person(self, person: dict) -> str:
        name = person.get("name", "Sem nome")
        if isinstance(name, dict):
            name = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
        
        emails = person.get("emails", {})
        email = emails.get("primaryEmail", "N/A") if isinstance(emails, dict) else "N/A"
        
        phones = person.get("phones", {})
        phone = phones.get("primaryPhoneNumber", "N/A") if isinstance(phones, dict) else "N/A"
        
        # Social links
        instagram = person.get("instagram", {})
        ig_url = instagram.get("primaryLinkUrl", "") if isinstance(instagram, dict) else ""
        
        linkedin = person.get("linkedinLink", {})
        li_url = linkedin.get("primaryLinkUrl", "") if isinstance(linkedin, dict) else ""
        
        x_link = person.get("xLink", {})
        x_url = x_link.get("primaryLinkUrl", "") if isinstance(x_link, dict) else ""
        
        # Monta resposta
        lines = [f"📇 {name}", f"📧 {email}", f"📱 {phone}"]
        
        if ig_url:
            lines.append(f"📷 Instagram: {ig_url}")
        if li_url:
            lines.append(f"💼 LinkedIn: {li_url}")
        if x_url:
            lines.append(f"🐦 X/Twitter: {x_url}")
        
        return "\n".join(lines)


# Singleton
_agent = None

def get_agent() -> MondayAgent:
    global _agent
    if _agent is None:
        _agent = MondayAgent()
    return _agent
