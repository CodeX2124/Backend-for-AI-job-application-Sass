# app/extensions.py
from flask import Flask
from flask_login import LoginManager
from supabase import create_client, Client
from supabase.client import ClientOptions
from decouple import config, Config, RepositoryEnv
from scrapingbee import ScrapingBeeClient
from openai import AzureOpenAI
import os
import logging
from logging.handlers import RotatingFileHandler
from authlib.integrations.flask_client import OAuth
import stripe

# Get FLASK_ENV, default to 'development' if not set
environment = os.getenv('FLASK_ENV', 'development')

# Ensure only 'development' or 'production' is assigned
if environment not in ['development', 'production']:
    environment = 'development'

# Get the directory one level up
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
# Determine the correct env file
env_file = os.path.join(base_dir, '.dev.env' if environment == 'development' else '.env')
    
# Load the environment variables
config = Config(RepositoryEnv(env_file))

#Flask Login
login_manager = LoginManager()

oauth = OAuth()

# Initialize OAuth
def init_oauth(app: Flask):
    global oauth
    oauth.init_app(app)
    oauth.register(
        "auth0",
        client_id=config("AUTH0_CLIENT_ID"),
        client_secret=config("AUTH0_CLIENT_SECRET"),
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f'https://{config("AUTH0_DOMAIN")}/.well-known/openid-configuration'
    )    

# Initialize Supabase
supabase_url = config('SUPABASE_URL')
supabase_key = config('SUPABASE_KEY')
supabase = create_client(
    supabase_url, 
    supabase_key,
    options=ClientOptions(
    postgrest_client_timeout=10,
    storage_client_timeout=10
  ))

# Initialize Scraping Bee
scrapingbee_api_key = config('SCRAPINGBEE_API_KEY')
scraping_bee_client = ScrapingBeeClient(api_key=scrapingbee_api_key)

client_id = config("AZURE_CLIENT_ID")
tenant_id = config("AZURE_TENANT_ID")
api_key = config("AZURE_OPENAI_API_KEY_COVER_LETTER")
client_secret = config("AZURE_CLIENT_SECRET")
azure_endpoint = config("AZURE_OPENAI_ENDPOINT_COVER_LETTER")


# Check for missing variables
if not all([api_key, azure_endpoint]):
    raise EnvironmentError("Ensure AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT_COVER_LETTER are set.")

# Initialize AzureOpenAI client with API Key
llm_client = AzureOpenAI(
    api_key=api_key,
    azure_endpoint=azure_endpoint,
    api_version="2024-05-01-preview"
)
llm_model_name = config('AZURE_OPENAI_MODEL_NAME', default='cognibly-gpt4o-mini')

print(llm_client)
# Initialize Azure OpenAI Service Embedding Model
embedding_client = AzureOpenAI(
        api_key=config('AZURE_OPENAI_TEXT_EMBEDDING_KEY'),
        api_version="2024-07-01-preview",
        azure_endpoint=config('AZURE_OPENAI_EMBEDDING_ENDPOINT')
    )

text_embedding_model_name = config('AZURE_OPENAI_EMBEDDING_MODEL_NAME', default='text-embedding-3-small')


#Initialize Logger
logger = logging.getLogger('cognibly_app')  # Use a specific logger name for your app
logger.setLevel(logging.DEBUG)  # Set the default logging level

# Prevent duplicate handlers if the logger is already configured
if not logger.handlers:
    # Create console handler with a higher log level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Set console handler level

    # Create file handler which logs debug and higher level messages
    log_file = os.getenv("LOG_FILE", "app.log")  # You can set LOG_FILE via environment variables
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Set file handler level

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
