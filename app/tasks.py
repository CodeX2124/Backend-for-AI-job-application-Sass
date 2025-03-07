# app/tasks.py

import os
import asyncio
import ast
import re
import json
from bs4 import BeautifulSoup
import urllib.parse
import secrets
import string
import random
from decouple import config
from typing import List
from supabase import Client
from openai import AzureOpenAI
from .extensions import logger, supabase, scraping_bee_client, llm_client, llm_model_name, embedding_client, text_embedding_model_name
from .jobmatcher import embed_user_preferences, calculate_user_job_fit,calculate_all_job_fits
from .generate_query import generate_job_keywords #, generate_urls
from .celery_app import celery, chain, group, chord
from .models import User
from datetime import datetime, timedelta, timezone
from scipy.spatial.distance import cosine
import numpy as np
import stripe
import requests

llm_model_name = "gpt-4o-mini"
SCRAPINGBEE_API_KEY = config('SCRAPINGBEE_API_KEY')



def initialize_stripe():
    stripe.endpoint_secret = config('STRIPE_ENDPOINT_SECRET')
    print(f"FLASK_ENV value: {os.environ.get('FLASK_ENV')}")
    if os.environ.get('FLASK_ENV') == 'development':
        stripe.api_key = config('STRIPE_TEST_SECRET_KEY')
        stripe.cognibly_subscription_price_id = config('STRIPE_SUBSCRIPTION_TEST_PRICE_ID')
        print("Using test Stripe key")
    else:
        stripe.api_key = config('STRIPE_SECRET_KEY') 
        stripe.cognibly_subscription_price_id = config('STRIPE_SUBSCRIPTION_PRICE_ID')
    return stripe

# Initialize stripe at module level
stripe = initialize_stripe()
if stripe:
    print(f"Initialized Stripe in Celery with API Key {stripe.api_key}")

@celery.task(name='sync_subscriptions')
def sync_subscriptions():
    logger.info("Starting subscription sync")
    try:
        response = supabase.table('profiles').select('id', 'subscription_id').not_.is_('subscription_id', 'null').execute()
        users = response.data

        for user in users:
            try:
                subscription = stripe.Subscription.retrieve(user['subscription_id'])
                
                # Retrieve upcoming invoice to get next payment amount and date
                upcoming_invoice = stripe.Invoice.upcoming(
                    customer=subscription.customer,
                    subscription=subscription.id
                )
                
                next_payment_amount = upcoming_invoice.amount_due / 100  # Convert from cents to dollars
                next_payment_date = upcoming_invoice.next_payment_attempt  # Unix timestamp

                # Convert Unix timestamp to datetime
                next_payment_date = datetime.fromtimestamp(next_payment_date).strftime('%Y-%m-%d %H:%M:%S')

                supabase.table('profiles').update({
                    'subscription_status': subscription.status,
                    'is_subscribed': subscription.status in ['active', 'trialing'],
                    'next_payment_amount': next_payment_amount,
                    'next_payment_date': next_payment_date
                }).eq('id', user['id']).execute()
                
                logger.debug(f"Updated subscription for user {user['id']}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error for user {user['id']}: {str(e)}")
            except Exception as e:
                logger.exception(f"Unexpected error for user {user['id']}: {str(e)}")
    except Exception as e:
        logger.exception(f"Error fetching users: {str(e)}")
    logger.info("Subscription sync completed")

# to be deleted    
# @celery.task(bind=True, max_retries=3)
# def scrape_job_board_urls(self, urls, user_id=None):
#     try:
#         if not urls:
#             logger.info(f"No URLs to scrape for user {user_id}.")
#             return []
#         # Create a chord
#         return chord(
#             header=[scrape_all_urls.s(url) for url in urls],
#             body=combine_scrape_results.si()  # combine_scrape_results is the callback - .si() used to ignore parent user_id argument
#         )
#     except Exception as e:
#         logger.error(f"Error in scrape_job_board_urls for user {user_id}: {e}")
#         raise self.retry(exc=e)
    
@celery.task(bind=True, max_retries=3)
def combine_scrape_results(results):
    # Combine all lists of URLs into a single list
    combined_links = []
    for result in results:
        combined_links.extend(result)
    logger.info(f"Combined {len(combined_links)} scraped URLs.")
    return combined_links

# #Takes in a list of job board search result URLs to scrape for job post URLs
# @celery.task(bind=True, max_retries=3, queue='scraping_queue')
# def scrape_links_from_job_board_result_pages(self, search_urls_set):
#     #just some simple input validation
#     if not isinstance(search_urls_set,list) or not search_urls_set: ``
#         logger.warning("Invalid or empty 'search_urls_set' passed to 'scrape_links_from_job_board_result_pages'.")
#         return []  # Return an empty list as default value
#     try:
#         extract_rules = {
#             "all_links": {
#                 "selector": "a",
#                 "type": "list",
#                 "output": {
#                     "anchor": {"selector": "a", "output": "text"},
#                     "href": {"selector": "a", "output": "@href"}
#                 }
#             }
#         }
#         list_of_job_post_urls = []

#         for search_result_url in search_urls_set:
#             response = scraping_bee_client.get(
#                 search_result_url,
#                 params={
#                     'extract_rules': extract_rules,
#                     'render_js': True,
#                     'wait': 1000
#                 }
#             )

