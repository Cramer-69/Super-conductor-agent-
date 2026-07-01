"""
Conductor agent that uses RAG to answer questions with context from all platforms.
"""

from typing import List, Dict, Any
import sys
from pathlib import Path

# Gracefully handle optional dependencies
GOOGLE_AVAILABLE = False
OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except (ImportError, Exception) as e:
    pass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except (ImportError, Exception) as e:
    pass

try:
    import httpx
except (ImportError, Exception) as e:
    httpx = None

# Core imports
from knowledge_base.retrieval import ConversationRetriever
from config.settings import settings
from utils.logger import logger
from skills.manager import SkillManager
from conductor.bedrock_client import BedrockClaude


class ConductorAgent:
    """Main conductor agent with RAG-based question answering."""
    
    def __init__(self, provider: str = "auto"):
        """Initialize the conductor agent.
        
        Args:
            provider: AI provider ('google', 'grok', 'openai', 'perplexity', or 'auto')
        """
        # Try to initialize retriever, but don't crash if it fails
        try:
            self.retriever = ConversationRetriever()
        except Exception as e:
            logger.warning(f"Could not initialize retriever: {e}. Running without memory.")
            self.retriever = None
            
        self.client = None
        self.provider = provider
        self.model = settings.conductor_model
        
        # Detect available providers. Claude on Bedrock is checked first —
        # it's the flagship provider for this app (AWS-native auth, no
        # Anthropic API key needed).
        if provider == "auto":
            if settings.bedrock_configured():
                self.provider = "bedrock"
                self.model = settings.bedrock_model_id
            elif settings.anthropic_api_key:
                self.provider = "anthropic"
                self.model = "claude-opus-4-8"
            elif GOOGLE_AVAILABLE and settings.google_api_key:
                self.provider = "google"
                self.model = "gemini-1.5-flash"  # Working model
            elif settings.xai_api_key:
                self.provider = "grok"
                self.model = "grok-2-latest"
            elif OPENAI_AVAILABLE and settings.openai_api_key:
                self.provider = "openai"
                self.model = "gpt-4o-mini"
            else:
                raise ValueError(
                    "No AI provider available. Set AWS_REGION (Claude on "
                    "Bedrock) or install google-generativeai / openai and "
                    "set the matching API key."
                )
        
        # Initialize Skills
        skills_path = Path(__file__).parent.parent / "skills"
        self.skill_manager = SkillManager(skills_path)
        self.current_skill = None
        
        logger.info(f"Initialized conductor agent with {self.provider.upper()}, model: {self.model}")
        logger.info(f"Loaded {len(self.skill_manager.skills)} skills")

    def activate_skill(self, skill_name: str) -> bool:
        """Activate a specific skill."""
        skill = self.skill_manager.get_skill(skill_name)
        if skill:
            self.current_skill = skill
            logger.info(f"Activated skill: {skill.name}")
            return True
        return False
    
    def _init_client(self):
        """Lazy initialize AI client based on provider."""
        if not self.client:
            if self.provider == "bedrock":
                self.client = BedrockClaude(region=settings.aws_region, model=self.model)
            elif self.provider == "anthropic":
                if not settings.anthropic_api_key:
                    raise ValueError("Anthropic API key not configured")
                import anthropic
                self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            elif self.provider == "google":
                if not settings.google_api_key:
                    raise ValueError("Google API key not configured")
                genai.configure(api_key=settings.google_api_key)
                self.client = "gemini"  # Flag
            elif self.provider == "grok":
                if not settings.xai_api_key:
                    raise ValueError("xAI/Grok API key not configured")
                self.client = httpx.Client(
                    base_url="https://api.x.ai/v1",
                    headers={"Authorization": f"Bearer {settings.xai_api_key}"}
                )
            elif self.provider == "openai":
                if not settings.openai_api_key:
                    raise ValueError("OpenAI API key not configured")
                self.client = OpenAI(api_key=settings.openai_api_key)
            elif self.provider == "perplexity":
                if not settings.perplexity_api_key:
                    raise ValueError("Perplexity API key not configured")
                self.client = httpx.Client(
                    base_url="https://api.perplexity.ai",
                    headers={"Authorization": f"Bearer {settings.perplexity_api_key}"}
                )
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
    
    def chat(
        self,
        query: str,
        platform_filter: str = None,
        max_context_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Answer a query using RAG with conversation history.
        
        Args:
            query: User question
            platform_filter: Optional platform to filter (chatgpt, gemini, grok, antigravity)
            max_context_tokens: Maximum tokens for context
            
        Returns:
            Dict with 'response', 'sources', and 'context_used'
        """
        self._init_client()
        
        # Retrieve relevant context
        logger.info(f"Processing query: {query[:100]}...")
        
        results = self.retriever.search_conversations(
            query=query,
            n_results=5,
            platform_filter=platform_filter
        )
        
        # Format context
        context_parts = []
        sources = []
        
        for result in results:
            meta = result['metadata']
            content = result['content']
            
            source_info = {
                'platform': meta['platform'],
                'title': meta['title'],
                'conversation_id': meta.get('conversation_id', ''),
                'score': result['score']
            }
            sources.append(source_info)
            
            # Add to context
            context_parts.append(
                f"[Source: {meta['platform'].upper()} - {meta['title']}]\n{content}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build prompt
        base_system_prompt = """You are a helpful AI assistant with access to the user's conversation history across multiple AI platforms (ChatGPT, Gemini, Grok, and Antigravity).

Your role is to:
1. Answer questions using the provided context from past conversations
2. Cite which platform and conversation the information came from
3. Synthesize information from multiple sources when relevant
4. Be honest when the context doesn't contain the answer

Always mention the source platform (ChatGPT/Gemini/Grok/Antigravity) when referencing information from the context."""

        # Inject Skill Prompt if active
        if self.current_skill:
            system_prompt = f"{self.current_skill.prompt}\n\n---\n\n{base_system_prompt}"
            logger.info(f"Using skill prompt: {self.current_skill.name}")
        else:
            system_prompt = base_system_prompt

        user_prompt = f"""Based on my conversation history, please answer this question:

{query}

Here is the relevant context from your past conversations:

{context}

Please provide a helpful answer based on this context. Cite which conversations/platforms you're referencing."""

        # Get completion based on provider
        try:
            if self.provider == "bedrock":
                # Use Claude on Amazon Bedrock
                answer = self.client.chat(
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=1000,
                )
            elif self.provider == "anthropic":
                # Use Claude via the first-party Anthropic API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                answer = "".join(block.text for block in response.content if hasattr(block, "text"))
            elif self.provider == "google":
                # Use Google Gemini
                model = genai.GenerativeModel(self.model)
                response = model.generate_content(
                    f"{system_prompt}\n\n{user_prompt}",
                    generation_config={"temperature": 0.7, "max_output_tokens": 1000}
                )
                answer = response.text
            elif self.provider == "grok":
                # Use Grok/xAI
                response = self.client.post(
                    "/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1000
                    }
                ).json()
                answer = response['choices'][0]['message']['content']
            elif self.provider == "openai":
                # Use OpenAI
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                answer = response.choices[0].message.content
            elif self.provider == "perplexity":
                # Use Perplexity
                response = self.client.post(
                    "/chat/completions",
                    json={
                        "model": "llama-3.1-sonar-large-128k-online",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.7
                    }
                ).json()
                answer = response['choices'][0]['message']['content']
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
            
            return {
                'response': answer,
                'sources': sources,
                'context_used': len(context),
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def stream_chat(
        self,
        query: str,
        platform_filter: str = None
    ):
        """
        Stream a chat response (for CLI display).
        
        Args:
            query: User question
            platform_filter: Optional platform filter
            
        Yields:
            Response chunks
        """
        self._init_client()
        
        # Retrieve context
        results = self.retriever.search_conversations(
            query=query,
            n_results=5,
            platform_filter=platform_filter
        )
        
        # Format context and sources
        context_parts = []
        sources = []
        
        for result in results:
            meta = result['metadata']
            content = result['content']
            
            sources.append({
                'platform': meta['platform'],
                'title': meta['title'],
                'score': result['score']
            })
            
            context_parts.append(
                f"[Source: {meta['platform'].upper()} - {meta['title']}]\n{content}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Build prompt
        base_system_prompt = """You are a helpful AI assistant with access to the user's conversation history across multiple AI platforms (ChatGPT, Gemini, Grok, and Antigravity).

Your role is to:
1. Answer questions using the provided context from past conversations
2. Cite which platform and conversation the information came from
3. Synthesize information from multiple sources when relevant
4. Be honest when the context doesn't contain the answer

Always mention the source platform when referencing information."""

        # Inject Skill Prompt if active
        if self.current_skill:
            system_prompt = f"{self.current_skill.prompt}\n\n---\n\n{base_system_prompt}"
            logger.info(f"Using skill prompt: {self.current_skill.name}")
        else:
            system_prompt = base_system_prompt

        user_prompt = f"""Based on my conversation history, please answer this question:

{query}

Here is the relevant context from your past conversations:

{context}

Please provide a helpful answer based on this context. Cite which conversations/platforms you're referencing."""

        # Stream response
        try:
            # First yield sources
            yield {'type': 'sources', 'data': sources}

            if self.provider == "bedrock":
                for text in self.client.stream(
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_tokens=1000,
                ):
                    yield {'type': 'content', 'data': text}
                return

            if self.provider == "anthropic":
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    for text in stream.text_stream:
                        yield {'type': 'content', 'data': text}
                return

            # OpenAI-compatible providers (openai, grok, perplexity via httpx
            # aside) use the chat.completions streaming shape.
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {'type': 'content', 'data': chunk.choices[0].delta.content}

        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            yield {'type': 'error', 'data': str(e)}


if __name__ == "__main__":
    # Test the conductor
    conductor = ConductorAgent()
    
    result = conductor.chat("What projects have I worked on?")
    
    print("Response:")
    print(result['response'])
    print(f"\nSources: {len(result['sources'])}")
    for source in result['sources']:
        print(f"  - {source['platform'].upper()}: {source['title']} (score: {source['score']:.2f})")
