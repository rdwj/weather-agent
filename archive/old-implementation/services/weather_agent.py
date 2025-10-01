"""LangChain agent with memory for weather queries."""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# Using MCP for weather data, not ChatOpenAI
from langchain.schema import AgentAction, AgentFinish
from langchain.callbacks.base import BaseCallbackHandler

from ..lib.mcp_weather_tool import MCPWeatherToolkit
from ..models.conversation_turn import ConversationTurn
from ..models.weather_query import Location
from .conversation_memory import ConversationMemoryManager

logger = logging.getLogger(__name__)


class WeatherAgentCallbackHandler(BaseCallbackHandler):
    """Callback handler for weather agent events."""

    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        """Log agent actions."""
        logger.debug(f"Agent action: {action.tool} with input: {action.tool_input}")

    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        """Log agent completion."""
        logger.debug(f"Agent finished with output: {finish.return_values}")


class WeatherAgent:
    """LangChain agent for processing weather queries with conversation memory."""

    def __init__(self,
                 session_id: str,
                 user_id: str,
                 memory_manager: Optional[ConversationMemoryManager] = None,
                 llm: Optional[Any] = None):
        """Initialize weather agent.

        Args:
            session_id: Session identifier
            user_id: User identifier
            memory_manager: Conversation memory manager
            llm: Language model (optional, defaults to ChatOpenAI)
        """
        self.session_id = session_id
        self.user_id = user_id
        self.memory_manager = memory_manager or ConversationMemoryManager(session_id)

        # Initialize LLM (in production, this would use actual LLM)
        # For now, using a mock or configurable LLM
        self.llm = llm or self._create_default_llm()

        # Initialize tools
        self.tools = MCPWeatherToolkit.get_tools()

        # Create agent
        self.agent_executor = self._create_agent()

        # Callback handler
        self.callback_handler = WeatherAgentCallbackHandler()

    def _create_default_llm(self):
        """Create default LLM for the agent."""
        # Using MockLLM since we're using MCP for weather data
        return MockLLM()

    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent with tools and memory."""
        # Create prompt template
        prompt = self._create_prompt_template()

        # Create memory
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Load conversation history from memory manager
        self._load_conversation_history(memory)

        # Create agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

        # Create agent executor
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=memory,
            verbose=True,
            max_iterations=3,
            handle_parsing_errors=True,
            callbacks=[self.callback_handler]
        )

    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Create the prompt template for the agent."""
        system_prompt = """You are a helpful weather assistant that provides accurate,
        current weather information. You have access to weather data through MCP tools.

        When answering weather queries:
        1. Extract location from the user's query
        2. Determine if they want current weather, forecast, or alerts
        3. Use the appropriate weather tool to get the information
        4. Provide a clear, concise response
        5. Remember context from previous queries in the conversation

        If the user asks about weather without specifying a location, check if there's
        a location from the previous context. If not, ask them to specify a location.

        Always be helpful and provide relevant weather details like temperature,
        conditions, humidity, and wind when available."""

        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

    def _load_conversation_history(self, memory: ConversationBufferMemory) -> None:
        """Load conversation history into agent memory."""
        try:
            history = self.memory_manager.get_conversation_history()
            for turn in history:
                memory.chat_memory.add_user_message(turn.user_query)
                memory.chat_memory.add_ai_message(turn.assistant_response)
        except Exception as e:
            logger.warning(f"Failed to load conversation history: {e}")

    async def process_query(self,
                           query: str,
                           location_context: Optional[Location] = None) -> Dict[str, Any]:
        """Process a weather query.

        Args:
            query: User's weather query
            location_context: Optional location context

        Returns:
            Response dictionary with weather information
        """
        try:
            # Add location context to query if provided
            enriched_query = query
            if location_context:
                enriched_query = f"{query} (Location context: {location_context.display_name})"

            # Run the agent
            result = await self.agent_executor.ainvoke({
                "input": enriched_query
            })

            # Extract response
            response_text = result.get("output", "I couldn't process your weather query.")

            # Save to conversation history
            turn = ConversationTurn(
                user_query=query,
                assistant_response=response_text,
                location_context=location_context
            )
            self.memory_manager.add_turn(turn)

            return {
                "response": response_text,
                "query": query,
                "session_id": self.session_id,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "response": "I encountered an error processing your weather query. Please try again.",
                "query": query,
                "session_id": self.session_id,
                "success": False,
                "error": str(e)
            }

    def extract_location_from_context(self) -> Optional[Location]:
        """Extract location from conversation context.

        Returns:
            Location if found in recent context, None otherwise
        """
        try:
            history = self.memory_manager.get_conversation_history(limit=5)
            for turn in reversed(history):
                if turn.location_context:
                    return turn.location_context
            return None
        except Exception as e:
            logger.warning(f"Failed to extract location from context: {e}")
            return None

    def clear_memory(self) -> None:
        """Clear conversation memory."""
        self.agent_executor.memory.clear()
        self.memory_manager.clear_history()


class MockLLM:
    """Mock LLM for testing when OpenAI is not available."""

    def invoke(self, messages: List[Any], **kwargs) -> str:
        """Mock invoke method."""
        return "Mock weather response - please configure a real LLM."

    async def ainvoke(self, messages: List[Any], **kwargs) -> str:
        """Mock async invoke method."""
        return "Mock weather response - please configure a real LLM."


class WeatherAgentFactory:
    """Factory for creating weather agents."""

    @staticmethod
    def create_agent(session_id: str,
                    user_id: str,
                    llm_config: Optional[Dict[str, Any]] = None) -> WeatherAgent:
        """Create a weather agent instance.

        Args:
            session_id: Session identifier
            user_id: User identifier
            llm_config: Optional LLM configuration

        Returns:
            Configured WeatherAgent instance
        """
        # Create memory manager
        memory_manager = ConversationMemoryManager(session_id)

        # Create LLM if config provided
        llm = None
        if llm_config:
            # LLM configuration not used with MCP
            pass

        # Create and return agent
        return WeatherAgent(
            session_id=session_id,
            user_id=user_id,
            memory_manager=memory_manager,
            llm=llm
        )