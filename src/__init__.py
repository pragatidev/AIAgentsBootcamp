"""
AI Agents Bootcamp - Complete Simple Interface
Easy-to-use functions for students with full 2025 model support
"""

from .llm_manager import ComprehensiveLLMManager, ModelInfo

# Global manager instance
_global_manager = None

def setup_llm(daily_budget: float = 10.0):
    """
    Initialize the LLM system with budget control
    
    Usage:
        from src import setup_llm
        setup_llm(daily_budget=5.0)
    """
    global _global_manager
    _global_manager = ComprehensiveLLMManager(daily_budget=daily_budget)
    
    print(f"🚀 AI Agents Bootcamp - LLM System Ready!")
    print(f"💰 Daily budget: ${daily_budget}")
    
    # Show available providers
    available = _global_manager.available_providers
    available_list = [provider for provider, status in available.items() if status]
    total_providers = len(available)
    
    print(f"🔗 Providers: {len(available_list)}/{total_providers} configured")
    
    # Show specific recommendations
    if available.get("deepseek"):
        print("🌟 DeepSeek detected - ultra-cheap learning mode ($0.14/1M tokens)!")
    if available.get("ollama"):
        print("🆓 Ollama detected - free local models available!")
    if available.get("groq"):
        print("⚡ Groq detected - ultra-fast inference available!")
    
    if len(available_list) == 0:
        print("⚠️  No providers configured. Check your .env file!")
        print("💡 Quick start: Add DEEPSEEK_API_KEY for ultra-cheap AI ($0.14/1M tokens)")
        print("🔧 Or install Ollama for completely free local models")
    
    return _global_manager

def get_manager():
    """Get or create the global LLM manager"""
    global _global_manager
    if _global_manager is None:
        _global_manager = setup_llm()
    return _global_manager

# =============================================================================
# SIMPLE CHAT FUNCTIONS
# =============================================================================

def chat(message: str, provider: str = None, model: str = None):
    """
    Simple chat with automatic or manual model selection
    
    Usage:
        # Automatic selection
        response = chat("Hello, how are you?")
        
        # Specific provider
        response = chat("Code a function", provider="deepseek")
        
        # Specific model
        response = chat("Explain AI", provider="openai", model="gpt-4o-mini")
        
        # Local DeepSeek R1
        response = chat("Solve this puzzle", provider="ollama", model="deepseek-r1:latest")
    """
    manager = get_manager()
    return manager.chat(message, provider, model)

def budget_chat(message: str):
    """
    Ultra-cheap chat (uses cheapest available model)
    
    Usage:
        response = budget_chat("What is machine learning?")
        # Uses models like DeepSeek ($0.14/1M) or Ollama (free)
    """
    manager = get_manager()
    return manager.chat(message, task_type="general", priority="cost")

def speed_chat(message: str):
    """
    Ultra-fast chat (uses fastest available model)
    
    Usage:
        response = speed_chat("Quick answer needed!")
        # Uses models like Groq (sub-100ms) or Gemini Flash
    """
    manager = get_manager()
    return manager.chat(message, task_type="general", priority="speed")

def quality_chat(message: str):
    """
    High-quality chat (uses best available model)
    
    Usage:
        response = quality_chat("Complex analysis needed")
        # Uses models like Claude 3.5 Sonnet or GPT-4o
    """
    manager = get_manager()
    return manager.chat(message, task_type="general", priority="quality")

def coding_chat(message: str):
    """
    Coding-optimized chat
    
    Usage:
        response = coding_chat("Write a Python sorting function")
        # Uses models optimized for coding like DeepSeek Coder or Codestral
    """
    manager = get_manager()
    return manager.chat(message, task_type="coding", priority="balanced")

def reasoning_chat(message: str):
    """
    Reasoning-optimized chat
    
    Usage:
        response = reasoning_chat("Solve this logic puzzle")
        # Uses models optimized for reasoning like DeepSeek R1 or o1-mini
    """
    manager = get_manager()
    return manager.chat(message, task_type="reasoning", priority="quality")

