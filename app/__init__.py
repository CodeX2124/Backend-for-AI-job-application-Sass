# app/__init__.py

from flask import Flask
from celery import Celery
from decouple import config, Config, RepositoryEnv
from .extensions import login_manager, supabase, logger
from .models import User
from .routes import main_bp  # Ensure this import uses relative imports
from scrapingbee import ScrapingBeeClient
from openai import AzureOpenAI
import stripe
import os
from authlib.integrations.flask_client import OAuth
from urllib.parse import quote_plus, urlencode

# Get FLASK_ENV, default to 'development' if not set
environment = os.getenv('FLASK_ENV', 'development')

# Ensure only 'development' or 'production' is assigned
if environment not in ['development', 'production']:
    environment = 'development'

def create_app(environment=environment):
    app = Flask(__name__)

    # Get the directory one level up
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Determine the correct env file
    env_file = os.path.join(base_dir, '.dev.env' if environment == 'development' else '.env')
    
    # Load the environment variables
    config = Config(RepositoryEnv(env_file))
    app.config['SECRET_KEY'] = config('SECRET_KEY')
    # Load configurations from environment variables
    app.config['broker_url'] = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
    app.config['result_backend'] = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')


    # Initialize OAuth
    #init_oauth(app)

    # Initialize Azure OpenAI Clients
    llm_client = AzureOpenAI(
        api_key=config('AZURE_OPENAI_KEY'),
        api_version="2024-07-01-preview",
        azure_endpoint=config('AZURE_OPENAI_ENDPOINT')
    )
    app.llm_client = llm_client
    app.llm_model_name = config('AZURE_OPENAI_MODEL_NAME', default='cognibly-gpt4o-mini')
    
    embedding_client = AzureOpenAI(
        api_key=config('AZURE_OPENAI_TEXT_EMBEDDING_KEY'),
        api_version="2024-07-01-preview",
        azure_endpoint=config('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    )
    app.embedding_client = embedding_client
    app.text_embedding_model_name = config('AZURE_OPENAI_EMBEDDING_MODEL_NAME', default='text-embedding-3-small')

    # Initialize stripe env settings
    
    stripe.endpoint_secret = config('STRIPE_ENDPOINT_SECRET')

    if os.environ.get('FLASK_ENV') == 'development':
        stripe.api_key = config('STRIPE_TEST_SECRET_KEY')
        stripe.cognibly_subscription_price_id = config('STRIPE_SUBSCRIPTION_TEST_PRICE_ID')
        print("Using test Stripe key")
    else:
        stripe.api_key = config('STRIPE_SECRET_KEY') 
        stripe.cognibly_subscription_price_id = config('STRIPE_SUBSCRIPTION_PRICE_ID')
    app.stripe = stripe


    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message_category = 'info'

    # User Loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        # Ensure user_id is a string, not a dictionary
        if isinstance(user_id, dict):
            user_id = user_id.get('id')
        try:
            user = User.get(user_id)
            return user
        except Exception as e:
            print(f"Error loading user: {e}")
            return None


    # Import tasks to ensure they are registered with Celery
    from app import tasks  # Ensure tasks are loaded

    #Redirect Flask internal logs to our centralized logger
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)

    # Register blueprints after initializing extensions
    app.register_blueprint(main_bp)

    return app