#             if response.status_code == 200:
#                 data = response.json()
#                 all_links = data.get('all_links', [])
#                 urls = [link['href'] for link in all_links if 'href' in link]
#                 logger.info(f"Successfully scraped {len(urls)} URLs from {search_result_url}")
#                 list_of_job_post_urls.append(urls)
#             else:
#                 logger.warning(f"Failed to scrape {search_result_url}. Status code: {response.status_code}")
#                 pass
#         return list_of_job_post_urls
#     except Exception as e:
#         logger.error(f"Error scraping {search_result_url}: {e}")
#         raise self.retry(exc=e)

# This function is a candidate for deletion and is not in use.
# #Celery Task to invoke extract_job_post_urls for the list of urls provided.
# #This is designed to return as a chord since it is invoked as part of a workflow that has multiple URL lists
# @celery.task(bind=True, max_retries=3)
# def extract_job_urls(self, urls_as_user_prompt):
#     try:
#         if not urls_as_user_prompt:
#             logger.info("No URLs to process for extracting job post URLs.")
#             return []

#         # Ensure urls_as_user_prompt is a list
#         if not isinstance(urls_as_user_prompt, list):
#             logger.error("urls_as_user_prompt is not a list.")
#             return []

#         return chord(
#             header=[extract_job_post_urls.s(url) for url in urls_as_user_prompt],
#             body=combine_extracted_urls.s()
#         )
#     except Exception as e:
#         logger.error(f"Error in extract_job_urls: {e}")
#         raise self.retry(exc=e)

#Takes in a list of URLs and uses LLM to determine which URLs actually link to job postings.
@celery.task(bind=True, max_retries=3)
def filter_job_post_urls(self, list_of_urls_scraped_from_job_board_search_result_pages):
    if not isinstance(list_of_urls_scraped_from_job_board_search_result_pages, list) or not list_of_urls_scraped_from_job_board_search_result_pages:
        logger.warning("Invalid or empty 'list_of_urls_scraped_from_job_board_search_result_pages' passed to 'filter_job_post_urls'.")
        return []  # Return an empty list as default value
    filtered_list_of_job_post_urls = []
    system_prompt = """
    Your task is to return a JSON array of strings representing links to job listings from the provided content.
    If the provided href URLs are relative, reconstruct the absolute URL based on the job board's base URL.
    Include only links that are actually for job posts. These typically have job titles as anchor text.
    Exclude unrelated links such as navigation to other parts of the website.

    Output format: Must be a valid JSON array of strings.  Do not include any markdown or backticks.
    ["url1", "url2", "url3"] 
    """

    for url in list_of_urls_scraped_from_job_board_search_result_pages:
        try:
            response = llm_client.chat.completions.create(
                model=llm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": str(url)}
                ],
                temperature=0.2,
                max_tokens=9999,
                n=1,
                stop=None
            )
            content = response.choices[0].message.content.strip()

            # Remove backticks and extra whitespace
            content = content.replace("```json", "").replace("```", "").strip()

            logger.debug(f"Cleaned LLM output from filter_job_post_urls() iteration: {content}") # Log the cleaned content

            try:
                url_list = json.loads(content)

                if isinstance(url_list, list) and all(isinstance(item, str) for item in url_list):
                    logger.info(f"Job Post URLS discovered and added: {url_list}")
                    filtered_list_of_job_post_urls.extend(url_list)
                else:
                    logger.error(f"Invalid data type from LLM: {type(url_list)}. Expected a list of strings. Skipping.")

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON output from LLM (even after cleaning): {content}. Skipping.")


        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            continue

    return filtered_list_of_job_post_urls
    
@celery.task(bind=True, max_retries=3)
def combine_extracted_urls(self, results):
    try:
        combined_urls = []
        for url_list in results:
            combined_urls.extend(url_list)  # Flatten the list of lists
        return combined_urls
    except Exception as e:
        logger.error(f"Error in combine_extracted_urls: {e}")
        raise self.retry(exc=e)

# #This cross-checks our list with existing job urls in our database and remove any duplicates already collected in the DB.
# @celery.task(bind=True, max_retries=3, name='remove_duplicate_jobs')
# def remove_duplicate_jobs(self, scraped_jobs_list): # Removed user_id parameter
#     if not isinstance(scraped_jobs_list, list) or not scraped_jobs_list:
#         logger.warning("Invalid or empty 'scraped_jobs_list' passed to 'remove_duplicate_jobs'.")
#         return []  # Return an empty list as default value
#     try:
#         # Select all posting_urls from the job_postings table
#         response = supabase.table('job_postings').select('posting_url').execute()
#         existing_urls = set(item['posting_url'] for item in response.data) if response.data else set()

#         new_jobs_list = [url for url in scraped_jobs_list if url not in existing_urls]

#         logger.info(f"Removed {len(scraped_jobs_list) - len(new_jobs_list)} duplicate URLs.") # Removed user_id specific logging
#         return new_jobs_list
#     except Exception as e:
#         logger.error(f"Error in remove_duplicate_jobs: {e}") # Removed user_id specific logging
#         raise self.retry(exc=e)


@celery.task(bind=True, max_retries=3, queue='scraping_queue')
def scrape_text_from_page_task(self, url):
    try:
        text = scrape_text_from_page(url)
        return text
    except Exception as exc:
        logger.error(f"Error in scrape_text_from_page_task for {url}: {exc}")
        raise self.retry(exc=exc)