# =============================================================================
# MODEL DISCOVERY FUNCTIONS
# =============================================================================

def list_providers():
    """
    Show all available providers and their status
    
    Usage:
        list_providers()
    """
    manager = get_manager()
    
    print("\n🔗 LLM PROVIDERS & MODELS")
    print("=" * 70)
    
    for provider_name in manager.models.keys():
        available = manager.available_providers.get(provider_name, False)
        status = "✅ READY" if available else "❌ NOT CONFIGURED"
        
        print(f"\n{provider_name.upper()} - {status}")
        
        if available:
            models = list(manager.models[provider_name].keys())
            # Show first 3 models
            display_models = models[:3]
            print(f"   Models: {', '.join(display_models)}")
            if len(models) > 3:
                print(f"           + {len(models) - 3} more...")
            
            # Show sample model info
            sample_model = list(manager.models[provider_name].values())[0]
            if sample_model.input_cost == 0:
                cost_str = "FREE"
            else:
                cost_str = f"${sample_model.input_cost:.3f}/1M tokens"
            print(f"   Cost: {cost_str}")
            print(f"   Speed: {sample_model.speed_tier}")
            print(f"   Best for: {', '.join(sample_model.specialties[:2])}")
        else:
            print(f"   Setup: Add {provider_name.upper()}_API_KEY to .env file")

def show_cheapest_models(max_count: int = 10):
    """
    Show cheapest available models
    
    Usage:
        show_cheapest_models(5)
    """
    manager = get_manager()
    models = manager.get_models_by_cost()[:max_count]
    
    print(f"\n💰 CHEAPEST {len(models)} MODELS")
    print("=" * 50)
    
    for i, model in enumerate(models, 1):
        cost_str = "FREE" if model.input_cost == 0 else f"${model.input_cost:.3f}/1M"
        print(f"{i:2d}. {model.display_name:<25} {cost_str}")
        print(f"     Provider: {model.provider:<10} Speed: {model.speed_tier}")
        if "coding" in model.specialties:
            print(f"     🔧 Great for coding")
        if "reasoning" in model.specialties:
            print(f"     🧠 Great for reasoning")

def show_fastest_models(max_count: int = 10):
    """
    Show fastest available models
    
    Usage:
        show_fastest_models(5)
    """
    manager = get_manager()
    all_models = []
    
    # Collect all models and sort by speed
    for provider, models in manager.models.items():
        if manager.available_providers.get(provider, False):
            all_models.extend(models.values())
    
    # Sort by speed tier
    speed_order = {"ultra_fast": 0, "fast": 1, "medium": 2, "slow": 3}
    all_models.sort(key=lambda x: speed_order.get(x.speed_tier, 4))
    
    print(f"\n⚡ FASTEST {min(max_count, len(all_models))} MODELS")
    print("=" * 50)
    
    for i, model in enumerate(all_models[:max_count], 1):
        cost_str = "FREE" if model.input_cost == 0 else f"${model.input_cost:.3f}/1M"
        print(f"{i:2d}. {model.display_name:<25} {cost_str}")
        print(f"     Speed: {model.speed_tier:<12} Provider: {model.provider}")

def show_coding_models():
    """
    Show models optimized for coding
    
    Usage:
        show_coding_models()
    """
    manager = get_manager()
    models = manager.get_models_by_specialty("coding")
    
    print(f"\n🔧 CODING MODELS ({len(models)} available)")
    print("=" * 45)
    
    for i, model in enumerate(models, 1):
        cost_str = "FREE" if model.input_cost == 0 else f"${model.input_cost:.3f}/1M"
        print(f"{i:2d}. {model.display_name:<25} {cost_str}")
        print(f"     Provider: {model.provider:<10} Quality: {model.quality_tier}")

