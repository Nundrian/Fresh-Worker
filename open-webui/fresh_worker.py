"""
Open WebUI Workspace Tool: Fresh Worker

title: Fresh Worker
author: Nundrian
git_url: https://github.com/Nundrian/Fresh-Worker
version: 0.1.3
description: Run one bounded prompt in a brand-new saved Open WebUI chat and return its completed response.
requirements: httpx
licence: MIT

Creates one saved chat, sends one prompt, polls until completion, validates the
saved result, and returns the assistant response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import tempfile
import time
import uuid
from http import HTTPStatus
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field


class FreshWorkerError(RuntimeError):
    """Explicit execution failure; remote bodies are never copied into diagnostics."""

    def __init__(
        self, kind: str, message: str, *, http_status: Optional[int] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.http_status = http_status
        self.endpoint = endpoint
        self.chat_id: Optional[str] = None
        super().__init__(f"{kind}: {message}")


class _SavedPending(FreshWorkerError):
    """Only absent messages and unfinished completion can reflect persistence lag."""


class Tools:
    class Valves(BaseModel):
        base_url: str = Field(default="", description="Open WebUI base URL reachable from its server")
        api_key: str = Field(
            default="", description="API key; its account owns every worker chat",
            json_schema_extra={"input": {"type": "password"}},
        )
        worker_model: str = Field(default="", description="Optional fallback model ID when chat metadata is unavailable; blank uses the current chat model")
        wait_timeout: int = Field(default=600, description="Execution deadline in seconds, excluding evidence and bounded stop cleanup")
        poll_interval: int = Field(default=2, description="Seconds between task polls")
        evidence_dir: str = Field(default="", description="Optional server-side directory for retrieved chat JSON; empty disables evidence")

    def __init__(self) -> None:
        self.valves = self.Valves()

    @staticmethod
    def _validate_chat_id(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise FreshWorkerError("malformed_response", "Open WebUI returned an invalid or unsafe chat ID")
        return value

    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json", "Authorization": f"Bearer {self.valves.api_key}"}

    def _base_url(self) -> str:
        return self.valves.base_url.strip().rstrip("/")

    def _chat_body(
        self, model_id: str, prompt: str, user_id: str, assistant_id: str,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        timestamp = int(time.time())
        user_message = {
            "id": user_id, "role": "user", "content": prompt, "parentId": None,
            "timestamp": timestamp, "models": [model_id], "childrenIds": [assistant_id],
        }
        assistant_message = {
            "id": assistant_id, "role": "assistant", "content": "", "parentId": user_id,
            "childrenIds": [], "model": model_id, "modelName": model_id, "modelIdx": 0,
            "done": False, "timestamp": timestamp + 1,
        }
        return {"chat": {
            "title": "Fresh Worker", "models": [model_id],
            "messages": [user_message, assistant_message],
            "history": {"currentId": assistant_id, "messages": {
                user_id: user_message, assistant_id: assistant_message,
            }},
            "currentId": assistant_id,
            "params": {"system": system_prompt} if system_prompt else {},
        }}

    def _completion_body(
        self, chat_id: str, assistant_id: str, model_id: str, prompt: str,
        session_id: str, user_message: dict, system_prompt: str = "",
    ) -> dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        messages.append({"role": "user", "content": prompt})
        return {
            "chat_id": chat_id, "id": assistant_id, "messages": messages,
            # v0.11.3 uses this to link the assistant and reload this chat's user history.
            "user_message": user_message,
            "model": model_id, "stream": True, "session_id": session_id,
            "tools": [], "tool_ids": [], "tool_servers": [], "skill_ids": [],
            "features": {"web_search": False, "code_interpreter": False,
                         "image_generation": False, "memory": False},
            "background_tasks": {"title_generation": False, "tags_generation": False,
                                 "follow_up_generation": False},
        }

    def _parse_retrieved_chat(self, retrieved: dict[str, Any]) -> dict[str, Any]:
        chat = retrieved.get("chat")
        if not isinstance(chat, dict):
            raise FreshWorkerError("malformed_response", "saved chat must be an object")
        history = chat.get("history")
        if not isinstance(history, dict):
            raise FreshWorkerError("malformed_response", "saved chat.history must be an object")
        messages = history.get("messages")
        if not isinstance(messages, dict):
            raise FreshWorkerError("malformed_response", "saved chat.history.messages must be an object")
        return {"chat": chat, "messages": messages}

    def _validate_saved(
        self, retrieved: dict, chat_id: str, model_id: str, prompt: str,
        user_id: str, assistant_id: str, system_prompt: str,
    ) -> str:
        parsed = self._parse_retrieved_chat(retrieved)
        chat, messages = parsed["chat"], parsed["messages"]
        if retrieved.get("id") != chat_id:
            raise FreshWorkerError("malformed_response", "retrieved chat ID does not match")
        models = chat.get("models")
        if not isinstance(models, list) or models != [model_id]:
            raise FreshWorkerError("malformed_response", "saved model list does not match")
        if system_prompt:
            params = chat.get("params")
            if not isinstance(params, dict) or params.get("system") != system_prompt:
                raise FreshWorkerError("malformed_response", "saved system prompt does not match")
        # Check explicit errors before considering any persistence retry.
        for record in (retrieved, chat, messages.get(assistant_id)):
            if isinstance(record, dict) and record.get("error") not in (None, False, "", {}, []):
                raise FreshWorkerError("generation", "saved execution contains an explicit backend error")
        if user_id not in messages:
            raise _SavedPending("malformed_response", "saved user message is missing")
        user = messages[user_id]
        if not isinstance(user, dict) or user.get("role") != "user" or user.get("content") != prompt:
            raise FreshWorkerError("malformed_response", "saved user prompt or role does not match")
        if user.get("id") != user_id or user.get("parentId") is not None:
            raise FreshWorkerError("malformed_response", "saved user identity or parent does not match")
        if assistant_id not in messages:
            raise _SavedPending("malformed_response", "saved assistant message is missing")
        assistant = messages[assistant_id]
        if not isinstance(assistant, dict):
            raise FreshWorkerError("malformed_response", "saved assistant message must be an object")
        if (assistant.get("id") != assistant_id or assistant.get("role") != "assistant"
                or assistant.get("parentId") != user_id):
            raise FreshWorkerError("malformed_response", "saved assistant identity, role or parent does not match")
        # 'model' is the saved logical ID (including custom aliases). The host
        # persists an explicit arena/routing selection as camelCase; snake_case
        # belongs to response events, not the saved-message schema.
        if assistant.get("model") != model_id or assistant.get("selectedModelId", model_id) != model_id:
            raise FreshWorkerError("malformed_response", "saved assistant model does not match")
        if "done" not in assistant or assistant["done"] is False:
            raise _SavedPending("generation", "saved assistant is not yet complete")
        if assistant["done"] is not True:
            raise FreshWorkerError("malformed_response", "saved assistant done flag must be a boolean")
        content = assistant.get("content")
        if not isinstance(content, str):
            raise FreshWorkerError("malformed_response", "saved assistant content must be a string")
        if not content.strip():
            raise FreshWorkerError("generation", "completed assistant response is empty or whitespace-only")
        return content

    async def _http_request(
        self, client: httpx.AsyncClient, method: str, path: str,
        body: Optional[dict] = None, *, deadline: Optional[float] = None,
    ) -> tuple[int, dict]:
        remaining = 30.0 if deadline is None else deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError
        try:
            # httpx's per-operation network timeout alone is not a total deadline.
            async with asyncio.timeout(remaining):
                response = await client.request(
                    method, path.lstrip("/"), json=body, timeout=min(30.0, remaining),
                )
        except httpx.TimeoutException:
            if deadline is not None and asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError from None
            raise FreshWorkerError("network_timeout", f"{method} {path}: network request timed out",
                                   endpoint=path) from None
        except httpx.RequestError:
            raise FreshWorkerError("network", f"{method} {path}: transport failure",
                                   endpoint=path) from None
        try:
            data = response.json()
        except ValueError:
            data = None
        if not 200 <= response.status_code < 300:
            # Server text can echo credentials, headers or prompt content. Parse its
            # structure for context, but never propagate arbitrary remote values.
            detail = data.get("detail", data.get("error")) if isinstance(data, dict) else None
            detail_type = type(detail).__name__ if detail is not None else "unavailable"
            try:
                reason = HTTPStatus(response.status_code).phrase
            except ValueError:
                reason = "Server rejection"
            kind = "authentication" if response.status_code in (401, 403) else "http"
            raise FreshWorkerError(
                kind, f"{method} {path}: HTTP {response.status_code} {reason}; "
                f"error detail type={detail_type} (remote contents withheld)",
                http_status=response.status_code, endpoint=path,
            ) from None
        if not isinstance(data, dict):
            raise FreshWorkerError("malformed_response",
                                   f"{method} {path}: expected a JSON object (HTTP {response.status_code})",
                                   http_status=response.status_code, endpoint=path)
        return response.status_code, data

    async def _stop(self, client: httpx.AsyncClient, chat_id: str) -> Optional[str]:
        try:
            deadline = asyncio.get_running_loop().time() + 2.0
            _, result = await self._http_request(
                client, "POST", f"/api/tasks/chat/{chat_id}/stop", deadline=deadline,
            )
            if result.get("error") or result.get("status") is False:
                return "server rejected stop request"
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                return "stop cleanup timed out"
            return str(exc) if isinstance(exc, FreshWorkerError) else f"stop cleanup failed ({type(exc).__name__})"
        return None

    async def _cleanup(self, client: httpx.AsyncClient, chat_id: str) -> Optional[str]:
        # Keep the client open until bounded cleanup ends. Repeated caller
        # cancellation cannot cancel this stop or replace the original exception.
        cleanup = asyncio.create_task(self._stop(client, chat_id))
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        return cleanup.result()

    @staticmethod
    def _write_evidence(directory: str, chat_id: str, retrieved: dict) -> str:
        Tools._validate_chat_id(chat_id)
        os.makedirs(directory, exist_ok=True)
        # Exclusive creation avoids overwrites even if a server repeats a chat ID.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=f"chat-{chat_id}-",
            suffix=".json", dir=directory, delete=False,
        ) as handle:
            path = handle.name
            try:
                json.dump(retrieved, handle, indent=2, ensure_ascii=False)
            except Exception:
                handle.close()
                os.unlink(path)
                raise
        return os.path.abspath(path)

    async def fresh_worker(
        self, prompt: str, __event_emitter__: Optional[Any] = None,
        model: Optional[str] = None, system_prompt: str = "",
        __metadata__: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Run one prompt in a fresh saved chat and return only a verified response.

        :param prompt: Exact user prompt; whitespace and line endings are preserved.
        :param model: Optional exact model ID override; omitted uses the selected
            Open WebUI chat model, then the configured worker_model fallback.
        :param system_prompt: Optional separate system instruction; empty adds none.
        """
        base_url = self._base_url()
        try:
            parsed_url = httpx.URL(base_url)
        except httpx.InvalidURL:
            raise ValueError("base_url is not a valid HTTP(S) URL") from None
        if parsed_url.scheme not in ("http", "https") or not parsed_url.host or parsed_url.userinfo or parsed_url.query or parsed_url.fragment:
            raise ValueError("base_url must be an HTTP(S) URL without credentials, query or fragment")
        if not self.valves.api_key or self.valves.api_key != self.valves.api_key.strip() or any(
            ord(c) < 32 or ord(c) > 126 for c in self.valves.api_key
        ):
            raise ValueError("api_key is not configured or contains invalid characters")
        # Open WebUI supplies the calling chat model through __metadata__["model"].
        # Do not use __model__ here: it can refer to the configured task model,
        # which may differ from the model selected in the chat.
        selected = model
        if selected is None:
            chat_model = __metadata__.get("model") if isinstance(__metadata__, dict) else None
            if isinstance(chat_model, dict):
                chat_model = chat_model.get("id")
            selected = chat_model if isinstance(chat_model, str) and chat_model else self.valves.worker_model.strip()
        if (not isinstance(selected, str) or not selected or selected != selected.strip()
                or len(selected) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in selected)):
            raise ValueError("No valid model ID: select an Open WebUI chat model, pass an explicit model, or configure worker_model")
        model_id = selected
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must not be empty or whitespace-only")
        if not isinstance(system_prompt, str):
            raise ValueError("system_prompt must be a string")
        wait_timeout, poll_interval = self.valves.wait_timeout, self.valves.poll_interval
        if not math.isfinite(wait_timeout) or wait_timeout <= 0:
            raise ValueError("wait_timeout must be greater than zero and finite")
        if not math.isfinite(poll_interval) or poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero and finite")
        evidence_dir = self.valves.evidence_dir.strip()
        headers = self._build_headers()  # Snapshot configuration once per invocation.
        user_id, assistant_id, session_id = (str(uuid.uuid4()) for _ in range(3))
        chat_id: Optional[str] = None
        generation_may_run = False

        async def emit(description: str, done: bool = False) -> None:
            if callable(__event_emitter__):
                try:
                    await __event_emitter__({"type": "status", "data": {"description": description, "done": done}})
                except Exception as exc:
                    # Cancellation is a BaseException and must continue to the
                    # invocation's cancellation/stop path. Never log callback text.
                    logging.getLogger(__name__).warning(
                        "Fresh Worker status notification failed (%s)", type(exc).__name__,
                    )

        chat_body = self._chat_body(model_id, prompt, user_id, assistant_id, system_prompt)
        deadline = asyncio.get_running_loop().time() + wait_timeout
        async with httpx.AsyncClient(base_url=base_url + "/", headers=headers, timeout=30,
                                    follow_redirects=False) as client:
            try:
                # Includes status callbacks, all HTTP phases and sleeps.
                async with asyncio.timeout_at(deadline):
                    await emit("Validating Fresh Worker configuration ...")
                    _, created = await self._http_request(
                        client, "POST", "/api/v1/chats/new", chat_body, deadline=deadline,
                    )
                    chat_id = self._validate_chat_id(created.get("id"))
                    await emit(f"Fresh Worker chat created: {chat_id}")
                    completion_body = self._completion_body(
                        chat_id, assistant_id, model_id, prompt, session_id,
                        chat_body["chat"]["history"]["messages"][user_id], system_prompt,
                    )
                    # The request could be accepted even if its response is lost.
                    generation_may_run = True
                    try:
                        _, started = await self._http_request(
                            client, "POST", "/api/chat/completions", completion_body, deadline=deadline,
                        )
                    except FreshWorkerError as exc:
                        if exc.http_status is not None and 400 <= exc.http_status < 500:
                            generation_may_run = False
                        raise
                    task_ids = started.get("task_ids")
                    if (started.get("status") is not True or started.get("chat_id") != chat_id
                            or not isinstance(task_ids, list)
                            or any(not isinstance(t, str) or not t for t in task_ids)):
                        raise FreshWorkerError("generation", "unexpected completion acceptance response")
                    await emit(f"Completion accepted; tasks={len(task_ids)}")
                    last_count = None
                    while True:
                        _, tasks = await self._http_request(
                            client, "GET", f"/api/tasks/chat/{chat_id}", deadline=deadline,
                        )
                        task_ids = tasks.get("task_ids")
                        if (not isinstance(task_ids, list)
                                or any(not isinstance(t, str) or not t for t in task_ids)):
                            raise FreshWorkerError("malformed_response", "task listing must contain string task_ids")
                        if len(task_ids) != last_count:
                            await emit(f"Poll: active tasks={len(task_ids)}")
                            last_count = len(task_ids)
                        if not task_ids:
                            break
                        await asyncio.sleep(min(poll_interval, max(0, deadline - asyncio.get_running_loop().time())))
                    await emit("Fresh Worker tasks inactive; verifying saved response")
                    for attempt in range(5):
                        _, retrieved = await self._http_request(
                            client, "GET", f"/api/v1/chats/{chat_id}", deadline=deadline,
                        )
                        try:
                            response = self._validate_saved(
                                retrieved, chat_id, model_id, prompt, user_id, assistant_id, system_prompt,
                            )
                            break
                        except _SavedPending:
                            if attempt == 4:
                                raise
                            await asyncio.sleep(min(0.5, max(0, deadline - asyncio.get_running_loop().time())))
                    generation_may_run = False
            except (asyncio.CancelledError, Exception) as exc:
                if isinstance(exc, TimeoutError):
                    exc = FreshWorkerError("timeout", "execution deadline exceeded")
                if chat_id:
                    if isinstance(exc, FreshWorkerError):
                        exc.chat_id = chat_id
                        exc.args = (f"{exc}; chat_id={chat_id}",)
                    else:
                        exc.add_note(f"Fresh Worker chat_id={chat_id}")
                if chat_id and generation_may_run:
                    cleanup_error = await self._cleanup(client, chat_id)
                    if cleanup_error:
                        exc.add_note(f"Best-effort stop failed: {cleanup_error}; chat_id={chat_id}")
                raise exc from None

        result = {"chat_id": chat_id, "response": response, "model": model_id,
                  "done": True, "evidence_path": None}
        try:
            if evidence_dir:
                try:
                    result["evidence_path"] = await asyncio.to_thread(
                        self._write_evidence, evidence_dir, chat_id, retrieved,
                    )
                except Exception as exc:
                    # File errors can contain server paths; return a stable diagnostic.
                    result["evidence_error"] = f"evidence_write: {type(exc).__name__}; chat_id={chat_id}"
            await emit("Fresh Worker complete" + ("; evidence write failed" if "evidence_error" in result else ""), done=True)
        except (asyncio.CancelledError, Exception) as exc:
            exc.add_note(f"Fresh Worker chat_id={chat_id}")
            raise
        return result
