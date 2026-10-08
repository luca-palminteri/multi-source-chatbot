"""Deterministic models for the subprocess API smoke check, never production routing."""
import asyncio
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool

from assistant.web import SchemaModel


class Model(SchemaModel):
    def _generate(self, messages, **kwargs):
        if messages[-1].type == "tool":
            if any("uncertain-test" in str(m.content) for m in messages if m.type == "human"):
                raise RuntimeError("private-provider-url-after-committed-action")
            answer = AIMessage(content="Tool result: " + str(messages[-1].content))
        else:
            text = str(messages[-1].content)
            if "fail-test" in text:
                raise RuntimeError("private-provider-url-and-credential")
            if "create-test" in text or "uncertain-test" in text:
                answer = AIMessage(content="", tool_calls=[{
                    "name": "create_service_request", "id": str(uuid4()),
                    "args": {"service_id": "svc-vpn", "summary": "API smoke request",
                             "description": "Disposable deterministic test"}}])
            elif "lookup-test" in text:
                answer = AIMessage(content="", tool_calls=[{
                    "name": "lookup_information", "id": str(uuid4()), "args": {"question": "VPN"}}])
            else:
                humans = [str(m.content) for m in messages if m.type == "human"]
                answer = AIMessage(content="Conversation: " + " | ".join(humans))
        return ChatResult(generations=[ChatGeneration(message=answer)])

    async def _agenerate(self, messages, **kwargs):
        if "slow-test" in str(messages[-1].content):
            await asyncio.sleep(3)
        return self._generate(messages, **kwargs)


class Pipeline:
    def as_tool(self):
        return StructuredTool.from_function(
            lambda question, context="": {"answer": "VPN policy [D1] and IT Operations [G1]",
                                          "sources": {"D1": {}, "G1": {}}},
            name="lookup_information", description="Deterministic read-only evidence")
