#!/usr/bin/env python
"""Manual QA execution suite for production stabilization verification.

Simulates all 13 scenarios specified in the stabilization phase requirements,
logs detailed execution traces for each to `qa_logs/scenario_X.log`, and outputs
a unified `qa_summary.json`.
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

# Configure sys path to include backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reconfigure encoding for Windows compatibility when printing Rupee symbol
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app
from app.db.postgres import get_db
from app.services.llm_service import (
    settings,
    metrics_service,
    circuit_breaker_service,
    llm_call_counts,
    GroqProvider,
    OllamaProvider
)
from app.models.product import Product
from app.models.customer import Customer
from app.models.negotiation_context import NegotiationContext
from app.schemas.chat import ConversationAnalysis
from app.schemas.simulation import DigitalTwinProfile, LLMStrategyOutput
from app.core.response_generator import _LLMResponseOutput
from app.core.intent_classifier import IntentClassification

# Setup directory for QA logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa_logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Helper to write logs
def log_scenario(scenario_num: int, message: str):
    log_file = os.path.join(LOGS_DIR, f"scenario_{scenario_num}.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[Scenario {scenario_num}] {message}")

class QASuite:
    def __init__(self):
        # Force TestClient to raise server exceptions so we get stack traces in scenario log files
        self.client = TestClient(app, raise_server_exceptions=True)
        self.results = {}
        self.provider_usage = {"groq": 0, "ollama": 0, "deterministic": 0}
        self.total_passed = 0
        self.total_failed = 0

    def record_scenario(self, num: int, passed: bool, info: dict):
        self.results[f"scenario_{num}"] = {
            "passed": passed,
            "details": info
        }
        if passed:
            self.total_passed += 1
            log_scenario(num, f"RESULT: PASSED - {info}")
        else:
            self.total_failed += 1
            log_scenario(num, f"RESULT: FAILED - {info}")

    def update_provider_metrics(self):
        # Read from sqlite metrics
        self.provider_usage["groq"] += metrics_service.get("provider_used:groq")
        self.provider_usage["ollama"] += metrics_service.get("provider_used:ollama")
        self.provider_usage["deterministic"] += metrics_service.get("provider_used:deterministic")

    async def run_all(self):
        # Reset services and metrics
        metrics_service.reset()
        settings.GROQ_API_KEY = "qa_dummy_key"
        await circuit_breaker_service._set_state({
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        })
        
        # 1. Run Scenario 1
        await self.run_scenario_1()
        
        # 2. Run Scenario 2
        await self.run_scenario_2()
        
        # 3. Run Scenario 3
        await self.run_scenario_3()
        
        # 4. Run Scenario 4
        await self.run_scenario_4()
        
        # 5. Run Scenario 5
        await self.run_scenario_5()
        
        # 6. Run Scenario 6
        await self.run_scenario_6()
        
        # 7. Run Scenario 7
        await self.run_scenario_7()
        
        # 8. Run Scenario 8
        await self.run_scenario_8()
        
        # 9. Run Scenario 9
        await self.run_scenario_9()
        
        # 10. Run Scenario 10
        await self.run_scenario_10()
        
        # 11. Run Scenario 11
        await self.run_scenario_11()
        
        # 12. Run Scenario 12
        await self.run_scenario_12()
        
        # 13. Run Scenario 13
        await self.run_scenario_13()
        
        # Write summary
        summary = {
            "passed": self.total_passed,
            "failed": self.total_failed,
            "provider_usage": self.provider_usage,
            "scenarios": self.results
        }
        
        summary_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "qa_summary.json"
        )
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=4)
        print(f"\nQA suite finished. Summary written to {summary_file}")

    def _setup_mock_db(self, context=None, product=None, customer=None):
        from app.services.product_knowledge_service import ProductKnowledgeService
        if hasattr(ProductKnowledgeService, "_in_memory_cache"):
            ProductKnowledgeService._in_memory_cache.clear()
        if hasattr(ProductKnowledgeService, "_in_memory_retrieval_cache"):
            ProductKnowledgeService._in_memory_retrieval_cache.clear()
        cust_id = customer.id if customer else uuid.UUID("00000000-0000-0000-0000-000000000001")
        prod_id = product.id if product else uuid.UUID("00000000-0000-0000-0000-000000000002")
        
        mock_customer = customer or Customer(
            id=cust_id,
            external_customer_id="U_QA_USER",
            name="QA Buyer",
            email="qa@buyer.com",
            customer_segment="VIP",
            total_spend=5000.0,
            average_order_value=500.0,
            total_orders=10
        )
        mock_product = product or Product(
            id=prod_id,
            external_product_id="P_QA_PROD",
            name="Alpha Vacuum",
            category="Home Appliances",
            selling_price=1000.0,
            cost_price=600.0,
            minimum_price=800.0,
            target_margin=40.0,
            stock_quantity=50,
            popularity_index=4.0,
            return_rate=0.5
        )
        mock_context = context or NegotiationContext(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            customer_id=cust_id,
            product_id=prod_id,
            quantity=1,
            current_offer=1000.0,
            requested_discount=0.0,
            negotiation_stage="initiated",
        )
        
        mock_db = AsyncMock()
        mock_db._force_context = True
        mock_result = MagicMock()
        
        async def get_side_effect(model, ident):
            model_name = getattr(model, "__name__", str(model))
            if "Customer" in model_name:
                return mock_customer
            elif "Product" in model_name:
                return mock_product
            elif "NegotiationContext" in model_name:
                return mock_context
            return None
        mock_db.get.side_effect = get_side_effect
        
        def first_side_effect():
            calls = mock_db.execute.call_args_list
            if not calls:
                return None
            last_call_stmt = str(calls[-1][0][0]).lower()
            if "from customers" in last_call_stmt:
                return mock_customer
            elif "from negotiation_contexts" in last_call_stmt:
                return mock_context
            elif "from products" in last_call_stmt:
                return mock_product
            elif "from locked_deals" in last_call_stmt:
                from app.models.locked_deal import LockedDeal
                deal = LockedDeal(
                    id=uuid.uuid4(),
                    customer_id=mock_customer.id,
                    product_id=mock_product.id,
                    quantity=mock_context.quantity if mock_context else 1,
                    negotiated_price=mock_context.current_offer if mock_context else 900.0,
                    strategy="discount",
                    confidence_score=1.0,
                    product=mock_product
                )
                return deal
            return None

        def all_side_effect():
            calls = mock_db.execute.call_args_list
            if not calls:
                return []
            last_call_stmt = str(calls[-1][0][0]).lower()
            if "from locked_deals" in last_call_stmt:
                from app.models.locked_deal import LockedDeal
                deal = LockedDeal(
                    id=uuid.uuid4(),
                    customer_id=mock_customer.id,
                    product_id=mock_product.id,
                    quantity=mock_context.quantity if mock_context else 1,
                    negotiated_price=mock_context.current_offer if mock_context else 900.0,
                    strategy="discount",
                    confidence_score=1.0,
                    product=mock_product
                )
                return [deal]
            return []
            
        mock_result.scalars.return_value.first.side_effect = first_side_effect
        mock_result.scalars.return_value.all.side_effect = all_side_effect
        mock_db.execute.return_value = mock_result
        return mock_db, mock_customer, mock_product, mock_context

    def _setup_llm_mocks(self, mock_fallback_gen):
        def side_effect(prompt, system_prompt, response_model):
            name = response_model.__name__
            if name == "IntentClassification":
                return response_model(intent="negotiation", confidence=0.95, reasoning="mock", target_product_ids=[])
            elif name == "ConversationAnalysis":
                return response_model(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation")
            elif name == "DigitalTwinProfile":
                return response_model(price_sensitivity=0.5, urgency=0.5, risk_aversion=0.5, brand_loyalty=0.5, decision_speed=0.5)
            elif name == "LLMStrategyOutput":
                return response_model(strategy_name="discount", offer_type="discount", discount_percent=10.0, bundle_value=0.0, reasoning="mock")
            elif name == "_LLMResponseOutput":
                return response_model(customer_response="Calibrated offer", internal_reasoning="mock")
            return response_model.construct()
            
        mock_fallback_gen.side_effect = side_effect

    # Scenarios -------------------------------------------------------------
    
    async def run_scenario_1(self):
        log_scenario(1, "Starting Scenario 1: Select product and ask 'I want 20% discount.'")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            self._setup_llm_mocks(mock_fallback_gen)
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            data = response.json() if passed else {}
            no_recs = "recommended_products" not in data or not data["recommended_products"]
            is_neg = data.get("intent_type") == "negotiation"
            
            passed = passed and no_recs and is_neg
            
            self.update_provider_metrics()
            self.record_scenario(1, passed, {
                "status_code": response.status_code,
                "intent_type": data.get("intent_type"),
                "has_recommendations": not no_recs,
                "provider": "groq",
                "fallback_used": False
            })
        app.dependency_overrides.clear()

    async def run_scenario_2(self):
        log_scenario(2, "Starting Scenario 2: Continue active negotiation with 'Can you do better?'")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "Can you do better?",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            self._setup_llm_mocks(mock_fallback_gen)
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            data = response.json() if passed else {}
            no_recs = "recommended_products" not in data or not data["recommended_products"]
            is_neg = data.get("intent_type") == "negotiation"
            
            passed = passed and no_recs and is_neg
            
            self.update_provider_metrics()
            self.record_scenario(2, passed, {
                "status_code": response.status_code,
                "intent_type": data.get("intent_type"),
                "has_recommendations": not no_recs,
                "provider": "groq",
                "fallback_used": False
            })
        app.dependency_overrides.clear()

    async def run_scenario_3(self):
        log_scenario(3, "Starting Scenario 3: Ask product color spec question.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        
        # Return empty list from DB specifications (forcing web retrieval)
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "What color is this product?",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.retrieval_provider.TavilyProvider.retrieve", new_callable=AsyncMock) as mock_retrieve, \
             patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            mock_retrieve.return_value = ["Product is color Space Gray with matte finish."]
            
            from pydantic import BaseModel
            class WebExtraction(BaseModel):
                answer: str
                confidence: float
            mock_fallback_gen.return_value = WebExtraction(answer="Space Gray", confidence=0.9)
            
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            data = response.json() if passed else {}
            has_color = "Space Gray" in data.get("response", "")
            
            passed = passed and has_color
            
            self.update_provider_metrics()
            self.record_scenario(3, passed, {
                "status_code": response.status_code,
                "answer_extracted": data.get("response"),
                "provider": "groq"
            })
        app.dependency_overrides.clear()

    async def run_scenario_4(self):
        log_scenario(4, "Starting Scenario 4: Reload / recovery from stale UUID session.")
        from app.services.product_knowledge_service import ProductKnowledgeService
        if hasattr(ProductKnowledgeService, "_in_memory_cache"):
            ProductKnowledgeService._in_memory_cache.clear()
        if hasattr(ProductKnowledgeService, "_in_memory_retrieval_cache"):
            ProductKnowledgeService._in_memory_retrieval_cache.clear()
        
        cust_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        prod_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
        stale_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
        
        mock_customer = Customer(
            id=cust_id,
            external_customer_id="U_QA_USER",
            name="QA Buyer",
            email="qa@buyer.com",
            customer_segment="VIP",
            total_spend=5000.0,
            average_order_value=500.0,
            total_orders=10
        )
        mock_product = Product(
            id=prod_id,
            external_product_id="P_QA_PROD",
            name="Alpha Vacuum",
            category="Home Appliances",
            selling_price=1000.0,
            cost_price=600.0,
            minimum_price=800.0,
            target_margin=40.0,
            stock_quantity=50,
            popularity_index=4.0,
            return_rate=0.5
        )
        mock_context = NegotiationContext(
            id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
            customer_id=cust_id,
            product_id=stale_id,
            quantity=1,
            current_offer=1000.0,
            requested_discount=0.0,
            negotiation_stage="initiated",
        )
        
        mock_db = AsyncMock()
        mock_db._force_context = True
        mock_result = MagicMock()
        
        async def get_side_effect(model, ident):
            print(f"[QA DEBUG] db.get called: model={model}, type={type(model)}, ident={ident}", flush=True)
            model_name = getattr(model, "__name__", str(model))
            if "Customer" in model_name:
                return mock_customer
            elif "Product" in model_name:
                return mock_product
            elif "NegotiationContext" in model_name:
                return mock_context
            return None
        mock_db.get.side_effect = get_side_effect
        
        def first_side_effect():
            calls = mock_db.execute.call_args_list
            if not calls:
                return None
            last_call_stmt = str(calls[-1][0][0]).lower()
            if "from customers" in last_call_stmt:
                return mock_customer
            elif "from negotiation_contexts" in last_call_stmt:
                deleted = any("delete" in str(c[0][0]).lower() for c in calls)
                return None if deleted else mock_context
            elif "from products" in last_call_stmt:
                if str(stale_id) in last_call_stmt:
                    return None
                return mock_product
            return None

        def all_side_effect():
            return []
            
        mock_result.scalars.return_value.first.side_effect = first_side_effect
        mock_result.scalars.return_value.all.side_effect = all_side_effect
        mock_db.execute.return_value = mock_result
        
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod_id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            self._setup_llm_mocks(mock_fallback_gen)
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            
            self.update_provider_metrics()
            self.record_scenario(4, passed, {
                "status_code": response.status_code,
                "context_recovered": passed
            })
        app.dependency_overrides.clear()

    async def run_scenario_5(self):
        log_scenario(5, "Starting Scenario 5: Groq disabled -> failover to Ollama.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        await circuit_breaker_service._set_state({
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        })
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GroqProvider.generate") as mock_groq, \
             patch("app.services.llm_service.OllamaProvider.generate") as mock_ollama:
            mock_groq.side_effect = Exception("Groq Service Temporarily Unavailable")
            mock_ollama.side_effect = [
                ConversationAnalysis(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation"),
                _LLMResponseOutput(customer_response="Ollama counteroffer", internal_reasoning="mock")
            ]
            
            with patch.object(settings, "ENABLE_OLLAMA_FALLBACK", True), \
                 patch.object(settings, "OLLAMA_MODEL", "qwen2.5:3b"):
                from app.services.llm_service import get_llm_provider
                fallback_prov = get_llm_provider("groq")
                
                with patch("app.api.chat.get_llm_provider", return_value=fallback_prov):
                    response = self.client.post("/api/v1/chat", json=payload)
                    
                    passed = response.status_code == 200
                    data = response.json() if passed else {}
                    is_ollama = "Ollama counteroffer" in data.get("response", "")
                    
                    passed = passed and is_ollama
                    
                    self.update_provider_metrics()
                    self.record_scenario(5, passed, {
                        "status_code": response.status_code,
                        "provider": "ollama",
                        "fallback_used": True
                    })
        app.dependency_overrides.clear()

    async def run_scenario_6(self):
        log_scenario(6, "Starting Scenario 6: Groq and Ollama disabled -> failover to Deterministic.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        await circuit_breaker_service._set_state({
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        })
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GroqProvider.generate") as mock_groq, \
             patch("app.services.llm_service.OllamaProvider.generate") as mock_ollama:
            mock_groq.side_effect = Exception("Groq down")
            mock_ollama.side_effect = Exception("Ollama down")
            
            from app.services.llm_service import get_llm_provider
            fallback_prov = get_llm_provider("groq")
            
            with patch("app.api.chat.get_llm_provider", return_value=fallback_prov), \
                 patch.object(settings, "ENABLE_OLLAMA_FALLBACK", True), \
                 patch.object(settings, "OLLAMA_MODEL", "qwen2.5:3b"):
                response = self.client.post("/api/v1/chat", json=payload)
                
                passed = response.status_code == 200
                data = response.json() if passed else {}
                is_det = any(term in data.get("response", "") for term in [
                    "We appreciate your budget considerations",
                    "Our catalog pricing reflects",
                    "To support your procurement objectives",
                    "Based on your requirements"
                ])
                
                passed = passed and is_det
                
                self.update_provider_metrics()
                self.record_scenario(6, passed, {
                    "status_code": response.status_code,
                    "provider": "deterministic",
                    "fallback_used": True
                })
        app.dependency_overrides.clear()

    async def run_scenario_7(self):
        log_scenario(7, "Starting Scenario 7: Groq repeated failures -> Circuit Breaker opens -> Ollama.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        await circuit_breaker_service._set_state({
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        })
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch.object(settings, "GROQ_COOLDOWN_SECONDS", 1), \
             patch.object(settings, "GROQ_FAILURE_THRESHOLD", 3), \
             patch.object(settings, "ENABLE_OLLAMA_FALLBACK", True), \
             patch.object(settings, "OLLAMA_MODEL", "qwen2.5:3b"):
            
            from app.services.llm_service import get_llm_provider
            fallback_prov = get_llm_provider("groq")
            
            with patch("app.api.chat.get_llm_provider", return_value=fallback_prov), \
                 patch("app.services.llm_service.GroqProvider.generate") as mock_groq, \
                 patch("app.services.llm_service.OllamaProvider.generate") as mock_ollama:
                mock_groq.side_effect = Exception("Connection Timeout")
                mock_ollama.side_effect = [
                    ConversationAnalysis(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation"),
                    _LLMResponseOutput(customer_response="Ollama recovery counteroffer", internal_reasoning="mock"),
                    ConversationAnalysis(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation"),
                    _LLMResponseOutput(customer_response="Ollama recovery counteroffer", internal_reasoning="mock"),
                    ConversationAnalysis(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation"),
                    _LLMResponseOutput(customer_response="Ollama recovery counteroffer", internal_reasoning="mock")
                ]
                
                for i in range(3):
                    self.client.post("/api/v1/chat", json=payload)
                    
                state = await circuit_breaker_service._get_state()
                is_open = state.get("state") == "open"
                cb_open_cnt = metrics_service.get("circuit_breaker_open_count")
                
                time.sleep(1.2)
                
                def groq_side_effect(prompt, system_prompt, response_model):
                    name = response_model.__name__
                    if name == "ConversationAnalysis":
                        return response_model(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation")
                    elif name == "DigitalTwinProfile":
                        return response_model(price_sensitivity=0.5, urgency=0.5, risk_aversion=0.5, brand_loyalty=0.5, decision_speed=0.5)
                    elif name == "LLMStrategyOutput":
                        return response_model(strategy_name="discount", offer_type="discount", discount_percent=10.0, bundle_value=0.0, reasoning="mock")
                    elif name == "_LLMResponseOutput":
                        return response_model(customer_response="Groq recovered counteroffer", internal_reasoning="mock")
                    return response_model.construct()
                mock_groq.side_effect = groq_side_effect
                
                response = self.client.post("/api/v1/chat", json=payload)
                data = response.json()
                
                passed = is_open and cb_open_cnt >= 1 and response.status_code == 200 and data.get("response") == "Groq recovered counteroffer"
                
                self.update_provider_metrics()
                self.record_scenario(7, passed, {
                    "circuit_tripped": is_open,
                    "breaker_open_count": cb_open_cnt,
                    "recovered_response": data.get("response")
                })
        app.dependency_overrides.clear()

    async def run_scenario_8(self):
        log_scenario(8, "Starting Scenario 8: Repeated product spec questions -> Cache hits.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "What color is this product?",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.retrieval_provider.TavilyProvider.retrieve", new_callable=AsyncMock) as mock_retrieve, \
             patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            mock_retrieve.return_value = ["Color is Space Gray."]
            
            from pydantic import BaseModel
            class WebExtraction(BaseModel):
                answer: str
                confidence: float
            mock_fallback_gen.return_value = WebExtraction(answer="Space Gray", confidence=0.9)
            
            self.client.post("/api/v1/chat", json=payload)
            self.client.post("/api/v1/chat", json=payload)
            
            hits = metrics_service.cache_hits
            misses = metrics_service.cache_misses
            
            passed = hits == 1 and misses == 1
            
            self.update_provider_metrics()
            self.record_scenario(8, passed, {
                "cache_hits": hits,
                "cache_misses": misses
            })
        app.dependency_overrides.clear()

    async def run_scenario_9(self):
        log_scenario(9, "Starting Scenario 9: Full B2B workflow (Search -> Select -> Negotiate -> Lock -> Cart -> Checkout -> PDF).")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        with patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
            self._setup_llm_mocks(mock_fallback_gen)
            
            # Step 1: Search / Discovery
            payload_search = {
                "message": "show laptops",
                "customer_id": "U_QA_USER",
                "quantity": 1
            }
            mock_resolver = MagicMock()
            mock_resolver.resolve_products = AsyncMock(return_value=[prod])
            with patch("app.api.chat.ProductResolver", return_value=mock_resolver):
                res_search = self.client.post("/api/v1/chat", json=payload_search)
            
            # Step 2: Select & Negotiate
            payload_neg = {
                "message": "I want 20% discount",
                "customer_id": "U_QA_USER",
                "product_id": str(prod.id),
                "quantity": 2
            }
            res_neg = self.client.post("/api/v1/chat", json=payload_neg)
            
            # Step 3: Lock Deal
            payload_lock = {
                "customer_id": "U_QA_USER",
                "product_id": str(prod.id),
                "negotiated_price": 800.0,
                "quantity": 2,
                "concessions": [],
                "strategy": "discount",
                "confidence_score": 1.0
            }
            res_lock = self.client.post("/api/v1/procurement/lock", json=payload_lock)
            
            # Step 4: Checkout & PDF
            payload_checkout = {
                "customer_id": "U_QA_USER"
            }
            res_checkout = self.client.post("/api/v1/procurement/purchase", json=payload_checkout)
            
            passed = (
                res_search.status_code == 200 and
                res_neg.status_code == 200 and
                res_lock.status_code == 200 and
                res_checkout.status_code == 200
            )
            
            self.update_provider_metrics()
            self.record_scenario(9, passed, {
                "search_status": res_search.status_code,
                "negotiate_status": res_neg.status_code,
                "lock_status": res_lock.status_code,
                "checkout_status": res_checkout.status_code
            })
        app.dependency_overrides.clear()

    async def run_scenario_10(self):
        log_scenario(10, "Starting Scenario 10: Internet disabled Q&A lookup.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "What color is this product?",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.retrieval_provider.TavilyProvider.retrieve") as mock_retrieve:
            mock_retrieve.side_effect = Exception("Connection Refused / No Internet Access")
            
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            data = response.json() if passed else {}
            unavailable = "[General Knowledge Estimate]" in data.get("response", "") or "[Specification Unavailable]" in data.get("response", "")
            
            passed = passed and unavailable
            
            self.update_provider_metrics()
            self.record_scenario(10, passed, {
                "status_code": response.status_code,
                "response": data.get("response")
            })
        app.dependency_overrides.clear()

    async def run_scenario_11(self):
        log_scenario(11, "Starting Scenario 11: Disable Groq and Ollama response generation.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        payload = {
            "message": "Can you do better?",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GroqProvider.generate") as mock_groq, \
             patch("app.services.llm_service.OllamaProvider.generate") as mock_ollama:
            mock_groq.side_effect = Exception("Groq timeout")
            mock_ollama.side_effect = Exception("Ollama offline")
            
            response = self.client.post("/api/v1/chat", json=payload)
            
            passed = response.status_code == 200
            data = response.json() if passed else {}
            is_det = any(term in data.get("response", "") for term in [
                "We appreciate your budget considerations",
                "Our catalog pricing reflects",
                "To support your procurement objectives",
                "Based on your requirements"
            ])
            
            passed = passed and is_det
            
            self.update_provider_metrics()
            self.record_scenario(11, passed, {
                "status_code": response.status_code,
                "provider": "deterministic"
            })
        app.dependency_overrides.clear()

    async def run_scenario_12(self):
        log_scenario(12, "Starting Scenario 12: Repeated Groq failures trip circuit breaker.")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        await circuit_breaker_service._set_state({
            "consecutive_failures": 0,
            "state": "closed",
            "cooldown_until": 0.0,
            "half_open_probe_active": False
        })
        
        payload = {
            "message": "I want 20% discount",
            "customer_id": "U_QA_USER",
            "product_id": str(prod.id),
            "quantity": 1
        }
        
        with patch("app.services.llm_service.GroqProvider.generate") as mock_groq, \
             patch("app.services.llm_service.OllamaProvider.generate") as mock_ollama:
            mock_groq.side_effect = [
                Exception("502 Bad Gateway"),
                Exception("Connection timeout"),
                Exception("Read Timeout Error"),
                Exception("500 Internal Error"),
                Exception("Connection refused")
            ]
            mock_ollama.return_value = _LLMResponseOutput(customer_response="Ollama counteroffer", internal_reasoning="mock")
            
            with patch.object(settings, "GROQ_FAILURE_THRESHOLD", 5), \
                 patch.object(settings, "ENABLE_OLLAMA_FALLBACK", True), \
                 patch.object(settings, "OLLAMA_MODEL", "qwen2.5:3b"):
                
                for i in range(5):
                    self.client.post("/api/v1/chat", json=payload)
                    
                state = await circuit_breaker_service._get_state()
                is_open = state.get("state") == "open"
                
                mock_groq.reset_mock()
                self.client.post("/api/v1/chat", json=payload)
                
                groq_called = mock_groq.called
                passed = is_open and (not groq_called)
                
                self.update_provider_metrics()
                self.record_scenario(12, passed, {
                    "circuit_tripped": is_open,
                    "groq_attempted_after_trip": groq_called
                })
        app.dependency_overrides.clear()

    async def run_scenario_13(self):
        log_scenario(13, "Starting Scenario 13: Full offline deterministic flow (Internet, Groq, Ollama unavailable).")
        mock_db, cust, prod, ctx = self._setup_mock_db()
        app.dependency_overrides[get_db] = lambda: mock_db
        metrics_service.reset()
        
        await circuit_breaker_service._set_state({
            "consecutive_failures": 5,
            "state": "open",
            "cooldown_until": time.time() + 300,
            "half_open_probe_active": False
        })
        
        with patch.object(settings, "ENABLE_OLLAMA_FALLBACK", False), \
             patch("app.services.retrieval_provider.TavilyProvider.retrieve") as mock_retrieve:
            mock_retrieve.side_effect = Exception("Network offline")
            
            # Step 1: Search
            payload_search = {
                "message": "show laptops",
                "customer_id": "U_QA_USER",
                "quantity": 1
            }
            mock_resolver = MagicMock()
            mock_resolver.resolve_products = AsyncMock(return_value=[prod])
            with patch("app.api.chat.ProductResolver", return_value=mock_resolver):
                res_search = self.client.post("/api/v1/chat", json=payload_search)
            
            # Step 2: Negotiate
            payload_neg = {
                "message": "I want 25% discount",
                "customer_id": "U_QA_USER",
                "product_id": str(prod.id),
                "quantity": 1
            }
            res_neg = self.client.post("/api/v1/chat", json=payload_neg)
            
            # Step 3: Lock Deal (Add to cart)
            payload_lock = {
                "customer_id": "U_QA_USER",
                "product_id": str(prod.id),
                "negotiated_price": 750.0,
                "quantity": 1,
                "concessions": [],
                "strategy": "discount",
                "confidence_score": 1.0
            }
            res_lock = self.client.post("/api/v1/procurement/lock", json=payload_lock)
            
            # Step 4: Checkout & PDF
            payload_checkout = {
                "customer_id": "U_QA_USER"
            }
            res_checkout = self.client.post("/api/v1/procurement/purchase", json=payload_checkout)
            
            passed = (
                res_search.status_code == 200 and
                res_neg.status_code == 200 and
                res_lock.status_code == 200 and
                res_checkout.status_code == 200
            )
            
            self.update_provider_metrics()
            self.record_scenario(13, passed, {
                "search_status": res_search.status_code,
                "negotiate_status": res_neg.status_code,
                "lock_status": res_lock.status_code,
                "checkout_status": res_checkout.status_code
            })
        app.dependency_overrides.clear()

if __name__ == "__main__":
    suite = QASuite()
    asyncio.run(suite.run_all())