@celery.task(bind=True, max_retries=3, queue='scraping_queue')
def scrape_text_from_page(self,url):
    # Input validation
    if not isinstance(url, str) or not url.startswith('http'):
        raise Exception(f"Invalid 'url' passed to 'scrape_text_from_page': {url}")
        #stop this chain to prevent flow of bad data
        #return None  # Return None as default value
    logger.info(f"Attempting to scrape page {url}")
    try:
        response = scraping_bee_client.get(
            url,
            params={
                'extract_rules': {"text": "body"},
                'render_js': True,
                'wait': 1000
            }
        )
        if response.status_code == 200:
            data = response.json()
            text_content = data.get('text')
            logger.info(f"Scraped text from {url}: {text_content[:100]}")
            return text_content
        else:
            logger.warning(f"Failed to scrape {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None
    return scraped_page_text

@celery.task(bind=True, max_retries=100)
def filter_details_from_job_page_texts(self,page_text,user_id=None):
    if page_text is None: return {}
    if not isinstance(page_text, str) or not page_text.strip():
        raise Exception ("Invalid or empty 'page_text' passed to 'filter_details_from_job_page_texts'.")
        #stop this chain to prevent flow of bad data
        #return {}  # Return an empty dictionary as default value
    system_prompt = """
    The user will upload text extracted from a job posting webpage. Based on the text content detail, return a JSON output with values for the following fields: 
    "Job Title","Company","Location","Remote(Yes/No/Hybrid/Unknown)","Date Posted","Job Description","Job Type","Salary Range".  
    If you cannot determine the value for a field, use the value "Unknown". 

    Example output:
    {
        "Job Title": "Director, Enterprise Applications",
        "Company": "Lone Star College System",
        "Location":"The Woodlands, TX",
        "Remote(Yes/No/Hybrid/Unknown)":"No",
        "Date Posted":"7/26/2024",
        "Job Description":"The Director, Enterprise Applications is an integral part...",
        "Job Type":"Full-time",
        "Salary Range":"$114,241 - $131,377"
    }
    """
    try:
        response = llm_client.chat.completions.create(
            model=llm_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": page_text}
            ],
            temperature=0.33,
            max_tokens=9999,
            n=1,
            stop=None
        )
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        logger.debug(f"Cleaned LLM output from filter_job_post_urls() iteration: {content}") # Log the cleaned content
        #Log the raw content for debugging
        #logger.debug(f"Raw LLM output from filter_details_from_job_page_texts() iteration: {content}")

        try:
            job_details = json.loads(content)
            return job_details
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in filter_details_from_job_pages() iteration: {e}. Continuing...")
            # Instead of returning {}, raise the exception to stop the chain
    except Exception as e:
        logger.error(f"Error in filter_details_from_job_page_texts() iteration: {e}")
        # Consider to re-raise the exception to halt the chain


# to be deleted    
# @celery.task(bind=True, max_retries=3)
# def extract_job_post_details_task(self, page_text):
#     try:
#         details = extract_job_post_details(page_text)
#         return details
#     except Exception as exc:
#         logger.error(f"Error in extract_job_post_details_task: {exc}")
#         raise self.retry(exc=exc)

@celery.task(bind=True, max_retries=3)
def generate_embedding(self, details):
    if not isinstance(details, dict) or not details:
        raise Exception("Invalid or empty 'details' passed to 'generate_embedding'.")
    try:
        response = embedding_client.embeddings.create(
            input=str(details),
            model=text_embedding_model_name,
            dimensions=512
        )
        details['Embedding'] = response.data[0].embedding

        return details
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise self.retry(exc=e)

@celery.task(bind=True, max_retries=3)
def save_job_to_database_and_process_diffs(self, job_details, url):
    if not isinstance(job_details, dict) or not job_details:
        logger.warning("Invalid or empty 'job_details' passed to 'save_job_to_database'.")
        return  # Return None to indicate the task did not process
    # Robust Date Posted check and handling
    date_posted_str = job_details.get("Date Posted", "")
    date_posted = None  # Initialize to None

    # Date format check using regular expression
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"  # YYYY-MM-DD format
    if re.match(date_pattern, date_posted_str):
        try:
            date_posted = datetime.strptime(date_posted_str, "%Y-%m-%d").date()
            date_posted = date_posted.isoformat()
        except ValueError:
            logger.warning(f"Invalid date format: {date_posted_str}. Setting to NULL.")

    elif date_posted_str.lower().find("unknown") != -1: # Handle "unknown" and set to NULL
        logger.warning(f"Date Posted is 'unknown'. Setting to NULL.")

    else: # Handle any other non-compliant value and set to NULL
        logger.warning(f"Non-compliant Date Posted value: {date_posted_str}. Setting to NULL.")
    try:
        # Ensure 'posting_url' exists in job_details
        supabase.table('job_postings').insert({
            'job_title': job_details.get("Job Title", "Unknown"),
            'company': job_details.get("Company", "Unknown"),
            'location': job_details.get("Location", "Unknown"),
            'remote': job_details.get("Remote(Yes/No/Hybrid/Unknown)", "Unknown"),
            'date_posted': date_posted,
            'job_description': job_details.get("Job Description", "Unknown"),
            'job_type': job_details.get("Job Type", "Unknown"),
            'salary_range': job_details.get("Salary Range", "Unknown"),
            'embedding': job_details.get("Embedding", ""),
            'posting_url': url
        }).execute()
        print("Successfully added job to DB.")
        logger.info(f"Saved job: {job_details.get('Job Title', 'Unknown')}")
    except Exception as e:
        logger.error(f"Error saving job to database: {e}")
        raise self.retry(exc=e)
    #Now the job is saved to the database and we can calculate the diffs for each user.
    try:
        embedding = job_details.get("Embedding")
        try:
            job_posting_id = get_job_posting_id(url)
        except Exception as e:
            print(f"Error in retrieving id from table job_postings for {url}: {e}")
        if embedding and job_posting_id:
            check_job_fit(job_posting_id,embedding)
        else:
            raise Exception (f"Unable to Check Job Fit for {url} since embedding or job_posting_id not found") #Abort the chain to prevent flow of bad data.
    except Exception as e:
        print(f"Error in generating embeddings for {job_posting_id}: {e}")
        

