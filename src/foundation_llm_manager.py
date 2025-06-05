"""
Cost-Free LLM Foundation for Agentic AI
=======================================

Purpose: Provide students with cost-effective, reliable LLM access
Strategy: Local-first (FREE) → Ultra-cheap cloud scaling
Goal: Fearless experimentation for AI agent development

Design Principles:
✅ Students never pay more than $5/month (even heavy usage)
✅ Local models available for 100% FREE practice
✅ Smart model selection based on task requirements
✅ Professional patterns from day one
"""

import os
import json
import requests
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Load environment variables from multiple possible locations
def load_environment():
    """Smart environment loading - finds .env wherever it is"""
    possible_locations = [
        '.env',                    # Current directory
        '../.env',                 # Parent directory  
        '../../.env',              # Grandparent directory
        Path.cwd() / '.env',       # Explicit current
        Path.cwd().parent / '.env', # Explicit parent
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
    speed_tier: str  # "ultra_fast", "fast", "medium", "slow"
    
class FoundationLLMManager:
    """
    Foundation LLM Manager for Cost-Free Agentic AI Development
    
    Key Features:
    - Local-first strategy (FREE unlimited)
    - Ultra-cheap cloud scaling ($0.05-0.14/1M tokens)
    - Task-based model selection
    - Usage tracking and cost management
    """
    
    def __init__(self, daily_budget: float = 5.0):
        self.daily_budget = daily_budget
        self.usage_file = Path("llm_usage.json")
        self.models = self._define_models()
        self.available_providers = self._check_availability()
        self.usage_data = self._load_usage_data()
        
    def _define_models(self) -> Dict[str, ModelSpec]:
        """Define all available models with their specifications"""
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
            
            "ollama_deepseek_r1": ModelSpec(
                name="deepseek-r1:latest",
                provider="ollama",
                cost_per_1m_input=0.0,
                cost_per_1m_output=0.0,
                max_tokens=8192,
                specialties=["reasoning", "logic", "free"],
                speed_tier="slow"
            ),
            
            # ULTRA-CHEAP CLOUD MODELS
            "groq_llama": ModelSpec(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost_per_1m_input=0.05,
                cost_per_1m_output=0.08,
                max_tokens=8192,
                specialties=["speed", "general"],
                speed_tier="ultra_fast"
            ),
            
            "google_gemini_flash": ModelSpec(
                name="gemini-1.5-flash",
                provider="google",
                cost_per_1m_input=0.075,
                cost_per_1m_output=0.30,
                max_tokens=8192,
                specialties=["general", "multimodal"],
                speed_tier="fast"
            ),
            
            "deepseek_chat": ModelSpec(
                name="deepseek-chat",
                provider="deepseek",
                cost_per_1m_input=0.14,
                cost_per_1m_output=0.28,
                max_tokens=4096,
                specialties=["general", "budget"],
                speed_tier="medium"
            ),
            
            "deepseek_coder_cloud": ModelSpec(
                name="deepseek-coder",
                provider="deepseek",
                cost_per_1m_input=0.14,
                cost_per_1m_output=0.28,
                max_tokens=4096,
                specialties=["coding", "budget"],
                speed_tier="medium"
            ),
            
            # PREMIUM MODELS (for quality-critical tasks)
            "openai_gpt4o_mini": ModelSpec(
                name="gpt-4o-mini",
                provider="openai",
                cost_per_1m_input=0.15,
                cost_per_1m_output=0.60,
                max_tokens=4096,
                specialties=["general", "quality"],
                speed_tier="fast"
            ),
            
            "anthropic_haiku": ModelSpec(
                name="claude-3-haiku-20240307",
                provider="anthropic",
                cost_per_1m_input=0.25,
                cost_per_1m_output=1.25,
                max_tokens=4096,
                specialties=["quality", "reasoning"],
                speed_tier="medium"
            ),
        }
    
    def _check_availability(self) -> Dict[str, bool]:
        """Check which providers are actually available"""
        available = {}
        
        # Check Ollama (local)
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                available['ollama'] = len(models) > 0
            else:
                available['ollama'] = False
        except:
            available['ollama'] = False
            
        # Check cloud providers
        api_keys = {
            'google': 'GOOGLE_API_KEY',
            'deepseek': 'DEEPSEEK_API_KEY',
            'groq': 'GROQ_API_KEY', 
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
    
    def _save_usage_data(self):
        """Save usage tracking data"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except:
            pass  # Fail silently to not break functionality
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation"""
        return len(text.split()) * 1.3  # Conservative estimate
    
    def _track_usage(self, model_key: str, input_text: str, output_text: str):
        """Track usage and costs"""
        model = self.models[model_key]
        
        if model.cost_per_1m_input == 0:  # Free local model
            return
            
        today = str(date.today())
        input_tokens = self._estimate_tokens(input_text)
        output_tokens = self._estimate_tokens(output_text)
        
        cost = (input_tokens * model.cost_per_1m_input + 
                output_tokens * model.cost_per_1m_output) / 1_000_000
        
        if today not in self.usage_data["daily_spending"]:
            self.usage_data["daily_spending"][today] = 0.0
            
        self.usage_data["daily_spending"][today] += cost
        self.usage_data["total_requests"] += 1
        self._save_usage_data()
    
    def get_daily_spending(self) -> float:
        """Get today's spending"""
        today = str(date.today())
        return self.usage_data["daily_spending"].get(today, 0.0)
    
    def get_remaining_budget(self) -> float:
        """Get remaining daily budget"""
        return max(0, self.daily_budget - self.get_daily_spending())
    
    def select_model(self, 
                    task_type: str = "general", 
                    priority: str = "cost",
                    force_provider: Optional[str] = None) -> Tuple[str, ModelSpec]:
        """
        Smart model selection based on task and priority
        
        Args:
            task_type: "general", "coding", "reasoning", "speed", "quality"
            priority: "cost", "speed", "quality", "balanced"
            force_provider: Force specific provider
            
        Returns:
            (model_key, model_spec)
        """
        
        # Filter available models
        candidates = []
        for key, model in self.models.items():
            if not self.available_providers.get(model.provider, False):
                continue
                
            if force_provider and model.provider != force_provider:
                continue
                
            # Check if model fits task
            if task_type in model.specialties or task_type == "general":
                candidates.append((key, model))
        
        if not candidates:
            raise ValueError(f"No models available for task '{task_type}' with provider '{force_provider}'")
        
        # Sort by priority
        if priority == "cost":
            candidates.sort(key=lambda x: x[1].cost_per_1m_input)
        elif priority == "speed":
            speed_order = {"ultra_fast": 0, "fast": 1, "medium": 2, "slow": 3}
            candidates.sort(key=lambda x: speed_order.get(x[1].speed_tier, 4))
        elif priority == "quality":
            # Prefer premium models, then by cost (higher cost = better quality)
            candidates.sort(key=lambda x: (
                0 if "quality" in x[1].specialties else 1,
                -x[1].cost_per_1m_input
            ))
        else:  # balanced
            # Balance cost and quality
            candidates.sort(key=lambda x: x[1].cost_per_1m_input * 0.7 + 
                           (4 - {"ultra_fast": 0, "fast": 1, "medium": 2, "slow": 3}.get(x[1].speed_tier, 3)) * 0.3)
        
        return candidates[0]
    
    def _get_llm_client(self, model_spec: ModelSpec):
        """Get LangChain LLM client for the model"""
        
        if model_spec.provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_spec.name,
                base_url="http://localhost:11434",
                temperature=0.1
            )
            
        elif model_spec.provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_spec.name,
                google_api_key=os.getenv('GOOGLE_API_KEY'),
                temperature=0.1
            )
            
        elif model_spec.provider == "deepseek":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_spec.name,
                api_key=os.getenv('DEEPSEEK_API_KEY'),
                base_url="https://api.deepseek.com",
                temperature=0.1
            )
            
        elif model_spec.provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=model_spec.name,
                groq_api_key=os.getenv('GROQ_API_KEY'),
                temperature=0.1
            )
            
        elif model_spec.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model_spec.name,
                anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
                temperature=0.1
            )
            
        elif model_spec.provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_spec.name,
                api_key=os.getenv('OPENAI_API_KEY'),
                temperature=0.1
            )
            
        else:
            raise ValueError(f"Unknown provider: {model_spec.provider}")
    
    def chat(self, 
             message: str, 
             task_type: str = "general",
             priority: str = "cost",
             force_provider: Optional[str] = None,
             force_model: Optional[str] = None) -> str:
        """
        Chat with optimal model selection
        
        Args:
            message: The message to send
            task_type: "general", "coding", "reasoning", "speed", "quality"  
            priority: "cost", "speed", "quality", "balanced"
            force_provider: Force specific provider
            force_model: Force specific model
        """
        
        # Handle forced model
        if force_model:
            model_key = None
            for key, model in self.models.items():
                if model.name == force_model:
                    model_key = key
                    model_spec = model
                    break
            if not model_key:
                raise ValueError(f"Model '{force_model}' not found")
        else:
            model_key, model_spec = self.select_model(task_type, priority, force_provider)
        
        # Check budget for paid models
        if model_spec.cost_per_1m_input > 0:
            estimated_cost = (self._estimate_tokens(message) * 2) * model_spec.cost_per_1m_input / 1_000_000
            if estimated_cost > self.get_remaining_budget():
                print(f"⚠️ Estimated cost ${estimated_cost:.4f} exceeds remaining budget ${self.get_remaining_budget():.4f}")
                print("🔄 Switching to FREE local model...")
                
                # Fall back to local model
                for key, model in self.models.items():
                    if model.provider == "ollama" and self.available_providers.get("ollama"):
                        model_key, model_spec = key, model
                        break
                else:
                    raise ValueError("No free local models available and budget exceeded")
        
        # Get LLM client and generate response
        llm = self._get_llm_client(model_spec)
        result = llm.invoke(message)
        response = result.content
        
        # Track usage
        self._track_usage(model_key, message, response)
        
        return response
    
    def show_status(self):
        """Show comprehensive system status"""
        print("🚀 Cost-Free LLM Foundation Status")
        print("=" * 60)
        
        # Budget info
        daily_spending = self.get_daily_spending()
        remaining = self.get_remaining_budget()
        print(f"💰 Daily Budget: ${self.daily_budget:.2f}")
        print(f"💸 Today's Spending: ${daily_spending:.4f}")
        print(f"💵 Remaining: ${remaining:.2f}")
        
        # Available models by category
        print(f"\n🔗 Available Models:")
        
        categories = {
            "🆓 FREE (Local)": [k for k, m in self.models.items() 
                               if m.cost_per_1m_input == 0 and self.available_providers.get(m.provider)],
            "💰 Ultra-Cheap ($0.05-0.14)": [k for k, m in self.models.items() 
                                           if 0 < m.cost_per_1m_input <= 0.14 and self.available_providers.get(m.provider)],
            "🏆 Premium ($0.15+)": [k for k, m in self.models.items() 
                                   if m.cost_per_1m_input > 0.14 and self.available_providers.get(m.provider)]
        }
        
        for category, model_keys in categories.items():
            print(f"\n{category}:")
            if model_keys:
                for key in model_keys:
                    model = self.models[key]
                    cost_str = "FREE" if model.cost_per_1m_input == 0 else f"${model.cost_per_1m_input:.3f}/1M"
                    specialties = ", ".join(model.specialties[:2])
                    print(f"  ✅ {model.name} ({model.provider}) - {cost_str} - {specialties}")
            else:
                print(f"  ❌ None configured")
        
        # Setup recommendations
        total_available = sum(len(models) for models in categories.values())
        if total_available == 0:
            print(f"\n⚠️ No models available!")
            print(f"🔧 Quick Setup:")
            print(f"   1. Install Ollama: https://ollama.ai")
            print(f"   2. Run: ollama pull llama3.2")
            print(f"   3. Add GOOGLE_API_KEY to .env for scaling")
        else:
            print(f"\n✅ {total_available} models ready for cost-free AI development!")


