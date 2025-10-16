from __future__ import annotations

import random

from locust import HttpUser, between, task


class AtlasUser(HttpUser):
    wait_time = between(1, 5)

    def __init__(self, environment) -> None:  # type: ignore[override]
        super().__init__(environment)
        self.doc_ids: list[str] = []

    def on_start(self) -> None:
        response = self.client.post("/auth/login", json={"email": "admin@acme.com", "password": "admin"})
        response.raise_for_status()
        token = response.json()["access"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

        try:
            search_response = self.client.get("/search", params={"q": "runbook"})
            if search_response.ok:
                payload = search_response.json()
                results = payload.get("results", []) if isinstance(payload, dict) else []
                self.doc_ids = [item.get("id") for item in results if isinstance(item, dict) and item.get("id")]
        except Exception:
            # Falhas na coleta inicial não devem derrubar o teste, apenas evitam chamadas /docs
            self.doc_ids = []

    @task(3)
    def search(self) -> None:
        self.client.get("/search", params={"q": "incidente"})

    @task(1)
    def get_document(self) -> None:
        if not self.doc_ids:
            return

        doc_id = random.choice(self.doc_ids)
        self.client.get(f"/docs/{doc_id}")
