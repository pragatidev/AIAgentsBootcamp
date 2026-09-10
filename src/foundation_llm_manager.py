"""
Cost-Free LLM Foundation for Agentic AI
=======================================

Purpose: Provide students with cost-effective, reliable LLM access
Strategy: Local-first (FREE) → Ultra-cheap cloud scaling
Goal: Fearless experimentation for AI agent development

Enhanced with ALL free tier providers mentioned in the course!
"""

import os
import json
import requests
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass
from dotenv import load_dotenv

# Smart environment loading
def load_environment():
    """Find and load .env file from multiple possible locations"""
    possible_locations = [
        '.env',
        '../.env', 
        '../../.env',
        Path.cwd() / '.env',
        Path.cwd().parent / '.env',
    ]
    
    for env_path in possible_locations:
        if Path(env_path).exists():
            load_dotenv(env_path, override=True)
            print(f"🔧 Loaded environment from: {env_path}")
            return str(env_path)
    
    print("⚠️ No .env file found - using default settings")
    return None

# Load environment on import
load_environment()

@dataclass
class ModelSpec:
    """Model specification with cost and capability info"""
    name: str
    provider: str
    cost_per_1m_input: float
    cost_per_1m_output: float
    max_tokens: int
    specialties: List[str]
    speed_tier: str

