"""Entry point do worker Celery."""

from services.api.atlas_api.tasks.indexing import celery_app


def main() -> None:
    celery_app.worker_main(["worker", "--loglevel=info", "-E"])


if __name__ == "__main__":
    main()
