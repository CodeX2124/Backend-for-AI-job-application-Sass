# app/celery_app.py

from celery import Celery, chain, group, chord
from decouple import config

def make_celery():
    celery = Celery(
        'app',
        broker=config('CELERY_BROKER_URL', default='redis://localhost:6379/0'),
        backend=config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
    )

    # Tell Celery to autodiscover tasks in the same module
    celery.autodiscover_tasks(['app.tasks'])
    celery.conf.task_routes = {
        'app.tasks.scrape_all_urls': {'queue': 'scraping_queue'},
        'app.tasks.scrape_text_from_page_task': {'queue': 'scraping_queue'},
        # Add other ScrapingBee-involved tasks as needed
    }
    celery.conf.worker_pool_args = {
        'scraping_queue': {'concurrency': 5}
    }
    celery.conf.task_default_retry_delay = 60  # seconds
    celery.conf.task_annotations = {
        '*': {'rate_limit': '10/s'}  # Adjust as needed for non-scraping tasks
    }
    celery.conf.beat_schedule = {
        # 'run-main-workflow-daily': {
        #     'task': 'app.tasks.main_workflow',
        #     'schedule': 86400.0,  # Every 24 hours
        # },
        'sync-subscriptions-hourly': {
        'task': 'sync_subscriptions',
        'schedule': 3600.0,  # Run every hour
        },
        'scrape_hiring_cafe':{
        'task': 'scrape_hiring_cafe',
        'schedule': 1440.0, # Run every 4 hours
        },
        'process-job-fits-every-hour': {
        'task': 'process_all_users_job_preferences',
        'schedule': 3600.0,  # Every hour
        },
        'remove-duplicate-embeddings': {
        'task': 'remove_duplicate_embeddings',
        'schedule': 1800.0,  # Run every half hour
        },
        'remove_duplicate_jobs': {
        'task': 'remove_duplicate_jobs',
        'schedule': 1800.0,  # Run every half hour
        }
    }
    celery.conf.timezone = 'UTC'

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            from app import create_app
            app = create_app()
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery()