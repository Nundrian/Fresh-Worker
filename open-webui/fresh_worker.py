"""Open WebUI Workspace Tool: Fresh Worker

title: Fresh Worker
author: Nundrian
git_url: https://github.com/Nundrian/Fresh-Worker
version: 0.1.0
description: Run one bounded prompt in a brand-new saved Open WebUI chat and return its completed response.
requirements: httpx
licence: MIT

Creates one saved chat, sends one prompt, polls until completion, validates the
saved result, and returns the assistant response.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        base_url: str = Field(
            default="",
            description="Open WebUI base URL reachable from the Open WebUI server",
        )
        api_key: str = Field(
            default="",
            description="Open WebUI API key",
            json_schema_extra={"input": {"type": "password"}},
        )
        worker_model: str = Field(
            default="",
            description="Exact Open WebUI model ID to use for the fresh worker",
        )
        wait_timeout: int = Field(
            default=600,
            description="Seconds to wait for task completion",
        )
        poll_interval: int = Field(
            default=2,
            description="Seconds between task polls",
        )
        evidence_dir: str = Field(
            default="",
            description="Optional directory in which to save retrieved worker-chat JSON",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.valves.api_key:
            headers["Authorization"] = f"Bearer {self.valves.api_key}"
        return headers

    def _base_url(self) -> str:
        return self.valves.base_url.strip().rstrip("/")

    def _chat_body(
        self,
        model_id: str,
        prompt: str,
        user_id: str,
        assistant_id: str,
    ) -> dict[str, Any]:
        timestamp = int(time.time())

        user_message: dict[str, Any] = {
            "id": user_id,
            "role": "user",
            "content": prompt,
            "timestamp": timestamp,
            "models": [model_id],
            "childrenIds": [assistant_id],
        }

        assistant_message: dict[str, Any] = {
            "id": assistant_id,
            "role": "assistant",
            "content": "",
            "parentId": user_id,
            "childrenIds": [],
            "model": model_id,
            "modelName": model_id,
            "modelIdx": 0,
            "done": False,
            "timestamp": timestamp + 1,
        }

        return {
            "chat": {
                "title": "Fresh Worker",
                "models": [model_id],
                "messages": [user_message, assistant_message],
                "history": {
                    "currentId": assistant_id,
                    "messages": {
                        user_id: user_message,
                        assistant_id: assistant_message,
                    },
                },
                "currentId": assistant_id,
            }
        }

    def _completion_body(
        self,
        chat_id: str,
        assistant_id: str,
        model_id: str,
        prompt: str,
        session_id: str,
    ) -> dict[str, Any]:
        return {
            "chat_id": chat_id,
            "id": assistant_id,
            "messages": [{"role": "user", "content": prompt}],
            "model": model_id,
            "stream": True,
            "session_id": session_id,
            "tools": [],
            "features": {
                "web_search": False,
                "code_interpreter": False,
                "image_generation": False,
                "memory": False,
            },
            "background_tasks": {
                "title_generation": False,
                "tags_generation": False,
                "follow_up_generation": False,
            },
        }

    def _parse_retrieved_chat(
        self,
        retrieved: dict[str, Any],
    ) -> dict[str, Any]:
        chat = retrieved.get("chat", {})
        history = chat.get("history", {})
        messages = history.get("messages", {})
        return {
            "chat": chat,
            "messages": messages,
        }

    async def _http_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> tuple[int, dict]:
        url = self._base_url() + path
        headers = self._build_headers()

        if body is not None:
            headers["Content-Type"] = "application/json"

        response = await client.request(
            method,
            url,
            content=json.dumps(body).encode("utf-8") if body else None,
            headers=headers,
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"{method} {path} returned non-JSON data (HTTP {response.status_code})"
            ) from exc

        return response.status_code, data

    async def fresh_worker(
        self,
        prompt: str,
        __event_emitter__: Optional[Any] = None,
    ) -> dict:
        """Run one bounded prompt in a new saved Open WebUI chat."""

        base_url = self._base_url()

        if not base_url:
            raise ValueError("base_url is not configured")

        if not self.valves.api_key:
            raise ValueError("api_key is not configured")

        model_id = self.valves.worker_model.strip()

        if not model_id:
            raise ValueError("worker_model is not configured")

        if not prompt or not prompt.strip():
            raise ValueError("prompt must not be empty")

        prompt = prompt.strip()
        wait_timeout = self.valves.wait_timeout
        poll_interval = self.valves.poll_interval

        if wait_timeout <= 0:
            raise ValueError("wait_timeout must be greater than zero")

        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")

        user_id = str(uuid.uuid4())
        assistant_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        async def emit(description: str, done: bool = False) -> None:
            if __event_emitter__ and callable(__event_emitter__):
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": description,
                            "done": done,
                        },
                    }
                )

        await emit("Validating Fresh Worker configuration ...")

        chat_body = self._chat_body(
            model_id,
            prompt,
            user_id,
            assistant_id,
        )

        async with httpx.AsyncClient(timeout=30) as client:
            status, created = await self._http_request(
                client,
                "POST",
                "/api/v1/chats/new",
                chat_body,
            )

            if not isinstance(created, dict):
                raise RuntimeError(
                    f"POST /api/v1/chats/new returned non-object (HTTP {status})"
                )

            chat_id = created.get("id")

            if not isinstance(chat_id, str) or not chat_id:
                raise RuntimeError(
                    f"POST /api/v1/chats/new: missing chat ID (HTTP {status})"
                )

            await emit(f"Fresh Worker chat created: {chat_id}")

            completion_body = self._completion_body(
                chat_id,
                assistant_id,
                model_id,
                prompt,
                session_id,
            )

            status, started = await self._http_request(
                client,
                "POST",
                "/api/chat/completions",
                completion_body,
            )

            if (
                not isinstance(started, dict)
                or started.get("status") is not True
                or started.get("chat_id") != chat_id
                or not isinstance(started.get("task_ids"), list)
            ):
                raise RuntimeError(
                    "POST /api/chat/completions: "
                    f"unexpected acceptance response (HTTP {status})"
                )

            await emit(
                f"Completion accepted; task_ids={started['task_ids']}"
            )

            deadline = asyncio.get_event_loop().time() + wait_timeout
            last_count = None

            while True:
                status, tasks = await self._http_request(
                    client,
                    "GET",
                    f"/api/tasks/chat/{chat_id}",
                )

                task_ids = (
                    tasks.get("task_ids")
                    if isinstance(tasks, dict)
                    else None
                )

                if not isinstance(task_ids, list):
                    raise RuntimeError(
                        f"GET /api/tasks/chat/{chat_id}: "
                        f"unexpected response (HTTP {status})"
                    )

                if len(task_ids) != last_count:
                    await emit(f"Poll: active tasks={len(task_ids)}")
                    last_count = len(task_ids)

                if not task_ids:
                    break

                if asyncio.get_event_loop().time() >= deadline:
                    raise RuntimeError(
                        "Server task did not complete within "
                        f"{wait_timeout} seconds; chat_id={chat_id}"
                    )

                await asyncio.sleep(poll_interval)

            await emit("Fresh Worker server task complete")

            status, retrieved = await self._http_request(
                client,
                "GET",
                f"/api/v1/chats/{chat_id}",
            )

            if not isinstance(retrieved, dict):
                raise RuntimeError(
                    f"GET /api/v1/chats/{chat_id}: "
                    f"retrieved chat is not an object (HTTP {status})"
                )

            parsed = self._parse_retrieved_chat(retrieved)
            messages = parsed["messages"]
            chat = parsed["chat"]

            saved_models = (
                chat.get("models")
                if isinstance(chat, dict)
                else None
            )

            if (
                retrieved.get("id") != chat_id
                or not isinstance(saved_models, list)
                or model_id not in saved_models
            ):
                raise RuntimeError(
                    "Retrieved chat ID or model list does not match"
                )

            saved_user = (
                messages.get(user_id)
                if isinstance(messages, dict)
                else None
            )

            if (
                not isinstance(saved_user, dict)
                or saved_user.get("content") != prompt
            ):
                raise RuntimeError("Saved user prompt does not match")

            saved_assistant = (
                messages.get(assistant_id)
                if isinstance(messages, dict)
                else None
            )

            if not isinstance(saved_assistant, dict):
                raise RuntimeError("Saved assistant message is missing")

            if saved_assistant.get("model") != model_id:
                raise RuntimeError(
                    "Saved assistant model mismatch: "
                    f"expected {model_id}, "
                    f"got {saved_assistant.get('model')}"
                )

            if saved_assistant.get("done") is not True:
                raise RuntimeError(
                    "Saved assistant done flag is not True: "
                    f"{saved_assistant.get('done')}"
                )

            response = saved_assistant.get("content", "")

        await emit("Fresh Worker complete", done=True)

        evidence_path: Optional[str] = None
        evidence_dir = self.valves.evidence_dir.strip()

        if evidence_dir:
            os.makedirs(evidence_dir, exist_ok=True)
            evidence_filename = f"chat-{chat_id}.json"
            evidence_path = os.path.join(
                evidence_dir,
                evidence_filename,
            )

            with open(evidence_path, "w", encoding="utf-8") as handle:
                json.dump(
                    retrieved,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

        return {
            "chat_id": chat_id,
            "response": response,
            "model": model_id,
            "done": True,
            "evidence_path": evidence_path,
        }
