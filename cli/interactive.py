"""
Interactive CLI for the Conductor Agent.
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from knowledge_base.retrieval import ConversationRetriever
from knowledge_base.vector_store import ConversationVectorStore
from conductor.agent import ConductorAgent
from config.settings import settings

console = Console()


class InteractiveCLI:
    """Interactive command-line interface for conductor agent."""
    
    def __init__(self):
        self.conductor = ConductorAgent()
        self.retriever = self.conductor.retriever
        self.vector_store = self.retriever.vector_store
        self.running = True
        
        console.print(Panel.fit(
            "[bold cyan]Conductor AI Super Agent[/bold cyan]\n"
            "[dim]Multi-Model Intelligent Assistant[/dim]\n\n"
            "Available Providers:\n"
            "• [green]Google Gemini[/green] (Primary)\n"
            "• [blue]Grok / xAI[/blue]\n"
            "• [yellow]Perplexity[/yellow]\n"
            "• [white]OpenAI[/white]",
            border_style="cyan"
        ))
        
        # Show database stats
        self._show_stats()
    
    def _show_stats(self):
        """Show database statistics."""
        try:
            conv_count = self.vector_store.get_collection_count(settings.conversations_collection)
            code_count = self.vector_store.get_collection_count(settings.code_collection)
            
            console.print(f"\n📊 Database Stats:")
            console.print(f"  • Conversations: {conv_count:,}")
            console.print(f"  • Code Snippets: {code_count:,}")
            console.print()
        except Exception as e:
            console.print(f"[yellow]⚠️  Database not initialized. Run ingestion first.[/yellow]\n")
    
    def run(self):
        """Main CLI loop."""
        while self.running:
            try:
                # Get user input
                query = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                
                if not query.strip():
                    continue
                
                # Handle commands
                if query.startswith('/'):
                    self._handle_command(query)
                    continue
                
                # Process query
                self._process_query(query)
                
            except KeyboardInterrupt:
                self._exit()
            except EOFError:
                self._exit()
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    def _handle_command(self, command: str):
        """Handle CLI commands."""
        cmd = command.lower().strip()
        
        if cmd == '/help':
            self._show_help()
        elif cmd == '/stats':
            self._show_stats()
        elif cmd.startswith('/search '):
            query = command[8:].strip()
            self._search(query)
        elif cmd.startswith('/code '):
            query = command[6:].strip()
            self._search_code(query)
        elif cmd.startswith('/platform '):
            parts = command[10:].strip().split(' ', 1)
            if len(parts) == 2:
                platform, query = parts
                self._search_platform(platform, query)
            else:
                console.print("[red]Usage: /platform <platform> <query>[/red]")
        elif cmd.startswith('/skill '):
            skill_name = command[7:].strip()
            self._activate_skill(skill_name)
        elif cmd == '/skills':
            self._list_skills()
        elif cmd == '/clear':
            console.clear()
            self._show_stats()
        elif cmd == '/exit' or cmd == '/quit':
            self._exit()
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            console.print("Type /help for available commands")
    
    def _show_help(self):
        """Show help message."""
        help_text = """
# Conductor Agent Commands

## Search Commands
- **Ask anything**: Just type your question
- `/search <query>` - Search conversations
- `/code <query>` - Search code snippets
- `/platform <name> <query>` - Search specific platform (chatgpt, gemini, grok, antigravity)

## Superpower Skills (NEW)
- `/skills` - List available skills (brainstorming, TDD, etc.)
- `/skill <name>` - Activate a superpower skill

## Utility Commands
- `/stats` - Show database statistics
- `/clear` - Clear screen
- `/help` - Show this help
- `/exit` - Exit the application

