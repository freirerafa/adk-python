# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for canonical_xxx fields in LlmAgent."""

from typing import Any
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.registry import LLMRegistry
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.agents.content_config import ContentConfig, SummarizationConfig
from google.genai import types
from pydantic import BaseModel, ValidationError
import pytest


def _create_readonly_context(
    agent: LlmAgent, state: Optional[dict[str, Any]] = None
) -> ReadonlyContext:
  session_service = InMemorySessionService()
  session = session_service.create_session(
      app_name='test_app', user_id='test_user', state=state
  )
  invocation_context = InvocationContext(
      invocation_id='test_id',
      agent=agent,
      session=session,
      session_service=session_service,
  )
  return ReadonlyContext(invocation_context)


def test_canonical_model_empty():
  agent = LlmAgent(name='test_agent')

  with pytest.raises(ValueError):
    _ = agent.canonical_model


def test_canonical_model_str():
  agent = LlmAgent(name='test_agent', model='gemini-pro')

  assert agent.canonical_model.model == 'gemini-pro'


def test_canonical_model_llm():
  llm = LLMRegistry.new_llm('gemini-pro')
  agent = LlmAgent(name='test_agent', model=llm)

  assert agent.canonical_model == llm


def test_canonical_model_inherit():
  sub_agent = LlmAgent(name='sub_agent')
  parent_agent = LlmAgent(
      name='parent_agent', model='gemini-pro', sub_agents=[sub_agent]
  )

  assert sub_agent.canonical_model == parent_agent.canonical_model


def test_canonical_instruction_str():
  agent = LlmAgent(name='test_agent', instruction='instruction')
  ctx = _create_readonly_context(agent)

  assert agent.canonical_instruction(ctx) == 'instruction'


def test_canonical_instruction():
  def _instruction_provider(ctx: ReadonlyContext) -> str:
    return f'instruction: {ctx.state["state_var"]}'

  agent = LlmAgent(name='test_agent', instruction=_instruction_provider)
  ctx = _create_readonly_context(agent, state={'state_var': 'state_value'})

  assert agent.canonical_instruction(ctx) == 'instruction: state_value'


def test_canonical_global_instruction_str():
  agent = LlmAgent(name='test_agent', global_instruction='global instruction')
  ctx = _create_readonly_context(agent)

  assert agent.canonical_global_instruction(ctx) == 'global instruction'


def test_canonical_global_instruction():
  def _global_instruction_provider(ctx: ReadonlyContext) -> str:
    return f'global instruction: {ctx.state["state_var"]}'

  agent = LlmAgent(
      name='test_agent', global_instruction=_global_instruction_provider
  )
  ctx = _create_readonly_context(agent, state={'state_var': 'state_value'})

  assert (
      agent.canonical_global_instruction(ctx)
      == 'global instruction: state_value'
  )


def test_output_schema_will_disable_transfer(caplog: pytest.LogCaptureFixture):
  with caplog.at_level('WARNING'):

    class Schema(BaseModel):
      pass

    agent = LlmAgent(
        name='test_agent',
        output_schema=Schema,
    )

    # Transfer is automatically disabled
    assert agent.disallow_transfer_to_parent
    assert agent.disallow_transfer_to_peers
    assert (
        'output_schema cannot co-exist with agent transfer configurations.'
        in caplog.text
    )


def test_output_schema_with_sub_agents_will_throw():
  class Schema(BaseModel):
    pass

  sub_agent = LlmAgent(
      name='sub_agent',
  )

  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        output_schema=Schema,
        sub_agents=[sub_agent],
    )


def test_output_schema_with_tools_will_throw():
  class Schema(BaseModel):
    pass

  def _a_tool():
    pass

  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        output_schema=Schema,
        tools=[_a_tool],
    )


def test_before_model_callback():
  def _before_model_callback(
      callback_context: CallbackContext,
      llm_request: LlmRequest,
  ) -> None:
    return None

  agent = LlmAgent(
      name='test_agent', before_model_callback=_before_model_callback
  )

  # TODO: add more logic assertions later.
  assert agent.before_model_callback is not None


def test_validate_generate_content_config_thinking_config_throw():
  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig()
        ),
    )


