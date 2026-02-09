"""
Monday Agent v2 - Dynamic Tool Use
LLM decide qual ferramenta usar baseado na pergunta
"""
import os
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
TWENTY_URL = os.getenv("TWENTY_API_URL", "")
TWENTY_KEY = os.getenv("TWENTY_API_KEY", os.getenv("TWENTY_KEY", ""))


# =============================================================================
# TOOLS - Ferramentas disponíveis para o LLM
# =============================================================================

class Tools:
    """Todas as ferramentas disponíveis para o agente."""
    
    def __init__(self):
        self.client = None  # Inicializado depois
    
    async def _api_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {TWENTY_KEY}"}
            if method != "GET":
                headers["Content-Type"] = "application/json"
            
            url = f"{TWENTY_URL.rstrip('/')}{endpoint}"
            if method == "GET":
                resp = await client.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=data, timeout=30)
            else:
                resp = await client.request(method, url, headers=headers, json=data, timeout=30)
            
            resp.raise_for_status()
            return resp.json() if resp.status_code != 204 else {}
    
    # ---------- PESSOAS ----------
    async def list_people(self, limit: int = 50) -> str:
        """Lista todos os contatos/pessoas do CRM"""
        r = await self._api_request("GET", f"/people?limit={limit}")
        people = r.get("data", {}).get("people", r.get("data", []))
        return self._format_people_list(people)
    
    async def search_people(self, name: str) -> str:
        """Busca pessoas por nome"""
        r = await self._api_request("GET", "/people?limit=100")
        all_people = r.get("data", {}).get("people", r.get("data", []))
        filtered = [p for p in all_people if name.lower() in str(p.get("name", "")).lower()]
        if not filtered:
            return f"Não achei ninguém com '{name}'."
        return self._format_people_list(filtered)
    
    async def search_people_by_field(self, field: str) -> str:
        """Busca pessoas que têm um campo específico preenchido (instagram, linkedin, email, phone)"""
        r = await self._api_request("GET", "/people?limit=100")
        all_people = r.get("data", {}).get("people", r.get("data", []))
        
        field_map = {
            "instagram": "instagram", "linkedin": "linkedinLink", "linked": "linkedinLink",
            "twitter": "xLink", "x": "xLink", "email": "emails", "telefone": "phones",
            "whatsapp": "phones", "phone": "phones"
        }
        api_field = field_map.get(field.lower(), field)
        
        filtered = []
        for p in all_people:
            field_data = p.get(api_field, {})
            if isinstance(field_data, dict):
                if field_data.get("primaryLinkUrl") or field_data.get("primaryEmail") or field_data.get("primaryPhoneNumber"):
                    filtered.append(p)
        
        if not filtered:
            return f"Não achei ninguém com '{field}' cadastrado."
        return f"Contatos com {field}:\n\n" + self._format_people_list(filtered)
    
    async def create_person(self, name: str, email: str = None, phone: str = None, company: str = None) -> str:
        """Cria uma nova pessoa/contato. Opcionalmente associa a uma empresa."""
        # Divide nome em firstName e lastName
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else name
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        data = {"name": {"firstName": first_name, "lastName": last_name}}
        if email:
            data["emails"] = {"primaryEmail": email}
        if phone:
            data["phones"] = {"primaryPhoneNumber": phone}
        
        # Se informou empresa, busca ou cria
        if company:
            company_id = await self._get_or_create_company(company)
            if company_id:
                data["companyId"] = company_id
        
        await self._api_request("POST", "/people", data)
        company_msg = f" (empresa: {company})" if company else ""
        return f"✅ Contato criado: {name}{company_msg}"
    
    async def _get_or_create_company(self, name: str) -> str:
        """Busca empresa pelo nome, cria se não existir. Retorna o ID."""
        try:
            # Busca empresas
            r = await self._api_request("GET", "/companies?limit=100")
            companies = r.get("data", {}).get("companies", r.get("data", []))
            
            # Procura por nome similar
            name_lower = name.lower()
            for c in companies:
                c_name = c.get("name", "")
                if isinstance(c_name, dict):
                    c_name = f"{c_name.get('firstName', '')} {c_name.get('lastName', '')}".strip()
                if name_lower in c_name.lower() or c_name.lower() in name_lower:
                    return c.get("id")
            
            # Cria nova empresa
            create_data = {"data": {"name": name}}
            result = await self._api_request("POST", "/companies", create_data)
            return result.get("data", {}).get("id")
        except Exception as e:
            print(f"[Warning] Erro ao buscar/criar empresa: {e}")
            return None
    
    # ---------- OPORTUNIDADES ----------
    async def list_opportunities(self, stage: str = None, limit: int = 50) -> str:
        """Lista oportunidades. Opcionalmente filtra por etapa/pipeline stage."""
        r = await self._api_request("GET", f"/opportunities?limit={limit}")
        opportunities = r.get("data", {}).get("opportunities", r.get("data", []))
        
        if stage:
            opportunities = self._filter_by_stage(opportunities, stage)
        
        return self._format_opportunities_list(opportunities)
    
    async def count_opportunities(self, stage: str = None) -> str:
        """Conta quantas oportunidades existem, opcionalmente filtradas por etapa"""
        r = await self._api_request("GET", "/opportunities?limit=1000")
        opportunities = r.get("data", {}).get("opportunities", r.get("data", []))
        
        if stage:
            opportunities = self._filter_by_stage(opportunities, stage)
            return f"📊 {len(opportunities)} oportunidades na etapa '{stage}'"
        
        return f"📊 Total de oportunidades: {len(opportunities)}"
    
    async def create_opportunity(self, name: str, stage: str = "PROSPECCAO", amount: float = None, company: str = None, person: str = None) -> str:
        """Cria uma nova oportunidade."""
        # Mapeia nomes de etapas para códigos
        stage_map = {
            "prospeccao": "PROSPECCAO", "prospeção": "PROSPECCAO",
            "contato iniciado": "CONTATO_INICIADO", "conversa estabelecida": "CONVERSA_ESTABELECIDA",
            "qualificado": "QUALIFICADO", "qualificada": "QUALIFICADO",
            "negociacao": "NEGOCIACAO", "negociação": "NEGOCIACAO",
            "fechado ganho": "FECHADO_GANHO", "ganho": "FECHADO_GANHO",
            "fechado perdido": "FECHADO_PERDIDO", "perdido": "FECHADO_PERDIDO",
        }
        stage_code = stage_map.get(stage.lower(), stage.upper().replace(" ", "_"))
        
        data = {
            "name": name,
            "stage": stage_code
        }
        
        if amount:
            data["amount"] = {"amountMicros": int(amount * 1_000_000), "currencyCode": "BRL"}
        
        # Busca empresa
        if company:
            company_id = await self._get_or_create_company(company)
            if company_id:
                data["companyId"] = company_id
        
        # Busca pessoa
        if person:
            person_id = await self._search_person_id(person)
            if person_id:
                data["pointOfContactId"] = person_id
        
        await self._api_request("POST", "/opportunities", {"data": data})
        return f"✅ Oportunidade criada: {name} (etapa: {stage_code})"
    
    async def _search_person_id(self, name: str) -> str:
        """Busca pessoa pelo nome e retorna o ID."""
        try:
            r = await self._api_request("GET", "/people?limit=100")
            people = r.get("data", {}).get("people", r.get("data", []))
            
            name_lower = name.lower()
            for p in people:
                p_name = p.get("name", "")
                if isinstance(p_name, dict):
                    p_name = f"{p_name.get('firstName', '')} {p_name.get('lastName', '')}".strip()
                if name_lower in p_name.lower():
                    return p.get("id")
        except Exception as e:
            print(f"[Warning] Erro ao buscar pessoa: {e}")
        return None
    
    def _filter_by_stage(self, opportunities: list, stage_query: str) -> list:
        """Filtra oportunidades por etapa."""
        stage_query = stage_query.lower().replace("_", " ").replace("-", " ")
        
        # Mapeamento de nomes comuns para códigos de stage
        stage_mapping = {
            "prospeccao": ["prospeccao", "prospeção", "prospeccao"],
            "conversa estabelecida": ["conversa estabelecida", "conversa", "conversa_estabelecida"],
            "qualificado": ["qualificado", "qualificada"],
            "negociacao": ["negociacao", "negociação", "negociando"],
            "fechado": ["fechado", "fechada", "ganho", "ganhos"],
        }
        
        # Encontra qual código de stage corresponde à query
        target_stages = []
        for key, variations in stage_mapping.items():
            if any(v in stage_query for v in variations):
                target_stages = variations
                break
        
        if not target_stages:
            target_stages = [stage_query]
        
        filtered = []
        for opp in opportunities:
            # Stage pode ser string ou objeto
            opp_stage = opp.get("stage", "")
            if isinstance(opp_stage, dict):
                opp_stage = opp_stage.get("name", "")
            opp_stage = str(opp_stage).lower()
            
            if any(t in opp_stage for t in target_stages):
                filtered.append(opp)
        
        return filtered
    
    # ---------- TAREFAS ----------
    async def list_tasks(self) -> str:
        """Lista todas as tarefas"""
        r = await self._api_request("GET", "/tasks?limit=50")
        tasks = r.get("data", {}).get("tasks", r.get("data", []))
        return self._format_tasks_list(tasks)
    
    async def create_task(self, title: str, due_date: str = None) -> str:
        """Cria uma nova tarefa. Opcionalmente com data de vencimento (formato ISO 8601)"""
        data = {"title": title, "status": "TODO"}
        if due_date:
            data["dueAt"] = due_date
        await self._api_request("POST", "/tasks", data)
        if due_date:
            # Formata data para exibição amigável
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                data_fmt = dt.strftime('%d/%m/%Y %H:%M')
                return f"✅ Tarefa criada: {title} (para {data_fmt})"
            except:
                return f"✅ Tarefa criada: {title} (para {due_date})"
        return f"✅ Tarefa criada: {title}"
    
    # ---------- EMPRESAS ----------
    async def list_companies(self) -> str:
        """Lista todas as empresas"""
        r = await self._api_request("GET", "/companies?limit=50")
        companies = r.get("data", {}).get("companies", r.get("data", []))
        return self._format_companies_list(companies)
    
    async def get_current_datetime(self) -> str:
        """Retorna a data e hora atual em São Paulo, Brasil"""
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(tz)
        
        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        
        dia_semana = dias_semana[now.weekday()]
        dia = now.day
        mes = meses[now.month]
        ano = now.year
        hora = now.strftime('%H:%M')
        
        return f"📅 {dia_semana}, {dia} de {mes} de {ano} - {hora} (São Paulo, BR)"
    
    # ---------- HELPERS ----------
    def _format_people_list(self, people: list) -> str:
        if not people:
            return "Nenhum contato encontrado."
        lines = []
        for p in people[:10]:
            name = p.get("name", {})
            if isinstance(name, dict):
                name = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
            lines.append(f"• {name}")
        return "\n".join(lines)
    
    def _format_opportunities_list(self, opps: list) -> str:
        if not opps:
            return "Nenhuma oportunidade encontrada."
        lines = []
        for o in opps[:10]:
            name = o.get("name", "Sem nome")
            
            # Stage pode ser string ou objeto
            stage = o.get("stage", "Sem etapa")
            if isinstance(stage, dict):
                stage = stage.get("name", "Sem etapa")
            
            # Valor
            amount_data = o.get("amount", {})
            amount_micros = amount_data.get("amountMicros") if isinstance(amount_data, dict) else None
            if amount_micros and isinstance(amount_micros, (int, float)):
                amount = amount_micros / 1_000_000
                currency = amount_data.get("currencyCode", "BRL")
                value = f"R$ {amount:,.0f}"
            else:
                value = "Valor não definido"
            
            lines.append(f"• {name} | {stage} | {value}")
        return "\n".join(lines)
    
    def _format_tasks_list(self, tasks: list) -> str:
        if not tasks:
            return "Nenhuma tarefa encontrada."
        lines = []
        for t in tasks[:10]:
            title = t.get("title", "Sem título")
            status = t.get("status", "TODO")
            lines.append(f"• [{status}] {title}")
        return "\n".join(lines)
    
    def _format_companies_list(self, companies: list) -> str:
        if not companies:
            return "Nenhuma empresa encontrada."
        lines = []
        for c in companies[:10]:
            # Name pode ser string ou objeto
            name = c.get("name", "Sem nome")
            if isinstance(name, dict):
                name = name.get("firstName", "") + " " + name.get("lastName", "")
                name = name.strip() or "Sem nome"
            
            # Domain pode ser string ou objeto
            domain = c.get("domainName", "")
            if isinstance(domain, dict):
                domain = domain.get("primaryLinkUrl", "")
            
            lines.append(f"• {name}" + (f" ({domain})" if domain else ""))
        return "\n".join(lines)