## Examples
```
How did I implement authentication before?
/code python async patterns
/platform chatgpt explain RAG architecture
```
"""
        console.print(Markdown(help_text))
    
    def _process_query(self, query: str):
        """Process a natural language query with conversational AI."""
        console.print(f"\n[bold green]Conductor[/bold green]: ", end="")
        
        try:
            # Stream the response
            sources = []
            response_text = ""
            
            for chunk in self.conductor.stream_chat(query):
                if chunk['type'] == 'sources':
                    sources = chunk['data']
                elif chunk['type'] == 'content':
                    console.print(chunk['data'], end="")
                    response_text += chunk['data']
                elif chunk['type'] == 'error':
                    console.print(f"\n[red]Error: {chunk['data']}[/red]")
                    return
            
            console.print("\n")
            
            # Display sources
            if sources:
                console.print("\n[dim]📚 Sources:[/dim]")
                for source in sources[:3]:  # Show top 3 sources
                    platform = source['platform'].upper()
                    title = source['title']
                    score = source.get('score')  # connector-sourced entries (e.g. GitHub) have no relevance score

                    platform_colors = {
                        'CHATGPT': 'green',
                        'GEMINI': 'blue',
                        'GROK': 'magenta',
                        'ANTIGRAVITY': 'cyan'
                    }
                    color = platform_colors.get(platform, 'white')

                    relevance = f" [dim](relevance: {score:.1%})[/dim]" if score is not None else ""
                    console.print(f"  [{color}]•[/{color}] {platform}: {title}{relevance}")
                console.print()
        
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("[yellow]Tip: Make sure your OPENAI_API_KEY is set in .env file[/yellow]")
    
    def _search(self, query: str):
        """Search conversations."""
        self._process_query(query)
    
    def _search_code(self, query: str):
        """Search code snippets."""
        console.print(f"\n[bold green]Conductor[/bold green]: Searching code snippets...\n")
        
        results = self.retriever.search_code(query, n_results=5)
        
        if not results:
            console.print("[yellow]No code snippets found.[/yellow]")
            return
        
        console.print(f"[bold]Found {len(results)} code snippets:[/bold]\n")
        
        for i, result in enumerate(results):
            meta = result['metadata']
            content = result['content']
            score = result['score']
            
            console.print(Panel(
                f"[bold]Language: {meta.get('language', 'unknown')}[/bold]\n"
                f"Context: {meta.get('context', 'N/A')}\n\n"
                f"{content}\n\n"
                f"[dim]Relevance: {score:.1%} | Platform: {meta.get('platform', 'unknown').upper()}[/dim]",
                title=f"Code Snippet {i+1}",
                border_style="green"
            ))
            console.print()
    
    def _search_platform(self, platform: str, query: str):
        """Search specific platform."""
        console.print(f"\n[bold green]Conductor[/bold green]: Searching {platform.upper()}...\n")
        
        results = self.retriever.search_conversations(
            query,
            n_results=5,
            platform_filter=platform.lower()
        )
        
        if not results:
            console.print(f"[yellow]No results found in {platform.upper()}.[/yellow]")
            return
        
        self._display_results(results)
    
    def _display_results(self, results):
        """Display search results."""
        for i, result in enumerate(results):
            meta = result['metadata']
            content = result['content']
            score = result['score']
            
            console.print(Panel(
                f"[bold]{meta['title']}[/bold]\n\n"
                f"{content[:500]}{'...' if len(content) > 500 else ''}\n\n"
                f"[dim]Relevance: {score:.1%} | Platform: {meta['platform'].upper()}[/dim]",
                border_style="cyan"
            ))
            console.print()
    
    def _list_skills(self):
        """List available skills."""
        skills = self.conductor.skill_manager.list_skills()
        if not skills:
            console.print("[yellow]No skills loaded.[/yellow]")
            return

        console.print("\n[bold]Available Superpowers:[/bold]")
        for skill in skills:
            console.print(f"• [cyan]{skill.name}[/cyan]: {skill.description[:100]}...")
        console.print()

    def _activate_skill(self, name: str):
        """Activate a skill."""
        success = self.conductor.activate_skill(name)
        if success:
            console.print(f"\n[green]Activated Superpower: {name}[/green]\n")
        else:
            console.print(f"\n[red]Skill not found: {name}[/red]")
            console.print("Type /skills to see available options.\n")

    def _exit(self):
        """Exit the CLI."""
        console.print("\n[bold blue]👋 Goodbye![/bold blue]\n")
        self.running = False
        sys.exit(0)


def main():
    """Main entry point."""
    try:
        cli = InteractiveCLI()
        cli.run()
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
