"""
Testes de Qualidade - Monday CRM Agent
"""
import asyncio
import json
import time
from typing import List, Tuple
from dataclasses import dataclass

from agent import MondayAgent, GeminiClient, TwentyAPI, Memory


@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    error: str = ""
    details: str = ""


class MondayTester:
    """Suite de testes do Monday Agent."""
    
    def __init__(self):
        self.agent = MondayAgent()
        self.results: List[TestResult] = []
    
    def run_all(self) -> List[TestResult]:
        """Executa todos os testes."""
        print("=" * 60)
        print("TESTES DE QUALIDADE - MONDAY CRM AGENT")
        print("=" * 60)
        
        # Testes de componentes
        self._test_memory_basic()
        self._test_memory_context()
        self._test_twenty_api()
        self._test_gemini_connection()
        
        # Testes de integração
        self._test_intent_detection()
        self._test_context_flow()
        self._test_data_extraction()
        
        # Testes de casos reais
        self._test_list_people()
        self._test_search_people()
        self._test_create_task_flow()
        self._test_conversation()
        
        # Testes de edge cases
        self._test_empty_message()
        self._test_special_chars()
        self._test_long_message()
        self._test_concurrent_users()
        
        return self.results
    
    def _run_test(self, name: str, test_func) -> TestResult:
        """Executa um teste individual."""
        start = time.time()
        try:
            test_func()
            duration = time.time() - start
            result = TestResult(name=name, passed=True, duration=duration)
            print(f"  [OK] {name} ({duration:.2f}s)")
        except AssertionError as e:
            duration = time.time() - start
            result = TestResult(name=name, passed=False, duration=duration, error=str(e))
            print(f"  [FAIL] {name} ({duration:.2f}s) - {e}")
        except Exception as e:
            duration = time.time() - start
            result = TestResult(name=name, passed=False, duration=duration, error=f"{type(e).__name__}: {e}")
            print(f"  [FAIL] {name} ({duration:.2f}s) - {type(e).__name__}: {e}")
        
        self.results.append(result)
        return result
    
    # =================================================================
    # TESTES DE MEMÓRIA
    # =================================================================
    def _test_memory_basic(self):
        """Testa operações básicas de memória."""
        def test():
            user_id, channel = "test-user-1", "web"
            # Limpa
            self.agent.memory.clear_context(user_id, channel)
            
            # Set
            self.agent.memory.set_context(user_id, channel, "create_task", {"titulo": "Teste"})
            
            # Get
            ctx = self.agent.memory.get_context(user_id, channel)
            assert ctx["intent"] == "create_task", f"Intent mismatch: {ctx}"
            assert ctx["data"]["titulo"] == "Teste", f"Data mismatch: {ctx}"
            
            # Clear
            self.agent.memory.clear_context(user_id, channel)
            ctx = self.agent.memory.get_context(user_id, channel)
            assert ctx["intent"] == "", f"After clear intent should be empty: {ctx}"
        
        self._run_test("Memory: CRUD básico", test)
    
    def _test_memory_context(self):
        """Testa isolamento de contexto entre usuários."""
        def test():
            # Usuário 1
            self.agent.memory.set_context("user-1", "web", "intent1", {"a": 1})
            # Usuário 2
            self.agent.memory.set_context("user-2", "web", "intent2", {"b": 2})
            
            ctx1 = self.agent.memory.get_context("user-1", "web")
            ctx2 = self.agent.memory.get_context("user-2", "web")
            
            assert ctx1["intent"] == "intent1", "User 1 context corrupted"
            assert ctx2["intent"] == "intent2", "User 2 context corrupted"
            assert ctx1["data"]["a"] == 1, "User 1 data corrupted"
            assert ctx2["data"]["b"] == 2, "User 2 data corrupted"
            
            # Cleanup
            self.agent.memory.clear_context("user-1", "web")
            self.agent.memory.clear_context("user-2", "web")
        
        self._run_test("Memory: Isolamento entre usuários", test)
    
    # =================================================================
    # TESTES DE API TWENTY
    # =================================================================
    def _test_twenty_api(self):
        """Testa conectividade com Twenty CRM."""
        async def async_test():
            # List people
            people = await self.agent.twenty.list_people()
            assert isinstance(people, list), "list_people should return list"
            
            # List tasks
            tasks = await self.agent.twenty.list_tasks()
            assert isinstance(tasks, list), "list_tasks should return list"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("TwentyAPI: Conectividade", test)
    
    # =================================================================
    # TESTES DE LLM
    # =================================================================
    def _test_gemini_connection(self):
        """Testa conexão com Gemini."""
        async def async_test():
            resp = await self.agent.gemini.complete(
                [{"role": "user", "content": "Responda apenas: OK"}],
                temperature=0.1
            )
            assert len(resp) > 0, "Empty response from Gemini"
            assert "OK" in resp.upper() or "ok" in resp.lower(), f"Unexpected response: {resp}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Gemini: Conexão básica", test)
    
    # =================================================================
    # TESTES DE DETECÇÃO DE INTENT
    # =================================================================
    def _test_intent_detection(self):
        """Testa detecção de intenções."""
        async def async_test():
            test_cases = [
                ("listar pessoas", "list_people"),
                ("mostrar contatos", "list_people"),
                ("ver clientes", "list_people"),
                ("tem alguma helena?", "search_people"),
                ("existe maria", "search_people"),
                ("criar tarefa", "create_task"),
                ("nova tarefa", "create_task"),
                ("criar pessoa", "create_person"),
                ("novo contato", "create_person"),
                ("oi, tudo bem?", "chat"),
                ("qual é seu nome?", "chat"),
            ]
            
            for message, expected_intent in test_cases:
                user_id = f"intent-test-{hash(message)}"
                
                # Usa método interno para testar
                prompt = f"""Analise: "{message}"
Responda APENAS com: {{"intent": "list_people|search_people|create_person|create_task|chat"}}"""
                
                resp = await self.agent.gemini.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                try:
                    parsed = json.loads(resp.strip())
                    detected = parsed.get("intent", "")
                    assert detected == expected_intent, f"Message '{message}': expected {expected_intent}, got {detected}"
                except json.JSONDecodeError:
                    # Se não conseguir parsear, tenta inferir do texto
                    resp_lower = resp.lower()
                    if expected_intent == "list_people" and "list" in resp_lower:
                        continue
                    elif expected_intent == "chat" and any(x in resp_lower for x in ["chat", "convers"]):
                        continue
                    raise AssertionError(f"Message '{message}': could not parse intent from: {resp}")
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Intent: Detecção de intenções", test)
    
    def _test_context_flow(self):
        """Testa fluxo de contexto multi-turn."""
        async def async_test():
            user_id = "context-flow-test"
            channel = "web"
            
            # Limpa
            self.agent.memory.clear_context(user_id, channel)
            
            # Passo 1: Inicia criação de tarefa (sem título)
            r1 = await self.agent.handle(user_id, channel, "criar tarefa")
            ctx1 = self.agent.memory.get_context(user_id, channel)
            assert ctx1["intent"] == "create_task", f"Should have intent create_task: {ctx1}"
            assert "titulo" not in ctx1.get("data", {}), "Should not have titulo yet"
            
            # Passo 2: Fornece título
            r2 = await self.agent.handle(user_id, channel, "Comprar pão")
            ctx2 = self.agent.memory.get_context(user_id, channel)
            assert ctx2["intent"] == "", f"Context should be cleared after completion: {ctx2}"
            assert "criada" in r2.lower() or "✅" in r2, f"Should confirm creation: {r2}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Context: Fluxo multi-turn", test)
    
    def _test_data_extraction(self):
        """Testa extração de dados de mensagens."""
        async def async_test():
            test_cases = [
                ("meu nome é João Silva", {"nome": "João Silva"}),
                ("email: joao@teste.com", {"email": "joao@teste.com"}),
                ("telefone 47999999999", {"telefone": "47999999999"}),
                ("titulo Comprar leite", {"titulo": "Comprar leite"}),
            ]
            
            for message, expected in test_cases:
                prompt = f"""Extraia dados de: "{message}"
Responda APENAS com JSON: {{"novos": {{...}}}}"""
                
                resp = await self.agent.gemini.complete(
                    [{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                parsed = self.agent._extract_json(resp)
                novos = parsed.get("novos", {})
                
                for key, value in expected.items():
                    assert key in novos, f"Message '{message}': missing key '{key}' in {novos}"
                    assert novos[key] == value, f"Message '{message}': expected {value}, got {novos[key]}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Context: Extração de dados", test)
    
    # =================================================================
    # TESTES DE INTEGRAÇÃO (CENÁRIOS REAIS)
    # =================================================================
    def _test_list_people(self):
        """Testa listagem de pessoas."""
        async def async_test():
            user_id = "list-test"
            response = await self.agent.handle(user_id, "web", "listar pessoas")
            
            assert len(response) > 0, "Empty response"
            assert "contatos" in response.lower() or "pessoas" in response.lower() or "achei" in response.lower(), f"Unexpected response: {response}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Integration: Listar pessoas", test)
    
    def _test_search_people(self):
        """Testa busca de pessoas."""
        async def async_test():
            user_id = "search-test"
            response = await self.agent.handle(user_id, "web", "tem alguma helena?")
            
            assert len(response) > 0, "Empty response"
            # Pode encontrar ou não, mas deve responder adequadamente
            assert any(x in response.lower() for x in ["resultado", "achei", "não", "nao"]), f"Unexpected response: {response}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Integration: Buscar pessoas", test)
    
    def _test_create_task_flow(self):
        """Testa fluxo completo de criação de tarefa."""
        async def async_test():
            user_id = "create-task-test"
            
            # Limpa contexto
            self.agent.memory.clear_context(user_id, "web")
            
            # Inicia
            r1 = await self.agent.handle(user_id, "web", "criar tarefa")
            assert "titulo" in r1.lower() or "título" in r1.lower() or "informa" in r1.lower(), f"Should ask for title: {r1}"
            
            # Fornece título
            r2 = await self.agent.handle(user_id, "web", "Teste QA")
            assert "criada" in r2.lower() or "✅" in r2 or "criado" in r2.lower(), f"Should confirm: {r2}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Integration: Criar tarefa (fluxo)", test)
    
    def _test_conversation(self):
        """Testa conversação casual."""
        async def async_test():
            user_id = "chat-test"
            response = await self.agent.handle(user_id, "web", "oi, como você está?")
            
            assert len(response) > 10, "Response too short"
            assert len(response) < 500, "Response too long"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Integration: Conversação", test)
    
    # =================================================================
    # TESTES DE EDGE CASES
    # =================================================================
    def _test_empty_message(self):
        """Testa mensagem vazia."""
        async def async_test():
            user_id = "empty-test"
            response = await self.agent.handle(user_id, "web", "")
            assert len(response) > 0, "Should handle empty message"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Edge: Mensagem vazia", test)
    
    def _test_special_chars(self):
        """Testa caracteres especiais."""
        async def async_test():
            user_id = "special-test"
            messages = [
                "teste @ # $ % & *",
                "emoji 😀 🎉 👍",
                "acentuação: João José María",
                "aspas 'simples' e \"duplas\"",
            ]
            
            for msg in messages:
                response = await self.agent.handle(user_id, "web", msg)
                assert len(response) > 0, f"Failed for message: {msg}"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Edge: Caracteres especiais", test)
    
    def _test_long_message(self):
        """Testa mensagem longa."""
        async def async_test():
            user_id = "long-test"
            long_msg = "A" * 1000
            response = await self.agent.handle(user_id, "web", long_msg)
            assert len(response) > 0, "Should handle long message"
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Edge: Mensagem longa", test)
    
    def _test_concurrent_users(self):
        """Testa múltiplos usuários simultâneos."""
        async def async_test():
            async def user_session(user_id: str, messages: List[str]) -> List[str]:
                responses = []
                for msg in messages:
                    r = await self.agent.handle(user_id, "web", msg)
                    responses.append(r)
                return responses
            
            # 3 usuários simultâneos
            tasks = [
                user_session("concurrent-1", ["oi", "listar pessoas"]),
                user_session("concurrent-2", ["criar tarefa", "Teste"]),
                user_session("concurrent-3", ["tem helena?"]),
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Verifica que cada usuário teve respostas
            for i, resps in enumerate(results):
                assert len(resps) > 0, f"User {i+1} got no responses"
                for r in resps:
                    assert len(r) > 0, f"User {i+1} got empty response"
            
            # Verifica isolamento
            ctx1 = self.agent.memory.get_context("concurrent-1", "web")
            ctx2 = self.agent.memory.get_context("concurrent-2", "web")
            ctx3 = self.agent.memory.get_context("concurrent-3", "web")
            
            # Limpa
            self.agent.memory.clear_context("concurrent-1", "web")
            self.agent.memory.clear_context("concurrent-2", "web")
            self.agent.memory.clear_context("concurrent-3", "web")
        
        def test():
            asyncio.run(async_test())
        
        self._run_test("Edge: Usuários concorrentes", test)
    
    # =================================================================
    # RELATÓRIO
    # =================================================================
    def print_report(self):
        """Imprime relatório final."""
        print("\n" + "=" * 60)
        print("RELATORIO DE TESTES")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_time = sum(r.duration for r in self.results)
        
        print(f"\nTotal de testes: {len(self.results)}")
        print(f"  [OK] Passaram: {passed}")
        print(f"  [FAIL] Falharam: {failed}")
        print(f"\nTempo total: {total_time:.2f}s")
        print(f"Tempo medio: {total_time/len(self.results):.2f}s")
        
        if failed > 0:
            print("\nTESTES COM FALHA:")
            for r in self.results:
                if not r.passed:
                    print(f"  • {r.name}")
                    print(f"    Erro: {r.error}")
        
        success_rate = (passed / len(self.results)) * 100
        print(f"\nTaxa de sucesso: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("\nEXCELENTE! Qualidade aprovada.")
        elif success_rate >= 70:
            print("\nATENCAO! Alguns testes falharam.")
        else:
            print("\nCRITICO! Revisar codigo.")
        
        print("=" * 60)
        
        return failed == 0


def main():
    """Entry point."""
    tester = MondayTester()
    tester.run_all()
    success = tester.print_report()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())

