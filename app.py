"""
Chainlit conversational UI for GeoThermal Sim Assistant.
Run with: chainlit run app.py
"""

import chainlit as cl
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

from agent.agent import create_agent


@cl.on_chat_start
async def on_chat_start():
    """Initialize agent and welcome the user."""
    api_key = os.getenv("groq_api_key")

    if not api_key:
        await cl.Message(
            content="⚠️ **groq_api_key not set.** Please set it in your environment and restart."
        ).send()
        return

    agent = create_agent(groq_api_key=api_key)
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])

    await cl.Message(
        content=(
            "# 🌍 GeoThermal Sim Assistant\n\n"
            "I'm an AI agent that simulates **deep geothermal district heating networks** "
            "using [pandapipes](https://www.pandapipes.org/).\n\n"
            "**Try asking me:**\n"
            "- *Run a simulation with 5 consumers at 85°C supply temperature*\n"
            "- *Compare high-temp (90/60°C) vs low-temp (70/40°C) scenarios*\n"
            "- *What is a geothermal doublet?*\n"
            "- *What happens if I increase the pipe diameter to 0.15m?*\n"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Process user message through the LangGraph agent."""
    agent = cl.user_session.get("agent")
    history = cl.user_session.get("history", [])

    if not agent:
        await cl.Message(content="❌ Agent not initialized. Check your API key.").send()
        return

    # Show thinking indicator
    async with cl.Step(name="🔧 Running simulation...", type="tool") as step:
        messages = history + [HumanMessage(content=message.content)]
        try:
            result = agent.invoke({
                "messages": messages,
                "simulation_results": [],
                "current_params": {},
            })
        except Exception as e:
            step.output = f"Error: {e}"
            await cl.Message(
                content="Something went wrong calling the model. Please try again."
            ).send()
            return

        tools_called = [r["tool"] for r in result.get("simulation_results", [])]
        if tools_called:
            step.output = f"Used tools: {', '.join(tools_called)}"
        else:
            step.output = "Responded from knowledge base"

    # Update history
    final_message = result["messages"][-1]
    history.append(HumanMessage(content=message.content))
    history.append(AIMessage(content=final_message.content))
    cl.user_session.set("history", history[-10:])

    # Send response
    await cl.Message(content=final_message.content).send()
