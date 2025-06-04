"""
Production-Grade LLM Manager for AI Agents Bootcamp
Complete 2025 Model Support with Granular Provider & Model Control

Supports ALL current LLM providers and models with exact pricing and specifications
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


@dataclass
class ModelInfo:
    """Complete model information structure"""
    provider: str
    model_name: str
    display_name: str
    input_cost: float  # Cost per 1M input tokens in USD
    output_cost: float  # Cost per 1M output tokens in USD
    max_tokens: int
    speed_tier: str  # "ultra_fast", "fast", "medium", "slow"
    quality_tier: str  # "excellent", "high", "good", "medium"
    specialties: List[str]  # ["coding", "reasoning", "multimodal", "creative", "cost-effective"]
    context_window: int
    available: bool = True


class ComprehensiveLLMManager:
    """
    Complete LLM Manager supporting ALL 2025 providers and models
    with granular control over provider and model selection
    """
    
    def __init__(self, daily_budget: float = 10.0):
        self.logger = logging.getLogger(__name__)
        self.daily_budget = daily_budget
        self.usage_log = []
        self.daily_spending = 0.0
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Complete 2025 model catalog with exact specifications
        self.models = {
            # OpenAI Models - Latest 2025
            "openai": {
                "gpt-4o": ModelInfo(
                    provider="openai", model_name="gpt-4o", display_name="GPT-4o",
                    input_cost=2.50, output_cost=10.00, max_tokens=4096, speed_tier="medium",
                    quality_tier="excellent", specialties=["reasoning", "multimodal", "general"],
                    context_window=128000
                ),
                "gpt-4o-mini": ModelInfo(
                    provider="openai", model_name="gpt-4o-mini", display_name="GPT-4o Mini",
                    input_cost=0.15, output_cost=0.60, max_tokens=16384, speed_tier="fast",
                    quality_tier="high", specialties=["general", "cost-effective"],
                    context_window=128000
                ),
                "gpt-3.5-turbo": ModelInfo(
                    provider="openai", model_name="gpt-3.5-turbo", display_name="GPT-3.5 Turbo",
                    input_cost=0.50, output_cost=1.50, max_tokens=4096, speed_tier="fast",
                    quality_tier="good", specialties=["general", "legacy"],
                    context_window=16385
                ),
                "o1-mini": ModelInfo(
                    provider="openai", model_name="o1-mini", display_name="OpenAI o1 Mini",
                    input_cost=3.00, output_cost=12.00, max_tokens=65536, speed_tier="slow",
                    quality_tier="excellent", specialties=["reasoning", "math", "complex"],
                    context_window=128000
                ),
            },
            
            # Anthropic Models - Latest Claude
            "anthropic": {
                "claude-3-5-sonnet-20241022": ModelInfo(
                    provider="anthropic", model_name="claude-3-5-sonnet-20241022", display_name="Claude 3.5 Sonnet",
                    input_cost=3.00, output_cost=15.00, max_tokens=8192, speed_tier="fast",
                    quality_tier="excellent", specialties=["reasoning", "coding", "analysis"],
                    context_window=200000
                ),
                "claude-3-haiku-20240307": ModelInfo(
                    provider="anthropic", model_name="claude-3-haiku-20240307", display_name="Claude 3 Haiku",
                    input_cost=0.25, output_cost=1.25, max_tokens=4096, speed_tier="ultra_fast",
                    quality_tier="high", specialties=["speed", "cost-effective"],
                    context_window=200000
                ),
                "claude-3-opus-20240229": ModelInfo(
                    provider="anthropic", model_name="claude-3-opus-20240229", display_name="Claude 3 Opus",
                    input_cost=15.00, output_cost=75.00, max_tokens=4096, speed_tier="medium",
                    quality_tier="excellent", specialties=["complex-reasoning", "premium"],
                    context_window=200000
                ),
            },
            
            # Google Models - Latest Gemini
            "google": {
                "gemini-1.5-pro": ModelInfo(
                    provider="google", model_name="gemini-1.5-pro", display_name="Gemini 1.5 Pro",
                    input_cost=1.25, output_cost=5.00, max_tokens=8192, speed_tier="medium",
                    quality_tier="excellent", specialties=["multimodal", "long-context"],
                    context_window=2000000
                ),
                "gemini-1.5-flash": ModelInfo(
                    provider="google", model_name="gemini-1.5-flash", display_name="Gemini 1.5 Flash",
                    input_cost=0.075, output_cost=0.30, max_tokens=8192, speed_tier="ultra_fast",
                    quality_tier="high", specialties=["speed", "cost-effective", "multimodal"],
                    context_window=1000000
                ),
                "gemini-pro": ModelInfo(
                    provider="google", model_name="gemini-pro", display_name="Gemini Pro",
                    input_cost=0.50, output_cost=1.50, max_tokens=32768, speed_tier="fast",
                    quality_tier="high", specialties=["general", "multimodal"],
                    context_window=32768
                ),
            },
            
            # DeepSeek Models - Ultra Cost-Effective
            "deepseek": {
                "deepseek-chat": ModelInfo(
                    provider="deepseek", model_name="deepseek-chat", display_name="DeepSeek Chat",
                    input_cost=0.14, output_cost=0.28, max_tokens=4096, speed_tier="fast",
                    quality_tier="high", specialties=["cost-effective", "general"],
                    context_window=32768
                ),
                "deepseek-coder": ModelInfo(
                    provider="deepseek", model_name="deepseek-coder", display_name="DeepSeek Coder",
                    input_cost=0.14, output_cost=0.28, max_tokens=4096, speed_tier="fast",
                    quality_tier="excellent", specialties=["coding", "programming", "cost-effective"],
                    context_window=16384
                ),
                "deepseek-r1": ModelInfo(
                    provider="deepseek", model_name="deepseek-r1", display_name="DeepSeek R1",
                    input_cost=0.55, output_cost=2.19, max_tokens=65536, speed_tier="medium",
                    quality_tier="excellent", specialties=["reasoning", "math", "complex"],
                    context_window=65536
                ),
            },
            
            # Groq Models - Ultra Fast
            "groq": {
                "llama-3.3-70b-versatile": ModelInfo(
                    provider="groq", model_name="llama-3.3-70b-versatile", display_name="Llama 3.3 70B",
                    input_cost=0.59, output_cost=0.79, max_tokens=32768, speed_tier="ultra_fast",
                    quality_tier="high", specialties=["speed", "versatile"],
                    context_window=131072
                ),
                "llama-3.1-8b-instant": ModelInfo(
                    provider="groq", model_name="llama-3.1-8b-instant", display_name="Llama 3.1 8B",
                    input_cost=0.05, output_cost=0.08, max_tokens=8192, speed_tier="ultra_fast",
                    quality_tier="good", specialties=["speed", "cost-effective"],
                    context_window=131072
                ),
                "mixtral-8x7b-32768": ModelInfo(
                    provider="groq", model_name="mixtral-8x7b-32768", display_name="Mixtral 8x7B",
                    input_cost=0.24, output_cost=0.24, max_tokens=32768, speed_tier="ultra_fast",
                    quality_tier="good", specialties=["speed", "multilingual"],
                    context_window=32768
                ),
            },
            
            # xAI Models
            "xai": {
                "grok-2-1212": ModelInfo(
                    provider="xai", model_name="grok-2-1212", display_name="Grok 2",
                    input_cost=2.00, output_cost=10.00, max_tokens=131072, speed_tier="medium",
                    quality_tier="excellent", specialties=["reasoning", "real-time"],
                    context_window=131072
                ),
                "grok-beta": ModelInfo(
                    provider="xai", model_name="grok-beta", display_name="Grok Beta",
                    input_cost=5.00, output_cost=15.00, max_tokens=131072, speed_tier="medium",
                    quality_tier="excellent", specialties=["latest", "experimental"],
                    context_window=131072
                ),
            },
            
            # Mistral Models
            "mistral": {
                "mistral-large-latest": ModelInfo(
                    provider="mistral", model_name="mistral-large-latest", display_name="Mistral Large",
                    input_cost=2.00, output_cost=6.00, max_tokens=128000, speed_tier="medium",
                    quality_tier="excellent", specialties=["reasoning", "multilingual"],
                    context_window=128000
                ),
                "codestral-latest": ModelInfo(
                    provider="mistral", model_name="codestral-latest", display_name="Codestral",
                    input_cost=0.20, output_cost=0.60, max_tokens=32768, speed_tier="fast",
                    quality_tier="excellent", specialties=["coding", "programming"],
                    context_window=32768
                ),
                "mistral-small-latest": ModelInfo(
                    provider="mistral", model_name="mistral-small-latest", display_name="Mistral Small",
                    input_cost=0.04, output_cost=0.04, max_tokens=128000, speed_tier="fast",
                    quality_tier="good", specialties=["cost-effective", "small"],
                    context_window=128000
                ),
            },
            
            # Ollama Local Models (Free!)
            "ollama": {
                "llama3.2": ModelInfo(
                    provider="ollama", model_name="llama3.2", display_name="Llama 3.2 (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=128000, speed_tier="slow",
                    quality_tier="good", specialties=["local", "free", "privacy"],
                    context_window=128000
                ),
                "mistral": ModelInfo(
                    provider="ollama", model_name="mistral", display_name="Mistral (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=32768, speed_tier="slow",
                    quality_tier="medium", specialties=["local", "free"],
                    context_window=32768
                ),
                "qwen2.5": ModelInfo(
                    provider="ollama", model_name="qwen2.5", display_name="Qwen 2.5 (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=32768, speed_tier="slow",
                    quality_tier="good", specialties=["local", "free", "multilingual"],
                    context_window=32768
                ),
                "codellama": ModelInfo(
                    provider="ollama", model_name="codellama", display_name="Code Llama (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=16384, speed_tier="slow",
                    quality_tier="good", specialties=["local", "free", "coding"],
                    context_window=16384
                ),
                "deepseek-coder": ModelInfo(
                    provider="ollama", model_name="deepseek-coder", display_name="DeepSeek Coder (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=16384, speed_tier="slow",
                    quality_tier="excellent", specialties=["local", "free", "coding"],
                    context_window=16384
                ),
                "deepseek-r1:latest": ModelInfo(
                    provider="ollama", model_name="deepseek-r1:latest", display_name="DeepSeek R1 (Local)",
                    input_cost=0.0, output_cost=0.0, max_tokens=65536, speed_tier="slow",
                    quality_tier="excellent", specialties=["local", "free", "reasoning", "math"],
                    context_window=65536
                ),
            },
        }
        
        # Check which providers are available
        self.available_providers = self._check_available_providers()
        self.logger.info(f"Available providers: {list(self.available_providers.keys())}")
    
    def _check_available_providers(self) -> Dict[str, bool]:
        """Check which providers have valid API keys or are accessible"""
        available = {}
        
        # API key mappings
        provider_keys = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "groq": "GROQ_API_KEY",
            "xai": "XAI_API_KEY",
            "mistral": "MISTRAL_API_KEY",
        }
        
        # Check API-based providers
        for provider, key in provider_keys.items():
            api_key = os.getenv(key)
            available[provider] = bool(api_key and api_key.strip() and api_key != "your_api_key_here")
        
        # Check Ollama (local)
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            available["ollama"] = response.status_code == 200
        except:
            available["ollama"] = False
        
        return available
    
    def get_llm_instance(self, provider: str, model: str = None):
        """Get configured LLM instance for specific provider and model"""
        if not self.available_providers.get(provider, False):
            raise ValueError(f"Provider '{provider}' not available. Check your .env configuration.")
        
        # Get default model if not specified
        if model is None:
            available_models = list(self.models[provider].keys())
            if not available_models:
                raise ValueError(f"No models available for provider '{provider}'")
            model = available_models[0]
        
        # Verify model exists
        if model not in self.models[provider]:
            available = list(self.models[provider].keys())
            raise ValueError(f"Model '{model}' not found for provider '{provider}'. Available: {available}")
        
        try:
            if provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    temperature=0.1
                )
            
            elif provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=model,
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    temperature=0.1
                )
            
            elif provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=os.getenv("GOOGLE_API_KEY"),
                    temperature=0.1
                )
            
            elif provider == "deepseek":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com",
                    temperature=0.1
                )
            
            elif provider == "groq":
                from langchain_groq import ChatGroq
                return ChatGroq(
                    model=model,
                    api_key=os.getenv("GROQ_API_KEY"),
                    temperature=0.1
                )
            
            elif provider == "xai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=os.getenv("XAI_API_KEY"),
                    base_url="https://api.x.ai/v1",
                    temperature=0.1
                )
            
            elif provider == "mistral":
                from langchain_mistralai import ChatMistralAI
                return ChatMistralAI(
                    model=model,
                    api_key=os.getenv("MISTRAL_API_KEY"),
                    temperature=0.1
                )
            
            elif provider == "ollama":
                from langchain_ollama import ChatOllama
                return ChatOllama(
                    model=model,
                    base_url="http://localhost:11434",
                    temperature=0.1
                )
            
            else:
                raise ValueError(f"Provider '{provider}' not supported")
        
        except Exception as e:
            self.logger.error(f"Failed to initialize {provider}:{model} - {e}")
            raise
    
    def smart_model_selection(self, task_type: str = "general", priority: str = "balanced", 
                            max_cost: float = None) -> tuple:
        """
        Intelligently select the best model based on requirements
        
        Args:
            task_type: "general", "coding", "reasoning", "creative", "multimodal"
            priority: "cost", "speed", "quality", "balanced"
            max_cost: Maximum cost per 1M tokens
        
        Returns:
            tuple: (provider, model_name)
        """
        # Get relevant models based on task type
        candidates = []
        for provider, models in self.models.items():
            if not self.available_providers.get(provider, False):
                continue
                
            for model_info in models.values():
                # Filter by task type
                if task_type == "coding" and "coding" not in model_info.specialties:
                    continue
                elif task_type == "reasoning" and "reasoning" not in model_info.specialties:
                    continue
                elif task_type == "multimodal" and "multimodal" not in model_info.specialties:
                    continue
                
                # Filter by cost if specified
                if max_cost is not None and model_info.input_cost > max_cost:
                    continue
                
                candidates.append(model_info)
        
        if not candidates:
            raise ValueError("No suitable models found for the given criteria")
        
        # Sort based on priority
        if priority == "cost":
            candidates.sort(key=lambda x: x.input_cost)
        elif priority == "speed":
            speed_order = {"ultra_fast": 0, "fast": 1, "medium": 2, "slow": 3}
            candidates.sort(key=lambda x: speed_order.get(x.speed_tier, 4))
        elif priority == "quality":
            quality_order = {"excellent": 0, "high": 1, "good": 2, "medium": 3}
            candidates.sort(key=lambda x: quality_order.get(x.quality_tier, 4))
        else:  # balanced
            # Balanced scoring: cost (40%) + speed (30%) + quality (30%)
            def balanced_score(model):
                # Normalize cost (higher cost = higher score)
                cost_score = min(model.input_cost / 10.0, 1.0)
                
                # Speed scores
                speed_scores = {"ultra_fast": 0, "fast": 0.25, "medium": 0.5, "slow": 1.0}
                speed_score = speed_scores.get(model.speed_tier, 1.0)
                
                # Quality scores (lower is better)
                quality_scores = {"excellent": 0, "high": 0.25, "good": 0.5, "medium": 1.0}
                quality_score = quality_scores.get(model.quality_tier, 1.0)
                
                return (cost_score * 0.4 + speed_score * 0.3 + quality_score * 0.3)
            
            candidates.sort(key=balanced_score)
        
        best_model = candidates[0]
        return best_model.provider, best_model.model_name
    
    def chat(self, message: str, provider: str = None, model: str = None, 
             task_type: str = "general", priority: str = "balanced") -> str:
        """
        Simple chat interface with automatic or manual model selection
        """
        if provider and model:
            # Use specified provider and model
            llm = self.get_llm_instance(provider, model)
            self.logger.info(f"Using specified model: {provider}:{model}")
        elif provider:
            # Use specified provider with default model
            llm = self.get_llm_instance(provider)
            self.logger.info(f"Using provider: {provider}")
        else:
            # Smart model selection
            selected_provider, selected_model = self.smart_model_selection(task_type, priority)
            llm = self.get_llm_instance(selected_provider, selected_model)
            self.logger.info(f"Smart selection: {selected_provider}:{selected_model}")
        
        # Execute the chat
        try:
            result = llm.invoke(message)
            return result.content
        except Exception as e:
            self.logger.error(f"Chat failed: {e}")
            raise
    
    def get_model_info(self, provider: str, model: str) -> ModelInfo:
        """Get detailed information about a specific model"""
        if provider not in self.models:
            raise ValueError(f"Provider '{provider}' not found")
        if model not in self.models[provider]:
            raise ValueError(f"Model '{model}' not found for provider '{provider}'")
        return self.models[provider][model]
    
    def list_all_models(self, provider: str = None, specialty: str = None) -> Dict[str, List[ModelInfo]]:
        """List all available models, optionally filtered by provider or specialty"""
        result = {}
        
        for prov_name, models in self.models.items():
            if provider and prov_name != provider:
                continue
                
            if not self.available_providers.get(prov_name, False):
                continue
                
            filtered_models = []
            for model_info in models.values():
                if specialty and specialty not in model_info.specialties:
                    continue
                filtered_models.append(model_info)
            
            if filtered_models:
                result[prov_name] = filtered_models
        
        return result
    
    def get_models_by_cost(self, max_cost_per_1m: float = None) -> List[ModelInfo]:
        """Get models sorted by cost (cheapest first)"""
        all_models = []
        
        for provider, models in self.models.items():
            if not self.available_providers.get(provider, False):
                continue
                
            for model_info in models.values():
                if max_cost_per_1m is None or model_info.input_cost <= max_cost_per_1m:
                    all_models.append(model_info)
        
        return sorted(all_models, key=lambda x: x.input_cost)
    
    def get_models_by_specialty(self, specialty: str) -> List[ModelInfo]:
        """Get models specialized for specific tasks"""
        specialized_models = []
        
        for provider, models in self.models.items():
            if not self.available_providers.get(provider, False):
                continue
                
            for model_info in models.values():
                if specialty in model_info.specialties:
                    specialized_models.append(model_info)
        
        return specialized_models
    
    def compare_models(self, models: List[tuple]) -> List[Dict]:
        """Compare multiple models side by side"""
        comparison = []
        for provider, model in models:
            try:
                info = self.get_model_info(provider, model)
                comparison.append({
                    "provider": provider,
                    "model": model,
                    "display_name": info.display_name,
                    "input_cost": info.input_cost,
                    "output_cost": info.output_cost,
                    "speed_tier": info.speed_tier,
                    "quality_tier": info.quality_tier,
                    "specialties": info.specialties,
                    "context_window": info.context_window,
                    "available": self.available_providers.get(provider, False)
                })
            except ValueError as e:
                comparison.append({
                    "provider": provider,
                    "model": model,
                    "error": str(e)
                })
        return comparison
    
    def get_usage_summary(self) -> Dict:
        """Get usage and cost summary"""
        return {
            "daily_budget": self.daily_budget,
            "daily_spending": self.daily_spending,
            "remaining_budget": self.daily_budget - self.daily_spending,
            "available_providers": self.available_providers,
            "total_requests": len(self.usage_log)
        }


# Simple interface functions for backward compatibility
def setup_llm_manager(daily_budget: float = 10.0) -> ComprehensiveLLMManager:
    """Setup the comprehensive LLM manager"""
    return ComprehensiveLLMManager(daily_budget=daily_budget)


# Example usage and testing
if __name__ == "__main__":
    # Initialize manager
    manager = ComprehensiveLLMManager(daily_budget=5.0)
    
    print("🚀 Comprehensive LLM Manager Test")
    print("=" * 50)
    
    try:
        # Test smart selection
        provider, model = manager.smart_model_selection(task_type="coding", priority="cost")
        print(f"✅ Best coding model (cost priority): {provider}:{model}")
        
        # Test chat
        response = manager.chat("Hello! What's your name?", provider=provider, model=model)
        print(f"✅ Chat response: {response[:100]}...")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("💡 Make sure to configure your .env file with API keys")