class FoundationLLMManager:
    """Foundation LLM Manager for Cost-Free Agentic AI Development"""
    
    def __init__(self, daily_budget: float = 5.0):
        self.daily_budget = daily_budget
        self.usage_file = Path("llm_usage.json")
        self.models = self._define_models()
        self.available_providers = self._check_availability()
        self.usage_data = self._load_usage_data()
        
    def _define_models(self) -> Dict[str, ModelSpec]:
        """Define all available models with 2025 pricing"""
        return {
            # FREE LOCAL MODELS
            "ollama_llama32": ModelSpec(
                name="llama3.2",
                provider="ollama",
                cost_per_1m_input=0.0,
                cost_per_1m_output=0.0,
                max_tokens=4096,
                specialties=["general", "learning", "free"],
                speed_tier="medium"
            ),
            "ollama_deepseek_coder": ModelSpec(
                name="deepseek-coder",
                provider="ollama",
                cost_per_1m_input=0.0,
                cost_per_1m_output=0.0,
                max_tokens=4096,
                specialties=["coding", "free"],
                speed_tier="medium"
            ),
            
            # ULTRA-CHEAP CLOUD MODELS
            "deepseek_chat": ModelSpec(
                name="deepseek-chat",
                provider="deepseek",
                cost_per_1m_input=0.14,
                cost_per_1m_output=0.28,
                max_tokens=4096,
                specialties=["general", "budget"],
                speed_tier="medium"
            ),
            "deepseek_coder": ModelSpec(
                name="deepseek-coder",
                provider="deepseek",
                cost_per_1m_input=0.14,
                cost_per_1m_output=0.28,
                max_tokens=4096,
                specialties=["coding", "budget"],
                speed_tier="medium"
            ),
            "groq_llama": ModelSpec(
                name="llama-3.3-70b-versatile",
                provider="groq",
                cost_per_1m_input=0.79,
                cost_per_1m_output=0.79,
                max_tokens=8192,
                specialties=["speed", "general"],
                speed_tier="ultra_fast"
            ),
            "groq_llama_8b": ModelSpec(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost_per_1m_input=0.05,
                cost_per_1m_output=0.08,
                max_tokens=8192,
                specialties=["speed", "budget"],
                speed_tier="ultra_fast"
            ),
            "google_flash": ModelSpec(
                name="gemini-2.0-flash-exp",
                provider="google",
                cost_per_1m_input=0.075,
                cost_per_1m_output=0.30,
                max_tokens=8192,
                specialties=["multimodal", "speed"],
                speed_tier="fast"
            ),
            "mistral_small": ModelSpec(
                name="ministral-3b-latest",
                provider="mistral",
                cost_per_1m_input=0.04,
                cost_per_1m_output=0.04,
                max_tokens=4096,
                specialties=["budget", "multilingual"],
                speed_tier="fast"
            ),
        }
    
    def _check_availability(self) -> Dict[str, bool]:
        """Check which providers are available"""
        available = {}
        
        # Check Ollama
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            available['ollama'] = response.status_code == 200
        except:
            available['ollama'] = False
            
        # Check cloud providers
        api_keys = {
            'deepseek': 'DEEPSEEK_API_KEY',
            'groq': 'GROQ_API_KEY',
            'google': 'GOOGLE_API_KEY',
            'mistral': 'MISTRAL_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY'
        }
        
        for provider, env_key in api_keys.items():
            key = os.getenv(env_key)
            available[provider] = bool(key and key.strip() and not key.startswith('your_'))
            
        return available
    
    def _load_usage_data(self) -> Dict:
        """Load usage tracking data"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "daily_spending": {},
            "total_requests": 0,
            "last_reset": str(date.today())
        }
    
    def get_daily_spending(self) -> float:
        """Get today's spending"""
        today = str(date.today())
        return self.usage_data["daily_spending"].get(today, 0.0)
    
    def get_remaining_budget(self) -> float:
        """Get remaining daily budget"""
        return max(0, self.daily_budget - self.get_daily_spending())
    
    def _get_preferred_provider(self) -> str:
        """Smart provider selection with FREE priority"""
        # Check .env preference first
        preferred = os.getenv('PREFERRED_PROVIDER', 'auto').lower()
        if preferred != 'auto' and preferred in self.available_providers:
            if self.available_providers[preferred]:
                return preferred
        
        # Smart auto-selection (FREE and cheap first)
        priority_order = [
            'ollama',    # FREE unlimited (best for learning)
            'groq',      # FREE tier + ultra-fast
            'google',    # FREE tier + multimodal
            'deepseek',  # FREE tier + ultra cheap scaling
            'mistral',   # Ultra cheap + multilingual
            'anthropic', # Premium quality
            'openai'     # Popular premium
        ]
        
        for provider in priority_order:
            if self.available_providers.get(provider, False):
                return provider
                
        raise ValueError("No LLM providers available. Install Ollama or add API keys to .env")
    
    def get_llm(self, provider: Optional[str] = None, model: Optional[str] = None):
        """Get LLM client with smart provider selection"""
        
        if provider is None:
            provider = self._get_preferred_provider()
        elif provider not in self.available_providers or not self.available_providers[provider]:
            raise ValueError(f"Provider '{provider}' not available")
            
        # Get provider-specific LLM with model selection
        if provider == 'ollama':
            return self._get_ollama(model)
        elif provider == 'google':
            return self._get_google(model)
        elif provider == 'deepseek':
            return self._get_deepseek(model)
        elif provider == 'groq':
            return self._get_groq(model)
        elif provider == 'mistral':
            return self._get_mistral(model)
        elif provider == 'anthropic':
            return self._get_anthropic(model)
        elif provider == 'openai':
            return self._get_openai(model)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def _get_ollama(self, model=None):
        """Local Ollama - FREE unlimited learning"""
        from langchain_ollama import ChatOllama
        default_model = os.getenv('OLLAMA_DEFAULT_MODEL', 'llama3.2')
        return ChatOllama(
            model=model or default_model,
            base_url="http://localhost:11434",
            temperature=0.1
        )
    
    def _get_google(self, model=None):
        """Google Gemini - Great value + FREE tier"""
        from langchain_google_genai import ChatGoogleGenerativeAI
        default_model = os.getenv('GOOGLE_DEFAULT_MODEL', 'gemini-2.0-flash-exp')
        return ChatGoogleGenerativeAI(
            model=model or default_model,
            google_api_key=os.getenv('GOOGLE_API_KEY'),
            temperature=0.1
        )
    
    def _get_deepseek(self, model=None):
        """DeepSeek - Ultra cheap + FREE tier"""
        from langchain_openai import ChatOpenAI
        default_model = os.getenv('DEEPSEEK_DEFAULT_MODEL', 'deepseek-chat')
        return ChatOpenAI(
            model=model or default_model,
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url="https://api.deepseek.com",
            temperature=0.1
        )
    
    def _get_groq(self, model=None):
        """Groq - Ultra fast + FREE tier"""
        from langchain_groq import ChatGroq
        default_model = os.getenv('GROQ_DEFAULT_MODEL', 'llama-3.1-8b-instant')
        return ChatGroq(
            model=model or default_model,
            groq_api_key=os.getenv('GROQ_API_KEY'),
            temperature=0.1
        )
    
    def _get_mistral(self, model=None):
        """Mistral - European AI + multilingual"""
        from langchain_mistralai import ChatMistralAI
        default_model = os.getenv('MISTRAL_DEFAULT_MODEL', 'ministral-3b-latest')
        return ChatMistralAI(
            model=model or default_model,
            mistral_api_key=os.getenv('MISTRAL_API_KEY'),
            temperature=0.1
        )
    
    def _get_anthropic(self, model=None):
        """Anthropic Claude - Premium quality"""
        from langchain_anthropic import ChatAnthropic
        default_model = os.getenv('ANTHROPIC_DEFAULT_MODEL', 'claude-3-haiku-20240307')
        return ChatAnthropic(
            model=model or default_model,
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            temperature=0.1
        )
    
    def _get_openai(self, model=None):
        """OpenAI GPT - Popular premium"""
        from langchain_openai import ChatOpenAI
        default_model = os.getenv('OPENAI_DEFAULT_MODEL', 'gpt-4o-mini')
        return ChatOpenAI(
            model=model or default_model,
            api_key=os.getenv('OPENAI_API_KEY'),
            temperature=0.1
        )
    
    def chat(self, message: str, task_type: str = "general", priority: str = "cost", provider: Optional[str] = None) -> str:
        """Chat with optimal model selection"""
        
        # If specific provider requested, use it directly
        if provider:
            if provider not in self.available_providers or not self.available_providers[provider]:
                raise ValueError(f"Provider '{provider}' not available")
            llm = self.get_llm(provider)
            result = llm.invoke(message)
            return result.content
        
        # Original logic for auto-selection
        selected_provider = self._get_preferred_provider()
        
        # Task-specific model selection
        if task_type == "coding" and self.available_providers.get('deepseek'):
            llm = self.get_llm('deepseek', 'deepseek-coder')
        elif task_type == "speed" and self.available_providers.get('groq'):
            llm = self.get_llm('groq', 'llama-3.1-8b-instant')
        elif task_type == "multimodal" and self.available_providers.get('google'):
            llm = self.get_llm('google', 'gemini-2.0-flash-exp')
        else:
            llm = self.get_llm(selected_provider)
        
        result = llm.invoke(message)
        return result.content
    
    def show_status(self):
        """Show system status"""
        print("🚀 Cost-Free LLM Foundation Status")
        print("=" * 50)
        
        # Budget info
        daily_spending = self.get_daily_spending()
        remaining = self.get_remaining_budget()
        print(f"💰 Daily Budget: ${self.daily_budget:.2f}")
        print(f"💸 Today's Spending: ${daily_spending:.4f}")
        print(f"💵 Remaining: ${remaining:.2f}")
        
        # Available models
        print(f"\n🔗 Available Providers:")
        
        if self.available_providers.get('ollama'):
            print(f"  ✅ Ollama (Local): FREE unlimited")
        else:
            print(f"  ❌ Ollama: Not available")
            print(f"     💡 Install: https://ollama.ai → ollama pull llama3.2")
        
        # FREE TIER providers
        free_providers = [
            ('groq', '⚡ Groq', 'FREE tier + ultra-fast LPU'),
            ('google', '🌟 Google Gemini', 'FREE tier + multimodal'),
            ('deepseek', '💰 DeepSeek', 'FREE tier + $0.14/1M scaling'),
            ('mistral', '🇪🇺 Mistral', '$0.04/1M tokens'),
        ]
        
        # PREMIUM providers  
        premium_providers = [
            ('anthropic', '🧠 Claude', '$0.25+/1M tokens'),
            ('openai', '🏆 OpenAI', '$0.15+/1M tokens'),
        ]
        
        print(f"\n🆓 FREE TIER PROVIDERS:")
        for provider, name, cost in free_providers:
            if self.available_providers.get(provider):
                print(f"  ✅ {name}: Available ({cost})")
            else:
                print(f"  ❌ {name}: Not configured")
        
        print(f"\n💎 PREMIUM PROVIDERS:")
        for provider, name, cost in premium_providers:
            if self.available_providers.get(provider):
                print(f"  ✅ {name}: Available ({cost})")
            else:
                print(f"  ❌ {name}: Not configured")
        
        available_count = sum(1 for available in self.available_providers.values() if available)
        if available_count == 0:
            print(f"\n⚠️ No providers available!")
            print(f"🔧 Quick setup: Install Ollama for FREE unlimited usage")
        else:
            print(f"\n✅ {available_count} provider(s) ready!")
            print(f"🎯 Recommended: Get all FREE API keys for maximum power!")