# =============================================================================
# AGENTE
# =============================================================================

class MondayAgent:
    """Agente Monday com Tool Use dinâmico."""
    
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        self.model = genai.GenerativeModel(GEMINI_MODEL)
        self.tools = Tools()
        self.memory = self._init_memory()
    
    def _init_memory(self):
        from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON
        from sqlalchemy.orm import declarative_base, sessionmaker
        
        Base = declarative_base()
        
        class Conversation(Base):
            __tablename__ = "conversations"
            user_id = Column(String, primary_key=True)
            channel = Column(String, primary_key=True)
            current_intent = Column(String)
            current_data = Column(JSON, default=dict)
            updated_at = Column(DateTime)
        
        os.makedirs("./data", exist_ok=True)
        engine = create_engine("sqlite:///./data/monday.db")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        
        return {"base": Base, "session": Session, "Conversation": Conversation}
    
    async def handle(self, user_id: str, channel: str, message: str) -> str:
        # Verifica se há contexto pendente
        ctx = self._get_context(user_id, channel)
        if ctx.get("intent"):
            return await self._continue_context(user_id, channel, message, ctx)
        
        # Nova pergunta - LLM decide qual tool usar
        return await self._process_with_tools(user_id, channel, message)
    
    async def _process_with_tools(self, user_id: str, channel: str, message: str) -> str:
        """Processa usando Function Calling."""
        
        # System prompt com as tools disponíveis
        system_prompt = """Você é Monday, assistente CRM sarcástico e direto.

FERRAMENTAS DISPONÍVEIS:
1. list_people() - Lista todos os contatos
2. search_people(name: string) - Busca pessoas por nome
3. search_people_by_field(field: string) - Busca por campo (instagram, linkedin, email, phone)
4. create_person(name: string, email?: string, phone?: string, company?: string) - Cria APENAS o contato/pessoa
5. list_opportunities(stage?: string) - Lista oportunidades
6. count_opportunities(stage?: string) - Conta oportunidades
7. create_opportunity(name: string, stage: string, company?: string, person?: string, amount?: number) - Cria APENAS a oportunidade (venda/negócio)
8. list_tasks() - Lista tarefas
9. create_task(title: string, due_date?: string) - Cria tarefa. due_date opcional no formato ISO 8601
10. list_companies() - Lista empresas
11. get_current_datetime() - Retorna data/hora atual de São Paulo
12. chat(message: string) - Conversa casual

REGRAS IMPORTANTES:
- Se o usuário pedir para "cadastrar uma oportunidade", use create_opportunity (NÃO create_person)
- Se o usuário pedir para "cadastrar uma pessoa/contato", use create_person (NÃO create_opportunity)
- São coisas DIFERENTES: pessoa = contato, oportunidade = negócio/venda em andamento
- Se o usuário mencionar data/hora na tarefa, converta para ISO 8601 e use due_date
- Se precisar de mais informações, pergunte de forma sarcástica
- Se for conversa casual, use a tool "chat"

Responda em JSON:
{"tool": "nome_da_tool", "params": {"param": "valor"}, "need_more": false, "thought": ""}"""

        try:
            # Chama o LLM
            chat = self.model.start_chat()
            resp = chat.send_message(
                f"{system_prompt}\n\nPergunta do usuário: \"{message}\"\n\nResponda apenas o JSON:",
                generation_config={"temperature": 0.2, "max_output_tokens": 500}
            )
            
            # Parse da resposta
            result = self._extract_json(resp.text)
            tool_name = result.get("tool", "chat")
            params = result.get("params", {})
            need_more = result.get("need_more", False)
            
            # Se precisa de mais dados, salva contexto
            if need_more:
                self._set_context(user_id, channel, tool_name, params)
                thought = result.get("thought", "Preciso de mais informações")
                return self._personality_response(thought + ". Qual é?")
            
            # Executa a tool
            if tool_name == "chat":
                return await self._chat(message)
            
            tool_method = getattr(self.tools, tool_name, None)
            if not tool_method:
                return f"Hmm, não sei fazer isso ainda. Tenta perguntar de outro jeito?"
            
            # Filtra apenas parâmetros válidos
            valid_params = self._get_valid_params(tool_name, params)
            result_text = await tool_method(**valid_params)
            return self._personality_response(result_text, is_data=True)
            
        except Exception as e:
            return f"Buguei aqui: {str(e)[:100]}. Tenta de novo?"
    
    def _get_valid_params(self, tool_name: str, params: dict) -> dict:
        """Filtra apenas os parâmetros válidos para a tool."""
        valid_params = {
            "list_people": [],
            "search_people": ["name"],
            "search_people_by_field": ["field"],
            "create_person": ["name", "email", "phone", "company"],
            "list_opportunities": ["stage", "limit"],
            "count_opportunities": ["stage"],
            "create_opportunity": ["name", "stage", "company", "person", "amount"],
            "list_tasks": [],
            "create_task": ["title", "due_date"],
            "list_companies": [],
            "get_current_datetime": [],
        }
        
        valid = valid_params.get(tool_name, [])
        return {k: v for k, v in params.items() if k in valid}
    
    async def _continue_context(self, user_id: str, channel: str, message: str, ctx: dict) -> str:
        """Continua uma ação que precisava de mais dados."""
        # Verifica se o usuário mudou de assunto (mensagem curta e direta)
        if len(message) < 50 and any(word in message.lower() for word in ["cadastrar", "criar", "nova", "novo", "quero", "preciso"]):
            self._clear_context(user_id, channel)
            return await self._process_with_tools(user_id, channel, message)
        
        # Extrai novos dados
        prompt = f"""Estamos executando: {ctx['intent']}
Dados já coletados: {json.dumps(ctx['data'])}
Nova mensagem: "{message}"

Extraia os novos dados em JSON: {{"novos": {{...}}}}"""
        
        try:
            resp = self.model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 200}
            )
            parsed = self._extract_json(resp.text)
            novos = parsed.get("novos", {})
            
            all_data = {**ctx["data"], **novos}
            
            # Limpa dados inválidos para a tool atual
            all_data = self._get_valid_params(ctx["intent"], all_data)
            
            # Verifica se tem tudo
            check = self.model.generate_content(
                f"Com os dados {json.dumps(all_data)}, consigo executar {ctx['intent']}? Responda SIM ou NÃO.",
                generation_config={"temperature": 0.1}
            )
            
            if "SIM" in check.text.upper():
                tool_method = getattr(self.tools, ctx["intent"], None)
                if tool_method:
                    result = await tool_method(**all_data)
                    self._clear_context(user_id, channel)
                    return self._personality_response(result, is_data=True)
            else:
                self._set_context(user_id, channel, ctx["intent"], all_data)
                return self._personality_response("Ainda preciso de mais informações. Qual é?")
                
        except Exception as e:
            return f"Erro: {str(e)[:100]}. Vamos tentar de novo?"
    
    async def _chat(self, message: str) -> str:
        """Resposta conversacional."""
        try:
            resp = self.model.generate_content(
                f"Você é Monday, assistente CRM sarcástico. Responda de forma natural.\n\nUsuário: {message}\n\nMonday:",
                generation_config={"temperature": 0.7, "max_output_tokens": 300}
            )
            return resp.text.strip()
        except:
            return "E aí! O que vamos fazer no CRM hoje?"
    
    def _personality_response(self, content: str, is_data: bool = False) -> str:
        """Adiciona personalidade à resposta."""
        if is_data:
            # Para dados, apenas formata
            return content
        return content
    
    def _extract_json(self, text: str) -> dict:
        """Extrai JSON da resposta do LLM."""
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        try:
            return json.loads(text.strip())
        except:
            return {}
    
    # ---------- MEMORY HELPERS ----------
    def _get_context(self, user_id: str, channel: str) -> dict:
        session = self.memory["session"]()
        try:
            conv = session.query(self.memory["Conversation"]).filter_by(user_id=user_id, channel=channel).first()
            if conv:
                return {"intent": conv.current_intent or "", "data": conv.current_data or {}}
            return {"intent": "", "data": {}}
        finally:
            session.close()
    
    def _set_context(self, user_id: str, channel: str, intent: str = None, data: dict = None):
        session = self.memory["session"]()
        try:
            conv = session.query(self.memory["Conversation"]).filter_by(user_id=user_id, channel=channel).first()
            if not conv:
                conv = self.memory["Conversation"](user_id=user_id, channel=channel)
                session.add(conv)
            if intent is not None:
                conv.current_intent = intent
            if data is not None:
                conv.current_data = data
            conv.updated_at = datetime.now()
            session.commit()
        finally:
            session.close()
    
    def _clear_context(self, user_id: str, channel: str):
        self._set_context(user_id, channel, "", {})


# Singleton
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = MondayAgent()
    return _agent
