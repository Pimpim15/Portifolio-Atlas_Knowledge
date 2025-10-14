from locust import HttpUser, between, task


class AtlasUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self) -> None:
        response = self.client.post("/auth/login", json={"email": "admin@acme.com", "password": "admin"})
        response.raise_for_status()
        token = response.json()["access"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(3)
    def search(self) -> None:
        self.client.get("/search", params={"q": "incidente"})

    @task(1)
    def get_document(self) -> None:
        self.client.get("/docs/doc-1")