def get_job_posting_id(url):
    try:
        response = supabase.table('job_postings').select('id').eq('posting_url', url).execute()
        if response.data:
            job_posting_id = response.data[0]['id']
            logger.info(f"Found id from job_postings: {job_posting_id} for URL: {url}")
            return job_posting_id
        else:
            logger.warning(f"No job_postings id found for URL: {url}")
            return None  # Or raise an exception if appropriate
    except Exception as e:
        logger.error(f"Error getting job_postings id for URL {url}: {e}")
        return None # Or raise an exception
    
def get_job_embedding_by_url(url):
    try:
        response = supabase.table('job_postings').select('embedding').eq('posting_url', url).execute()
        if response.data and response.data[0]['embedding']: #check for null embeddings
            embedding_str = response.data[0]['embedding']
            try:
                embedding = ast.literal_eval(embedding_str) # Safely evaluate the string as a list
                logger.info(f"Found embedding from job_postings: {embedding} for URL: {url}")
                return embedding
            except (SyntaxError, ValueError) as e:
                logger.error(f"Error converting embedding string to list: {e}, String: {embedding_str}")
                return None # Or handle error differently
        else:
            logger.warning(f"No job_postings embedding found for URL: {url}")
            return None
    except Exception as e:
        logger.error(f"Error getting job_postings embedding for URL {url}: {e}")
        return None
    
def get_job_embedding_by_id(id): # Same fix for get_job_embedding_by_id
    try:
        response = supabase.table('job_postings').select('embedding').eq('id', id).execute()
        if response.data and response.data[0]['embedding']:
            embedding_str = response.data[0]['embedding']
            try:
                embedding = ast.literal_eval(embedding_str)
                logger.info(f"Found embedding from job_postings: {embedding} for id: {id}")
                return embedding
            except (SyntaxError, ValueError) as e:
                logger.error(f"Error converting embedding string to list: {e}, String: {embedding_str}")
                return None
        else:
            logger.warning(f"No job_postings embedding found for id: {id}")
            return None
    except Exception as e:
        logger.error(f"Error getting job_postings embedding for id {id}: {e}")
        return None



def get_user_preference_embeddings():
    try:
        response = supabase.table('user_job_preferences').select('id, embedding512').execute()
        if response.data:
            embeddings = {}
            for row in response.data:
                try:
                    embedding512 = ast.literal_eval(row['embedding512']) # Convert to list
                    embeddings[row['id']] = embedding512
                except (SyntaxError, ValueError) as e:
                    logger.error(f"Error converting embedding512 string to list: {e}, String: {row['embedding512']}, ID: {row['id']}")
                    embeddings[row['id']] = None # Or handle the error differently (e.g., skip)
            logger.info(f"Retrieved embeddings for {len(embeddings)} user preferences.")
            return embeddings
        else:
            logger.warning("No entries found in user_job_preferences.")
            return {}
    except Exception as e:
        logger.error(f"Error retrieving user preference embeddings: {e}")
        return None

def check_job_fit(job_posting_id,job_embedding):
#recursively checks the job's fit for all entries in user_job_preferences
    user_job_preference_embeddings_dict = get_user_preference_embeddings()
    if user_job_preference_embeddings_dict is None: #Handle the error case
        logger.error("Error retrieving user preference embeddings. Exiting check_job_fit.")
        return

    if not user_job_preference_embeddings_dict:  # Handle empty dictionary case
        logger.warning("No user preferences found. Exiting check_job_fit.")
        return
    try:
        print(f"job_embedding type: {type(job_embedding)}, content: {job_embedding}")

        if user_job_preference_embeddings_dict:
            for id,embedding512 in user_job_preference_embeddings_dict.items():
                if embedding512 is not None:
                    print(f"embedding512 type: {type(embedding512)}, content: {embedding512}")
                    fit_score_512 = cosine(job_embedding,embedding512) #compare the job embedding and user prefs embedding
                    supabase.table('user_job_fit').insert({
                    'user_job_preferences_id': id,
                    'job_postings_id': job_posting_id,
                    'fit_score_512': fit_score_512
                    }).execute()

                else:
                    logger.warning(f"Embedding for user preference {id} is None. Skipping fit calculation.")
    except ValueError as e: #Catch and log ValueError from cosine function
        logger.error(f"ValueError in cosine calculation: {e}")
        # Add more specific error handling if needed (e.g., check dimensions)
    except Exception as e:  # Catch other potential errors during insert
        logger.error(f"Error inserting job fit data: {e}")


@celery.task(bind=True, max_retries=3)
def process_job_posts(self, job_post_urls, user_id):
    if not isinstance(job_post_urls, list) or not job_post_urls:
        logger.warning(f"Invalid or empty 'job_post_urls' passed to 'process_job_posts' for user {user_id}.")
        return  # Return None to indicate no processing to be done

    logger.info(f"Processing {len(job_post_urls)} job post URLs for user {user_id}")

    try:
        # Use a list comprehension to create the chain for each URL
        job_post_chains = [
            chain(
                scrape_text_from_page.s(url),  
                filter_details_from_job_page_texts.s(),
                generate_embedding.s(),
                save_job_to_database_and_process_diffs.s(url)
            ) for url in job_post_urls
        ]

        # Execute the group of chains
        group(job_post_chains).apply_async()

    except Exception as e:
        logger.error(f"Error in process_job_posts: {e}")
        raise self.retry(exc=e)
    
