# wsgi.py

import os
from decouple import Config,RepositoryEnv
from dotenv import load_dotenv
from app import create_app

# Determine which .env file to load based on FLASK_ENV
env_file = '.dev.env' if os.getenv('FLASK_ENV') == 'development' else '.env'
load_dotenv(env_file)

# Create a Config object with the appropriate .env file
config = Config(RepositoryEnv(env_file))

# Set the config in the environment
os.environ['DECOUPLE_CONFIG'] = env_file

print(f"Loaded {env_file}")

# Create the app
app = create_app()

if __name__ == '__main__':
    app.run()