def test_validate_generate_content_config_tools_throw():
  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        generate_content_config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[])]
        ),
    )


def test_validate_generate_content_config_system_instruction_throw():
  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        generate_content_config=types.GenerateContentConfig(
            system_instruction='system instruction'
        ),
    )


def test_validate_generate_content_config_response_schema_throw():
  class Schema(BaseModel):
    pass

  with pytest.raises(ValueError):
    _ = LlmAgent(
        name='test_agent',
        generate_content_config=types.GenerateContentConfig(
            response_schema=Schema
        ),
    )


def test_allow_transfer_by_default():
  sub_agent = LlmAgent(name='sub_agent')
  agent = LlmAgent(name='test_agent', sub_agents=[sub_agent])

  assert not agent.disallow_transfer_to_parent
  assert not agent.disallow_transfer_to_peers


# Tests for canonical_content_config
def test_canonical_content_config_default_string():
    agent = LlmAgent(name='test_agent', include_contents='default')
    config = agent.canonical_content_config
    assert isinstance(config, ContentConfig)
    assert config.enabled is True


def test_canonical_content_config_none_string():
    agent = LlmAgent(name='test_agent', include_contents='none')
    config = agent.canonical_content_config
    assert isinstance(config, ContentConfig)
    assert config.enabled is False


def test_canonical_content_config_object():
    custom_config = ContentConfig(enabled=True, max_events=5)
    agent = LlmAgent(name='test_agent', include_contents=custom_config)
    config = agent.canonical_content_config
    assert config is custom_config  # Should be the same object
    assert config.max_events == 5


# Tests for ContentConfig and SummarizationConfig models
def test_summarization_config_defaults():
    config = SummarizationConfig()
    assert config.model is None
    assert config.instruction is None
    assert config.max_tokens is None


def test_summarization_config_custom():
    config = SummarizationConfig(model="gemini-2.0-flash", instruction="Summarize.", max_tokens=123)
    assert config.model == "gemini-2.0-flash"
    assert config.instruction == "Summarize."
    assert config.max_tokens == 123


def test_content_config_defaults():
    config = ContentConfig()
    assert config.enabled is True
    assert config.include_authors is None
    assert config.exclude_authors is None
    assert config.max_events is None
    assert config.summarize is False
    assert config.summary_template == "Previous conversation summary: {summary}"
    assert config.summarization_config is None
    assert config.summarization_window is None
    assert config.always_include_last_n is None
    assert config.context_from_state is None
    assert config.state_template == "Session Information:\n{context}"


def test_content_config_custom():
    summ_cfg = SummarizationConfig(model="gemini-2.0-flash", instruction="Summarize.", max_tokens=50)
    config = ContentConfig(
        enabled=False,
        include_authors=["user", "agent"],
        max_events=10,
        summarize=True,
        summary_template="Summary: {summary}",
        summarization_config=summ_cfg,
        summarization_window=5,
        always_include_last_n=2,
        context_from_state=["foo", "bar"],
        state_template="CTX: {context}"
    )
    assert config.enabled is False
    assert config.include_authors == ["user", "agent"]
    assert config.exclude_authors is None
    assert config.max_events == 10
    assert config.summarize is True
    assert config.summary_template == "Summary: {summary}"
    assert config.summarization_config == summ_cfg
    assert config.summarization_window == 5
    assert config.always_include_last_n == 2
    assert config.context_from_state == ["foo", "bar"]
    assert config.state_template == "CTX: {context}"


def test_content_config_serialization():
    data = {
        "enabled": False,
        "include_authors": ["user"],
        "summarize": True,
        "summarization_config": {"model": "gemini-2.0-flash", "instruction": "Summarize briefly", "max_tokens": 100}
    }
    config = ContentConfig(**data)
    dumped = config.model_dump()
    assert dumped["enabled"] is False
    assert dumped["include_authors"] == ["user"]
    assert dumped["summarize"] is True
    assert dumped["summarization_config"]["model"] == "gemini-2.0-flash"


def test_content_config_type_validation():
    with pytest.raises(ValidationError):
        ContentConfig(enabled="not_a_valid_boolean")  # This should now raise ValidationError
    with pytest.raises(ValidationError):
        SummarizationConfig(max_tokens="thousand")  # This should correctly raise ValidationError