# Global manager instance
_global_manager = None

def get_manager(daily_budget: float = 5.0) -> FoundationLLMManager:
    """Get or create the global LLM manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = FoundationLLMManager(daily_budget)
    return _global_manager

# Simple functions for students
def chat(message: str, **kwargs) -> str:
    """Smart chat with cost-optimized selection"""
    return get_manager().chat(message, **kwargs)

def free_chat(message: str) -> str:
    """Force free local models only"""
    manager = get_manager()
    if not manager.available_providers.get('ollama'):
        raise ValueError("Ollama not available. Install Ollama and pull llama3.2")
    return chat(message, provider='ollama')

def budget_chat(message: str) -> str:
    """Ultra-cheap models (FREE tiers first)"""
    return chat(message, priority="cost")

def speed_chat(message: str) -> str:
    """Ultra-fast models (Groq priority)"""
    return chat(message, task_type="speed")

def quality_chat(message: str) -> str:
    """Highest quality models"""
    return chat(message, priority="quality")

def coding_chat(message: str) -> str:
    """Coding-optimized models"""
    return chat(message, task_type="coding")

def reasoning_chat(message: str) -> str:
    """Reasoning-optimized models"""
    return chat(message, task_type="reasoning")

def multimodal_chat(message: str) -> str:
    """Multimodal models (Google Gemini)"""
    return chat(message, task_type="multimodal")

def show_status():
    """Show system status"""
    get_manager().show_status()

def setup_foundation(daily_budget: float = 5.0):
    """Initialize the cost-free LLM foundation"""
    manager = get_manager(daily_budget)
    print("🚀 Cost-Free LLM Foundation Initialized!")
    manager.show_status()
    return manager

if __name__ == "__main__":
    setup_foundation()