# Global manager instance
_global_manager = None

def get_manager(daily_budget: float = 5.0) -> FoundationLLMManager:
    """Get or create the global LLM manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = FoundationLLMManager(daily_budget)
    return _global_manager

# Convenient functions for students
def chat(message: str, task_type: str = "general", priority: str = "cost", **kwargs) -> str:
    """
    Smart chat with cost-optimized model selection
    
    Examples:
        chat("Hello!")                                    # Cheapest available
        chat("Write Python code", task_type="coding")    # Coding-optimized
        chat("Solve puzzle", task_type="reasoning")      # Reasoning-optimized
        chat("Quick answer", priority="speed")           # Speed-optimized
        chat("Important analysis", priority="quality")   # Quality-optimized
    """
    return get_manager().chat(message, task_type, priority, **kwargs)

def free_chat(message: str) -> str:
    """Force free local models only"""
    return chat(message, force_provider="ollama")

def budget_chat(message: str) -> str:
    """Ultra-cheap models (prefer under $0.15/1M tokens)"""
    return chat(message, priority="cost")

def speed_chat(message: str) -> str:
    """Ultra-fast models (Groq, Gemini Flash)"""
    return chat(message, priority="speed")

def quality_chat(message: str) -> str:
    """Highest quality models (Claude, GPT-4)"""
    return chat(message, priority="quality")

def coding_chat(message: str) -> str:
    """Coding-optimized models"""
    return chat(message, task_type="coding")

def reasoning_chat(message: str) -> str:
    """Reasoning-optimized models"""
    return chat(message, task_type="reasoning")

def show_status():
    """Show system status and available models"""
    get_manager().show_status()

def setup_foundation(daily_budget: float = 5.0):
    """
    Initialize the cost-free LLM foundation
    
    Args:
        daily_budget: Maximum daily spending (default: $5)
    """
    manager = get_manager(daily_budget)
    print("🚀 Cost-Free LLM Foundation Initialized!")
    manager.show_status()
    return manager

if __name__ == "__main__":
    # Quick test
    setup_foundation()