@celery.task(bind=True, max_retries=3, name='update_all_jobs')
def update_all_jobs(self):
    try:
        # Fetch all user IDs from the user_job_preferences table
        response = supabase.table('user_job_preferences').select('user_id').execute()
        if not response.data:
            logger.info("No users found in user_job_preferences.")
            print("No users found in user_job_preferences.")
            return

        user_ids = [row['user_id'] for row in response.data]

        # Get the current time (UTC)
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)

        for user_id in user_ids:
            # Fetch the last_login for each user from the profiles table
            user_response = supabase.table('profiles').select('last_login').eq('id', user_id).execute()

            # If the user has a last_login
            if user_response.data:
                last_login_str = user_response.data[0].get('last_login')
                if last_login_str:
                    # Convert last_login to a datetime object
                    last_login_time = datetime.strptime(last_login_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                    print(f"User's last login time: {last_login_time}")
                    # Check if the last login is more than 7 days ago
                    if current_time - last_login_time < timedelta(days=7):
                        # Trigger the request for the user if they have been inactive for more than 7 days
                        uuid = user_id
                        response = requests.get(f'https://cognibly-n8n-hmasbrgge7gkdtew.southcentralus-01.azurewebsites.net/webhook/808ebdcf-1aea-4c4f-a640-0d2d9aec3e44?uuid={uuid}')
                        logger.info(f"Triggered job update for user {user_id}.")
                        print(f"Triggered job update for user {user_id}.")
                    else:
                        logger.info(f"User {user_id} inactive in more than 7 days. Skipping job update.")
                        print(f"User {user_id}. Skipping job update.")
                else:
                    logger.warning(f"User {user_id} has no last_login field.")
                    print(f"User {user_id} has no last_login field.")
            else:
                logger.warning(f"User {user_id} not found in profiles table.")
                print(f"User {user_id} not found in profiles table.")

    except Exception as e:
        logger.error(f"Error in update_all_jobs: {e}")
        print(f"Error in update_all_jobs: {e}")
        raise self.retry(exc=e)


# @celery.task(bind=True, max_retries=3)
# def main_workflow(self, user_id=None):
#     if user_id is not None: #code for single user
#         try:
#             # Chain tasks for the given user, including extract_job_urls and remove_duplicate_jobs
#             user_chain = chain(
#                 get_job_board_urls.s(user_id), #get search_urls JSON
#                 scrape_links_from_job_board_result_pages.s(), #iterate through the list of search result pages to scrape a bigger list of job page urls 
#                 filter_job_post_urls.s(),
#                 remove_duplicate_jobs.s(),
#                 process_job_posts.s(user_id=user_id)
#             )
#             user_chain.apply_async()
#         except Exception as e:
#             logger.error(f"Error in main_workflow for user {user_id}: {e}")
#             raise self.retry(exc=e)
#     else: #code for all users
#         try:
#             # Fetch all user IDs from the user_job_preferences table
#             response = supabase.table('user_job_preferences').select('user_id').execute()
#             if not response.data:
#                 logger.info("No users found in user_job_preferences.")
#                 return

#             user_ids = [row['user_id'] for row in response.data]
#             for user_id in user_ids: #for each user:
#                 # Chain tasks for each user
#                 user_chain = chain(
#                 get_job_board_urls.s(user_id), #get search_urls JSON
#                 scrape_links_from_job_board_result_pages.s(), #iterate through the list of search result pages to scrape a bigger list of job page urls 
#                 filter_job_post_urls.s(),
#                 remove_duplicate_jobs.s(),
#                 process_job_posts.s(user_id=user_id)
#                 )
#                 user_chain.apply_async()
#         except Exception as e:
#             logger.error(f"Error in main_workflow: {e}")
#             raise self.retry(exc=e)

@celery.task
def process_job_preferences(user_id):
    try:
        # Fetch the last login date for the user from the profiles table
        profile_response = supabase.table('profiles').select('last_login').eq('id', user_id).execute()
        
        if not profile_response.data:
            logger.error(f"No profile found for user {user_id}")
            return
        
        last_login = profile_response.data[0].get('last_login')
        
        # Assuming 'last_login' is a string in ISO format with timezone
        if last_login:
            # Convert the last_login to a datetime with timezone
            last_login_date = datetime.strptime(last_login, '%Y-%m-%dT%H:%M:%S.%f%z')
            
            # Get the current UTC time with timezone information
            current_time = datetime.utcnow().replace(tzinfo=timezone.utc)

            # Log the values of the dates
            logger.info(f"Last login date: {last_login_date}")
            logger.info(f"Current time (UTC): {current_time}")
            
            # Check if the last login is within the last 7 days
            if last_login_date > current_time - timedelta(days=7):
                logger.info(f"User {user_id} has logged in within the last 7 days. Proceeding with processing.")
                print(f"User {user_id} has logged in within the last 7 days. Proceeding with processing.")
            else:
                logger.info(f"User {user_id} has not logged in within the last 7 days. Skipping processing.")
                print(f"User {user_id} has not logged in within the last 7 days. Skipping processing.")
                
        else:
            logger.error(f"Invalid or missing last login for user {user_id}")
            return
            
        # Fetch user preferences
        response = supabase.table('user_job_preferences').select('*').eq('user_id', user_id).execute()
        if not response.data:
            logger.error(f"No job preferences found for user {user_id}")
            return
        
        preferences = response.data[0]
        values = {
            'user_id': user_id,
            'ideal_work_situation': preferences['ideal_work_situation'],
            'preferred_industries': preferences['preferred_industries'],
            'preferred_roles_responsibilities': preferences['preferred_roles_responsibilities'],
            'work_arrangement_preference': preferences['work_arrangement_preference'],
            'current_city': preferences['current_city'],
            'current_state': preferences['current_state'],
            'willing_to_relocate': preferences['willing_to_relocate'],
            'relocation_preference': preferences.get('relocation_preference'),
            'preferred_locations': preferences['preferred_locations'],
            'expected_salary_range': preferences['expected_salary_range']}
        
        # Generate keywords based on subscription status
        is_subscribed = preferences.get('is_subscribed', False)
        if not is_subscribed:
            keywords = generate_job_keywords(values, maximum_keywords=5)
        else:
            keywords = generate_job_keywords(values, maximum_keywords=25)
        
        logger.info(f"Keywords Generated for user {user_id}: {keywords}")
        
        if not keywords:
            logger.error(f"No keywords generated for user {user_id}")
            return
        
        # Update Supabase with keywords
        supabase.table('user_job_preferences').update({
            "keywords": keywords
        }).eq('user_id', user_id).execute()
        
        # Generate search URLs
        preferred_locations = values.get('preferred_locations', [])
        try:
            preferred_locations = json.loads(preferred_locations)
        except:
            print("Unable to convert preferred locations into a list.")
        if preferred_locations:
            salary_range = preferences['expected_salary_range']
            if isinstance(salary_range, list) and len(salary_range) == 2:
                min_salary_value = salary_range[0]  # or calculate an average
            else:
                min_salary_value = float(salary_range)  # If it's a single value

            print(f"Salary Range Type: {type(salary_range)}")
            print(f"Salary Range Value: {salary_range}")
            print(f"Min Salary Value: {min_salary_value}")
            min_salary = min_salary_value * 0.66
            max_salary = min_salary_value * 2.5
            # maximum_urls = 25 if is_subscribed else 5
            # search_urls = generate_urls(
            #     keywords=keywords,
            #     preferred_locations=preferred_locations,
            #     remote_work_type=values['work_arrangement_preference'],
            #     min_salary=min_salary,
            #     max_salary=max_salary,
            #     from_age=7,
            #     maximum_urls=maximum_urls
            # )
            
        
        # Generate new embedding and update job matches
        embed_user_preferences(user_id, 512)
        
        # Get recent jobs (last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        jobs_response = supabase.table('job_postings')\
            .select('id')\
            .gte('created_at', thirty_days_ago.isoformat())\
            .execute()
        
        jobs = jobs_response.data
        
        if jobs:
            # Delete existing fit scores
            supabase.table('user_job_fit')\
                .delete()\
                .eq('user_job_preferences_id', preferences['id'])\
                .execute()
            
            # # Calculate new fit scores
            # for job in jobs:
            #     calculate_user_job_fit(preferences['id'], job['id'], 512)
        
        fit_scores = calculate_all_job_fits(preferences['id'],dimensionality=512)
        if fit_scores is None:
            return {"error":"Failed to calculate job fits"},500
        else:
            return {"message":f"Calculate fit scores for user {user_id}"},200

        logger.info(f"Job preferences processed successfully for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error processing job preferences for user {user_id}: {str(e)}", exc_info=True)

@celery.task(bind=True, max_retries=3, name='process_all_users_job_preferences')
def process_all_users_job_preferences(self):
    """
    Celery task to process job preferences for all users.
    Iterates through all user_ids in the user_job_preferences table
    and dispatches a separate task for each user to process their preferences.
    """
    try:
        logger.info("Starting process_all_users_job_preferences task.")

        # Fetch all unique user_ids from the user_job_preferences table
        response = supabase.table('user_job_preferences').select('user_id').execute()

        if not response.data:
            logger.info("No users found in user_job_preferences table.")
            return "No users to process."

        # Extract unique user_ids
        user_ids = {row['user_id'] for row in response.data}
        logger.info(f"Found {len(user_ids)} unique users to process.")

        if not user_ids:
            logger.info("No valid user_ids found to process.")
            return "No valid user_ids to process."

        # Create a group of process_job_preferences tasks
        job_preference_tasks = [process_job_preferences.s(user_id) for user_id in user_ids]

        # Execute the group of tasks concurrently
        job_group = group(job_preference_tasks)
        result = job_group.apply_async()

        logger.info(f"Dispatched {len(user_ids)} process_job_preferences tasks successfully.")
        return f"Dispatched {len(user_ids)} tasks."

    except Exception as e:
        logger.error(f"Error in process_all_users_job_preferences: {e}", exc_info=True)
        # Retry the task in case of failure
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds

@celery.task(bind=True,max_retries=3,name='remove_duplicate_embeddings')
def remove_duplicate_embeddings(self):
    """Remove job postings with duplicate embeddings, keeping the most recent entries."""
    try:
        # First, delete related entries in user_job_fit
        duplicate_ids_query = """
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (PARTITION BY embedding512 ORDER BY created_at DESC) as row_num
                FROM job_postings
                WHERE embedding512 IS NOT NULL
            ) t
            WHERE t.row_num > 1
        """
        
        # Delete user_job_fit entries
        user_job_fits_response = supabase.rpc(
            'delete_user_job_fits_for_duplicates',
            {
                'duplicate_ids_query': duplicate_ids_query
            }
        ).execute()

        # Delete duplicate job_postings
        job_postings_response = supabase.rpc(
            'delete_duplicate_job_postings',
            {
                'duplicate_ids_query': duplicate_ids_query
            }
        ).execute()

        user_job_fits_deleted = len(user_job_fits_response.data) if user_job_fits_response.data else 0
        job_postings_deleted = len(job_postings_response.data) if job_postings_response.data else 0

        logger.info(f"Successfully removed {job_postings_deleted} duplicate job postings and {user_job_fits_deleted} related fit scores")
        return {
            'job_postings_deleted': job_postings_deleted,
            'user_job_fits_deleted': user_job_fits_deleted
        }

    except Exception as e:
        logger.error(f"Error removing duplicate embeddings: {str(e)}")
        raise e
    
@celery.task(bind=True, max_retries=3, name='remove_duplicate_jobs')
def remove_duplicate_jobs(self):
    """Remove duplicate job postings with same title, company and location, keeping the most recent entries."""
    try:
        # First identify duplicates using PostgreSQL function
        duplicates = supabase.rpc(
            'get_duplicate_job_ids'
        ).execute()

        duplicate_ids = [record['duplicate_id'] for record in duplicates.data] if duplicates.data else []

        if not duplicate_ids:
            logger.info("No duplicates found")
            return {
                'job_postings_deleted': 0,
                'deleted_ids': []
            }

        # Delete from user_job_fit first
        user_job_fit_deleted = supabase.table('user_job_fit') \
            .delete() \
            .in_('job_postings_id', duplicate_ids) \
            .execute()

        # Then delete from job_postings
        job_postings_deleted = supabase.table('job_postings') \
            .delete() \
            .in_('id', duplicate_ids) \
            .execute()

        num_deleted = len(job_postings_deleted.data) if job_postings_deleted.data else 0
        logger.info(f"Successfully removed {num_deleted} duplicate job postings")
        
        return {
            'job_postings_deleted': num_deleted,
            'user_job_fits_deleted': len(user_job_fit_deleted.data) if user_job_fit_deleted.data else 0,
            'deleted_job_ids': [record['id'] for record in job_postings_deleted.data] if job_postings_deleted.data else []
        }

    except Exception as e:
        logger.error(f"Error removing duplicate jobs: {str(e)}")
        raise e

TEST_PREFERRED_LOCATIONS = ["New York, NY", "Los Angeles, CA"]
# Preferred Locations
states = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "California": "CA",
    "Colorado": "CO",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Massachusetts": "MA",
    "Maryland": "MD",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Missouri": "MO",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Virginia": "VA",
    "Washington": "WA",
    "Wisconsin": "WI"
}