def show_reasoning_models():
    """
    Show models optimized for reasoning
    
    Usage:
        show_reasoning_models()
    """
    manager = get_manager()
    models = manager.get_models_by_specialty("reasoning")
    
    print(f"\n🧠 REASONING MODELS ({len(models)} available)")
    print("=" * 45)
    
    for i, model in enumerate(models, 1):
        cost_str = "FREE" if model.input_cost == 0 else f"${model.input_cost:.3f}/1M"
        print(f"{i:2d}. {model.display_name:<25} {cost_str}")
        print(f"     Provider: {model.provider:<10} Quality: {model.quality_tier}")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compare_models(*model_specs):
    """
    Compare multiple models side by side
    
    Usage:
        compare_models(
            ("openai", "gpt-4o-mini"),
            ("deepseek", "deepseek-chat"),
            ("google", "gemini-1.5-flash")
        )
    """
    manager = get_manager()
    comparison = manager.compare_models(list(model_specs))
    
    print(f"\n📊 MODEL COMPARISON")
    print("=" * 80)
    
    for model in comparison:
        if "error" in model:
            print(f"❌ {model['provider']}:{model['model']} - {model['error']}")
        else:
            available_str = "✅" if model['available'] else "❌"
            print(f"\n{available_str} {model['display_name']}")
            print(f"   Provider: {model['provider']}")
            print(f"   Model: {model['model']}")
            print(f"   Cost: ${model['input_cost']:.3f}/${model['output_cost']:.3f} per 1M tokens")
            print(f"   Speed: {model['speed_tier']:<12} Quality: {model['quality_tier']}")
            print(f"   Context: {model['context_window']:,} tokens")
            print(f"   Best for: {', '.join(model['specialties'])}")

def get_model_recommendation(task: str):
    """
    Get model recommendation for specific task
    
    Usage:
        get_model_recommendation("coding")
        get_model_recommendation("budget")
        get_model_recommendation("speed")
        get_model_recommendation("quality")
    """
    manager = get_manager()
    
    print(f"\n🎯 RECOMMENDATION FOR: {task.upper()}")
    print("=" * 50)
    
    try:
        if task.lower() in ["coding", "code", "programming"]:
            provider, model = manager.smart_model_selection("coding", "balanced")
        elif task.lower() in ["budget", "cheap", "cost"]:
            provider, model = manager.smart_model_selection("general", "cost")
        elif task.lower() in ["speed", "fast", "quick"]:
            provider, model = manager.smart_model_selection("general", "speed")
        elif task.lower() in ["quality", "best", "premium"]:
            provider, model = manager.smart_model_selection("general", "quality")
        elif task.lower() in ["reasoning", "logic", "analysis"]:
            provider, model = manager.smart_model_selection("reasoning", "quality")
        else:
            provider, model = manager.smart_model_selection("general", "balanced")
        
        model_info = manager.get_model_info(provider, model)
        
        print(f"🏆 RECOMMENDED: {model_info.display_name}")
        print(f"   Provider: {provider}")
        print(f"   Model: {model}")
        cost_str = "FREE" if model_info.input_cost == 0 else f"${model_info.input_cost:.3f}/1M"
        print(f"   Cost: {cost_str}")
        print(f"   Speed: {model_info.speed_tier}")
        print(f"   Quality: {model_info.quality_tier}")
        print(f"   Best for: {', '.join(model_info.specialties)}")
        
        print(f"\n💡 Usage:")
        print(f'   chat("Your message", provider="{provider}", model="{model}")')
        
    except Exception as e:
        print(f"❌ Could not get recommendation: {e}")