HIRING_CAFE_BASE_URL = "https://hiring.cafe/"

def generate_random_place_id():
    """Generate a random hex string to simulate a place ID."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

def build_hiring_cafe_url(base_url, location):
    """
    Generates a properly formatted Hiring Cafe URL.
    
    :param base_url: The base URL for the Hiring Cafe job search.
    :param location: The formatted address (e.g., "Arizona, United States").
    :return: Fully formatted and encoded URL.
    """

    # Generate a random hex string for the place ID
    random_place_id = generate_random_place_id()

    # Split the location to extract the state and country
    location_parts = location.split(",")
    
    # Check if we have exactly two parts (state, country)
    if len(location_parts) == 2:
        state = location_parts[0].strip()  # e.g., "New York"
        country = location_parts[1].strip()  # e.g., "United States"
    else:
        # If there is no comma, assume the country is "United States"
        state = location.strip()
        country = "United States"

    # Check if the state is in our states dictionary
    if state not in states:
        # If not found in the states dictionary, assume the first two letters of the state are its abbreviation
        state_abbreviation = state[:2].upper()
    else:
        # If the state is found in the dictionary, use its abbreviation
        state_abbreviation = states[state]

    # Define the JSON structure
    search_state = {
        "locationSearchType": "precise",
        "selectedPlaceDetail": {
            "formatted_address": location,
            "types": ["administrative_area_level_1"],
            "place_id": random_place_id,  # Use the randomly generated place ID
            "address_components": [
                {
                    "long_name": state,
                    "short_name": state_abbreviation,
                    "types": ["administrative_area_level_1"]
                },
                {
                    "long_name": 'United States',
                    "short_name": 'US',
                    "types": ["country"]
                }
            ]
        },
        "higherOrderPrefs": []
    }

    # Convert JSON to string and URL-encode it
    encoded_search_state = urllib.parse.quote(json.dumps(search_state, separators=(",", ":")))

    # Construct the final URL
    return f"{base_url}?searchState={encoded_search_state}"

# Use states as TEST_PREFERRED_LOCATIONS
TEST_PREFERRED_LOCATIONS = list(states.keys())


@celery.task(bind=True, name='scrape_hiring_cafe')
def scrape_hiring_cafe(self):
    """Fetches job listings from Hiring Cafe API via ScrapingBee and extracts response correctly."""
    
    logger.info("Starting scrape for Hiring Cafe")

    for location in TEST_PREFERRED_LOCATIONS:
        url = build_hiring_cafe_url(HIRING_CAFE_BASE_URL, location)
        logger.info(f"Built URL: {url}")
        print(f"Built URL: {url}")

        try:
            # Making the API request
            response = scraping_bee_client.get(
                url,
                params={
                    "render_js": True,
                    "wait": 1000,
                    "json_response": True
                }
            )

            if response.status_code == 200:
                logger.info(f"Successfully intercepted API response for {location}")
                print(f"Successfully intercepted API response for {location}")

                try:
                    # Parse JSON response
                    api_responses = response.json()

                    # Ensure "xhr" key exists
                    if "xhr" in api_responses and isinstance(api_responses["xhr"], list):
                        search_jobs_response = None

                        for req in api_responses["xhr"]:
                            if isinstance(req, dict) and req.get("url") == 'https://hiring.cafe/api/search-jobs':
                                # Debugging: Check raw body
                                raw_body = req.get("body", "{}")
                                print(f"Raw 'body' content for {location}: {raw_body[:500]}...")  # Print first 500 chars
                                
                                # Ensure that the raw body content is correctly formatted
                                try:
                                    # Replace single quotes with double quotes (not ideal for all cases, better validation needed)
                                    formatted_body = raw_body

                                    # Try parsing the formatted body to JSON
                                    search_jobs_response = json.loads(formatted_body)

                                except json.JSONDecodeError as e:
                                    # If JSONDecodeError happens, output it and continue
                                    print(f"JSON Decode Error while parsing body for {location}: {e}")
                                    continue  # Skip to next response

                                break

                        # Extract information from the response
                        if search_jobs_response:
                            job_results = search_jobs_response.get('results', [])

                            for job_data in job_results:  # 🔁 Loop over all job postings
                                job_info = job_data.get('job_information', {})
                                company_data = job_data.get('v5_processed_company_data', {})
                                workplace_data = job_data.get('v5_processed_job_data', {})

                                # ✅ Extract and format date_posted
                                date_posted = workplace_data.get('estimated_publish_date')
                                if date_posted:
                                    date_posted = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                                    date_posted = date_posted.isoformat()  # ✅ Convert to string before saving
                                elif workplace_data.get('estimated_publish_date_millis'):
                                    date_posted = datetime.utcfromtimestamp(workplace_data['estimated_publish_date_millis'] / 1000)
                                    date_posted = date_posted.isoformat()  # ✅ Convert to string before saving
                                    
                                else:
                                    date_posted = None  # Ensure None if no date is found

                                # ✅ Extract and properly format location (Remove duplicates)
                                workplace_cities = workplace_data.get('workplace_cities', [])
                                workplace_states = workplace_data.get('workplace_states', [])
                                
                                # Remove duplicates by converting to a set
                                location_parts = list(dict.fromkeys(workplace_cities + workplace_states))  # Keeps order but removes dupes
                                location = ", ".join(location_parts) if location_parts else workplace_data.get('formatted_workplace_location', None)

                                # ✅ Extract and clean job description (Remove HTML tags)
                                raw_description = job_info.get('description', "")
                                job_description = BeautifulSoup(raw_description, "html.parser").get_text(separator=" ").strip()

                                # ✅ Fix Remote Status Detection
                                workplace_type = job_data.get('workplace_type') or workplace_data.get('workplace_type')  # Check both levels
                                if workplace_type:
                                    workplace_type = workplace_type.strip().lower()  # Normalize case and trim spaces

                                if workplace_type == 'onsite':
                                    remote = 'No'
                                elif workplace_type == 'remote':
                                    remote = 'Yes'
                                elif workplace_type == 'hybrid':
                                    remote = 'Hybrid'
                                else:
                                    remote = 'Unknown'  # Handle unexpected values

                                # ✅ Debugging: Log what values are being received
                                logger.warning(f"Debug: workplace_type received: {workplace_type}")  


                                # ✅ Extract salary range (Format properly)
                                min_salary = workplace_data.get('yearly_min_compensation')
                                max_salary = workplace_data.get('yearly_max_compensation')
                                salary_range = f"${min_salary:,} - ${max_salary:,}" if min_salary and max_salary else None

                                # ✅ Extract other job details
                                job_title = job_info.get('title', None)
                                posting_url = job_data.get('apply_url', None)
                                company = company_data.get('name', None)

                                # Generate text embedding
                                embedding_text = f"{job_title} {company} {location} {job_description}"
                                job_embedding = generate_embedding_job(embedding_text, 512)
                                logger.info("Generated job embedding")


                                # ✅ Prepare data for Supabase
                                job_record = {
                                    "date_posted": date_posted,
                                    "posting_url": posting_url,
                                    "company": company,
                                    "location": location,
                                    "job_description": job_description,
                                    "remote": remote,
                                    "salary_range": salary_range,
                                    "job_title": job_title,
                                    "embedding512": job_embedding
                                }

                                # ✅ Save to Supabase (Handle duplicates)
                                try:
                                    supabase.table('job_postings').insert(job_record).execute()
                                    logger.info(f"✅ Job posting saved for {company} at {location}")
                                    print(f"✅ Job posting saved for {company} at {location}")
                                except Exception as e:
                                    logger.error(f"⚠️ Error saving job {posting_url}: {e}")
                                    print(f"⚠️ Error saving job {posting_url}: {e}")

                        else:
                            print(f"⚠️ No 'search-jobs' API response found")


                    else:
                        print(f"⚠️ No valid 'xhr' key in the API response for {location}")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON response for {location}: {e}")
                    print(f"Failed to decode JSON response for {location}: {e}")

            else:
                logger.error(f"Failed to fetch API response for {location}, status code: {response.status_code}")
                print(f"Failed to fetch API response for {location}, status code: {response.status_code}")

        except Exception as e:
            logger.error(f"Request failed for {location}: {e}")
            print(f"Request failed for {location}: {e}")

def generate_embedding_job(client, text, dimensionality=512):
    """Generates a text embedding using Azure OpenAI API."""
    try:
        response = embedding_client.embeddings.create(
            input=str(text),
            model='text-embedding-3-small',
            dimensions=dimensionality
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        raise