def quick_test():
    """
    Quick test of the LLM system with multiple models
    
    Usage:
        quick_test()
    """
    print("\n🧪 QUICK SYSTEM TEST")
    print("=" * 40)
    
    test_message = "Say 'Hello from' followed by your model name in one short sentence."
    
    # Test different priorities
    test_configs = [
        ("Budget", "general", "cost"),
        ("Speed", "general", "speed"),
        ("Coding", "coding", "balanced"),
    ]
    
    manager = get_manager()
    
    for test_name, task_type, priority in test_configs:
        try:
            print(f"\n{test_name} Test:")
            provider, model = manager.smart_model_selection(task_type, priority)
            response = manager.chat(test_message, provider, model)
            
            model_info = manager.get_model_info(provider, model)
            cost_str = "FREE" if model_info.input_cost == 0 else f"${model_info.input_cost:.3f}/1M"
            
            print(f"   Model: {model_info.display_name} ({cost_str})")
            print(f"   Response: {response[:100]}...")
            
        except Exception as e:
            print(f"   ❌ {test_name} test failed: {e}")
    
    print(f"\n✅ System test complete!")

def show_usage_summary():
    """
    Show usage and cost summary
    
    Usage:
        show_usage_summary()
    """
    manager = get_manager()
    summary = manager.get_usage_summary()
    
    print(f"\n📊 USAGE SUMMARY")
    print("=" * 30)
    print(f"💰 Daily budget: ${summary['daily_budget']:.2f}")
    print(f"💸 Daily spending: ${summary['daily_spending']:.2f}")
    print(f"💵 Remaining: ${summary['remaining_budget']:.2f}")
    print(f"📝 Total requests: {summary['total_requests']}")
    
    available_providers = [p for p, status in summary['available_providers'].items() if status]
    print(f"🔗 Available providers: {len(available_providers)}")
    for provider in available_providers:
        print(f"   ✅ {provider}")

# =============================================================================
# LOCAL MODEL HELPERS
# =============================================================================

def setup_local_deepseek_r1():
    """
    Helper to set up local DeepSeek R1 (if Ollama is available)
    
    Usage:
        setup_local_deepseek_r1()
    """
    manager = get_manager()
    
    if not manager.available_providers.get("ollama", False):
        print("❌ Ollama not available. Install from https://ollama.ai/")
        return False
    
    try:
        # Test if DeepSeek R1 is available
        response = chat("Hello! Are you DeepSeek R1?", provider="ollama", model="deepseek-r1:latest")
        print("✅ Local DeepSeek R1 is working!")
        print(f"Response: {response}")
        return True
    except Exception as e:
        print(f"❌ DeepSeek R1 not available: {e}")
        print("💡 Try: ollama pull deepseek-r1:latest")
        return False

def local_reasoning_chat(message: str):
    """
    Use local DeepSeek R1 for reasoning (completely free!)
    
    Usage:
        response = local_reasoning_chat("Solve this logic puzzle step by step")
    """
    return chat(message, provider="ollama", model="deepseek-r1:latest")

def local_coding_chat(message: str):
    """
    Use local DeepSeek Coder for coding (completely free!)
    
    Usage:
        response = local_coding_chat("Write a Python function to sort a list")
    """
    return chat(message, provider="ollama", model="deepseek-coder")

# =============================================================================
# MAKE FUNCTIONS AVAILABLE AT PACKAGE LEVEL
# =============================================================================

__all__ = [
    # Setup
    'setup_llm',
    'get_manager',
    
    # Chat functions
    'chat',
    'budget_chat',
    'speed_chat', 
    'quality_chat',
    'coding_chat',
    'reasoning_chat',
    
    # Discovery functions
    'list_providers',
    'show_cheapest_models',
    'show_fastest_models',
    'show_coding_models',
    'show_reasoning_models',
    
    # Utility functions
    'compare_models',
    'get_model_recommendation',
    'quick_test',
    'show_usage_summary',
    
    # Local model helpers
    'setup_local_deepseek_r1',
    'local_reasoning_chat',
    'local_coding_chat',
    
    # Advanced access
    'ComprehensiveLLMManager',
    'ModelInfo'
]