import os
import numpy as np
from openai import AzureOpenAI # type: ignore
from scipy.spatial.distance import cosine
from supabase import create_client
#from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from typing import List, Optional, Dict

load_dotenv()
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# PINECONE_API_KEY=os.getenv('PINECONE_API_KEY')
# pinecone = Pinecone(api_key=PINECONE_API_KEY,environment=os.getenv("PINECONE_ENVIRONMENT"))

client = AzureOpenAI(
    api_key = os.getenv('AZURE_OPENAI_TEXT_EMBEDDING_KEY'),
    api_version="2024-07-01-preview",
    azure_endpoint="https://cognibly-jobs-ai-service.openai.azure.com/openai/deployments/text-embedding-3-small/embeddings?api-version=2023-05-15"
)

def generate_embedding(text, dimensionality):
    try:
        response = client.embeddings.create(
            input=text,
            model='text-embedding-3-small',
            dimensions=dimensionality
        )
        # The response structure has changed in the new OpenAI API version
        # We need to access the embedding data differently
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        raise

def embed_job_details(job_id_number,dimensionality=512):
    response = supabase.table('job_postings').select('*').eq('id',job_id_number).execute()
    if response.data:
        job = response.data[0]
        text = f"""
            Job Title: {job['job_title']}
            Company Name: {job['company_name']}
            Location: {job['location']}
            Job Description: {job['job_description']}
            Remote Job?: {job['remote']}
            Salary Range: {job['salary_range']}
            """
        embedding = generate_embedding(text,dimensionality)
        supabase.table('job_postings').update({
            f"embedding{dimensionality}":embedding
        }).eq('id',job_id_number).execute()
    else:
        print("Did not receive data for the given Job Details ID number.")
        return None

def embed_user_preferences(user_id, dimensionality=512):
    try:
        response = supabase.table('user_job_preferences').select('*').eq('user_id', user_id).execute()
        if not response.data:
            print(f"No preferences found for user {user_id}. Raw response: {str(response)}")
            return None
            
        preferences = response.data[0]
        text = f"""
            Ideal Work Situation: {preferences['ideal_work_situation']}
            Preferred Industries: {preferences['preferred_industries']}
            Preferred Work Arrangement: {preferences['work_arrangement_preference']}
            Willing to Relocate?: {preferences['willing_to_relocate']}
            Current City: {preferences['current_city']}
            Current State: {preferences['current_state']}
            Preferred Relocation Location(s): {preferences['preferred_locations']}
            Preferred Role & Responsibilities: {preferences['preferred_roles_responsibilities']}
            Preferred Salary Range: {preferences['expected_salary_range']}
            Industry Importance Weight (out of 5): {preferences['industry_importance']}
            Location & Work Arrangement Importance Weight (out of 5): {preferences['location_work_arrangement_importance']}
            Role & Responsibilities Importance Weight (out of 5): {preferences['role_responsibilities_importance']}
            Salary Importance Weight (out of 5): {preferences['salary_importance']}
            Company Prestige Importance Weight (out of 5): {preferences['company_prestige_importance']}
            Job Search Keywords: {preferences.get('keywords', [])}
        """
        
        embedding = generate_embedding(text, dimensionality)
        if embedding:
            update_response = supabase.table('user_job_preferences').update({
                f"embedding{dimensionality}": embedding
            }).eq('user_id', user_id).execute()
            
            if not update_response.data:
                print(f"Failed to update embedding for user {user_id}")
                return None
                
            return embedding
            
    except Exception as e:
        print(f"Error in embed_user_preferences: {str(e)}")
        raise

    return None
    
def get_embedding(table, id, dimensionality):
    response = supabase.table(table).select(f'embedding{dimensionality}').eq('id', id).execute()
    if response.data and response.data[0][f'embedding{dimensionality}']:
        embedding = response.data[0][f'embedding{dimensionality}']
        # Convert to numpy array and ensure it's 1-D
        if isinstance(embedding, str):
            # If it's stored as a string, convert to list then to numpy array
            embedding = np.array(eval(embedding))
        elif isinstance(embedding, list):
            embedding = np.array(embedding)
        
        # Ensure it's 1-D
        embedding = embedding.flatten()
        
        return embedding
    else:
        print(f"No embedding found for id {id} in table {table}")
        return None

    
def calculate_user_job_fit(user_job_preferences_id, job_postings_id,dimensionality=512):
    user_job_preferences_embedding = get_embedding('user_job_preferences',user_job_preferences_id,dimensionality)
    job_details_embedding = get_embedding('job_postings',job_postings_id,dimensionality)
    if user_job_preferences_embedding is None:
        print(f"Could not get embedding data for {user_job_preferences_id}")
        return None
    if job_details_embedding is None: 
        print(f"Could not get embedding data for {job_postings_id}")
        return None
    fit = 1 - cosine(user_job_preferences_embedding, job_details_embedding)
    supabase.table('user_job_fit').insert({
        "user_job_preferences_id":user_job_preferences_id,
        "job_postings_id":job_postings_id,
        f"fit_score_{dimensionality}":fit,
    }).execute()
    return fit

import json  # Add this import at the top of your jobmatcher.py
import logging

logger = logging.getLogger(__name__)

def get_user_embedding(user_job_preferences_id: int, dimensionality: int = 512) -> Optional[List[float]]:
    """Fetch the user's job preferences embedding from the database."""
    logger.info(f"Fetching user embedding for user_job_preferences_id: {user_job_preferences_id}")
    response = supabase.table('user_job_preferences') \
                       .select('embedding512') \
                       .eq('id', user_job_preferences_id) \
                       .single() \
                       .execute()
    
    # Log the raw response data for debugging
    logger.debug(f"Raw response data: {response.data}")
    
    if not response.data:
        logger.error(f"Could not retrieve embedding for user_job_preferences_id: {user_job_preferences_id}. Raw response: {str(response)}")
        return None
    
    embedding_str = response.data.get('embedding512')
    
    if not embedding_str:
        logger.error(f"No embedding512 data found for user_job_preferences_id: {user_job_preferences_id}.")
        return None
    
    # Check if the embedding is a string and parse it
    if isinstance(embedding_str, str):
        try:
            # Using json.loads if the string is in JSON array format
            embedding = json.loads(embedding_str)
            logger.info(f"Successfully parsed embedding512 for user_job_preferences_id {user_job_preferences_id}.")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse embedding512 for user_job_preferences_id {user_job_preferences_id}. Invalid JSON format.")
            return None
    elif isinstance(embedding_str, list):
        # If it's already a list, no action needed
        embedding = embedding_str
        logger.info(f"Embedding512 is already a list for user_job_preferences_id {user_job_preferences_id}.")
    else:
        logger.error(f"Unexpected data type for embedding512: {type(embedding_str)}. Expected str or list.")
        return None
    
    # Optionally, verify the length of the embedding
    if len(embedding) != dimensionality:
        logger.error(f"Embedding dimension mismatch for user_job_preferences_id {user_job_preferences_id}. Expected {dimensionality}, got {len(embedding)}.")
        return None
    
    return embedding

def get_all_job_embeddings(dimensionality: int = 512, batch_size: int = 1000) -> List[Dict]:
    """Fetch all job postings' embeddings from the database in batches."""
    logger.info("Starting batch retrieval of job postings' embeddings.")
    all_valid_jobs = []
    page = 0  # Current batch number

    while True:
        from_ = page * batch_size
        to = from_ + batch_size - 1  # Supabase range is inclusive
        logger.debug(f"Fetching jobs with range {from_} to {to}.")

        try:
            response = supabase.table('job_postings') \
                               .select('id, embedding512') \
                               .order('id', desc=False) \
                               .range(from_, to) \
                               .execute()
        except Exception as e:
            logger.error(f"Exception during fetching job embeddings: {e}")
            break

        # Handle empty data gracefully
        if not response.data:
            if page == 0:
                logger.info("No job postings found in the database.")
            else:
                logger.info("No more job postings to fetch.")
            break

        batch_jobs = response.data
        valid_jobs = []
        for job in batch_jobs:
            job_id = job.get('id')
            embedding_str = job.get('embedding512')

            if not embedding_str:
                logger.warning(f"No embedding512 found for job_id {job_id}. Skipping.")
                continue

            # Parse the embedding string into a list
            if isinstance(embedding_str, str):
                try:
                    embedding = json.loads(embedding_str)
                    logger.debug(f"Parsed embedding512 for job_id {job_id}.")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse embedding512 for job_id {job_id}. Invalid JSON format. Skipping.")
                    continue
            elif isinstance(embedding_str, list):
                embedding = embedding_str
                logger.debug(f"Embedding512 is already a list for job_id {job_id}.")
            else:
                logger.error(f"Unexpected data type for embedding512: {type(embedding_str)} for job_id {job_id}. Skipping.")
                continue

            # Verify embedding dimensionality
            if len(embedding) != dimensionality:
                logger.error(f"Embedding dimension mismatch for job_id {job_id}. Expected {dimensionality}, got {len(embedding)}. Skipping.")
                continue

            # Append the valid job with parsed embedding
            valid_jobs.append({
                'id': job_id,
                'embedding512': embedding
            })

        logger.info(f"Fetched {len(batch_jobs)} jobs in batch {page + 1}, {len(valid_jobs)} valid ones.")
        all_valid_jobs.extend(valid_jobs)
        page += 1

    logger.info(f"Completed fetching job embeddings. Total valid jobs: {len(all_valid_jobs)}")
    return all_valid_jobs

def calculate_all_job_fits(user_job_preferences_id: int, dimensionality: int = 512, batch_size_insert: int = 500) -> Optional[np.ndarray]:
    """Calculate and store job fit scores for a user's preferences."""
    
    logger.info(f"Starting job fit calculation for user_job_preferences_id: {user_job_preferences_id}")
    
    # Step 1: Retrieve the user's embedding
    user_embedding = get_user_embedding(user_job_preferences_id, dimensionality)
    if user_embedding is None:
        logger.error(f"No embedding found for user_job_preferences_id: {user_job_preferences_id}")
        return None
        
    user_vector = np.array(user_embedding, dtype=float)
    user_norm = np.linalg.norm(user_vector)
    if user_norm == 0:
        logger.error("User embedding vector has zero norm.")
        return None
    user_vector_normalized = user_vector / user_norm
    logger.info("User embedding successfully normalized.")
    
    # Step 2: Retrieve all job embeddings in batches
    job_postings = get_all_job_embeddings(dimensionality)
    if not job_postings:
        logger.error("No job postings available for fit calculation.")
        return None
    
    job_ids = []
    job_embeddings = []
    for job in job_postings:
        job_id = job['id']
        embedding = job['embedding512']
        job_ids.append(job_id)
        job_embeddings.append(embedding)
    
    if not job_embeddings:
        logger.error("No valid job embeddings found for calculation.")
        return None
    
    job_matrix = np.array(job_embeddings, dtype=float)
    job_norms = np.linalg.norm(job_matrix, axis=1)
    
    # Avoid division by zero
    valid_norms = job_norms != 0
    if not np.all(valid_norms):
        skipped = np.sum(~valid_norms)
        logger.warning(f"Filtered out {skipped} jobs with zero norm embeddings.")
        job_matrix = job_matrix[valid_norms]
        job_ids = [job_id for idx, job_id in enumerate(job_ids) if valid_norms[idx]]
        job_norms = job_norms[valid_norms]
    
    job_matrix_normalized = job_matrix / job_norms[:, np.newaxis]
    logger.info(f"Normalized {len(job_ids)} job embeddings.")
    
    # Step 3: Compute cosine similarities
    cosine_similarities = np.dot(job_matrix_normalized, user_vector_normalized)
    cosine_similarities = np.clip(cosine_similarities, -1.0, 1.0)
    logger.info("Cosine similarities computed.")
    
    # Step 4: Prepare data for bulk insertion
    fit_data = [
        {
            "user_job_preferences_id": user_job_preferences_id,
            "job_postings_id": job_id,
            f"fit_score_{dimensionality}": float(sim)
        }
        for job_id, sim in zip(job_ids, cosine_similarities)
    ]
    logger.info(f"Prepared fit scores data for bulk insertion: {len(fit_data)} records.")
    
    # Step 5: Perform bulk insert in smaller batches
    inserted_count = 0
    failed_batches = 0
    
    # First, clear existing entries for this user to avoid duplicates
    try:
        delete_response = supabase.table('user_job_fit') \
                                  .delete() \
                                  .eq('user_job_preferences_id', user_job_preferences_id) \
                                  .execute()
    except Exception as e:
        logger.exception(f"Exception during deletion of existing fit scores: {e}")
        return None
    
    # Handle DELETE response data
    if delete_response.data:
        deleted_count = len(delete_response.data)
        logger.info(f"Deleted {deleted_count} existing fit scores for user {user_job_preferences_id}.")
    else:
        logger.info(f"No existing fit scores to delete for user {user_job_preferences_id}.")
    
    # Proceed with bulk insertion
    for i in range(0, len(fit_data), batch_size_insert):
        batch = fit_data[i:i+batch_size_insert]
        try:
            response = supabase.table('user_job_fit').insert(batch).execute()
        except Exception as e:
            logger.exception(f"Exception during insertion of batch starting at index {i}: {e}")
            failed_batches += 1
            continue

        # Since 'status_code' and 'error' are not available, infer success based on 'response.data'
        if not response.data:
            logger.error(f"Failed to insert batch starting at index {i}. No data returned.")
            failed_batches += 1
            continue

        inserted_count += len(batch)
        logger.info(f"Successfully inserted batch starting at index {i}: {len(batch)} records.")

    logger.info(f"Successfully inserted {inserted_count} of {len(fit_data)} fit scores for user_job_preferences_id {user_job_preferences_id}.")
    if failed_batches > 0:
        logger.warning(f"Failed to insert {failed_batches} batches. Please review the errors.")
    
    # Return fit scores if needed
    if inserted_count == 0:
        return None
    return cosine_similarities

def process_new_job(job_id):
    pass

# def process_new_jobs():
#     new_jobs = scrape_new_jobs()
#     for job in new_jobs:
#         job_embedding = create_embedding(job.description)
#         process_job(job, job_embedding)

# def process_job(job, job_embedding):
#     users = get_all_users()
#     for user in users:
#         similarity_score = calculate_cosine_similarity(job_embedding, user.profile_embedding)
#         insert_job_fit(job.id, user.id, similarity_score)
    
#     update_percentiles()
#     refresh_materialized_views()
    
######
#START
######
# embed_user_preferences(1,256)
# embed_job_details(1926,512)
# iterator = 1927
# lastjob = 1309
# while iterator >= lastjob:
#     try:
#         embed_job_details(iterator,256)
#         print(f"Finished embedding job_details entry with id: {iterator}")
#         iterator = iterator - 1
#     except Exception as e:
#         print(f"Failed to embed job_details entry with id: {iterator}. Details: {e}")
#         print("Stopping.")
#         break


# job_id = 1927
# while job_id >= 1309:
#     diff = calculate_user_job_fit(1,job_id,512)
#     print(f"Cosine difference between user preferences and Job ID {job_id}: {str(diff)}")
#     job_id -= 1


# #Define the index
# index_name = "job-embeddings"
# # if index_name not in pinecone.list_indexes():
# #     pinecone.create_index(index_name, dimension=1536, metric="cosine", spec=ServerlessSpec(
# #             cloud='aws', 
# #             region='us-east-1'
# #         )
# #     )

# #Connect to the index
# index = pinecone.Index(index_name)

# def insert_job(job):
#     job_text = format_job_for_embedding(job)
#     job_embedding = generate_embedding(job_text)
    
#     index.upsert(vectors=[
#         {
#             "id": str(job['id']),
#             "values": job_embedding,
#             "metadata": {
#                 "title": job['title'],
#                 "company": job['company'],
#                 "location": job['location'],
#                 "salary": job['salary'],
#                 "industry": job['industry'],
#                 "role": job['role'],
#                 "work_arrangement": job['work_arrangement']
#             }
#         }
#     ])

# def search_similar_jobs(user_preferences, top_k=10): #top_k=10 means Find the 10 most similar jobs given user preferences
#     preference_text = format_job_for_embedding(user_preferences)
#     query_embedding = generate_embedding(preference_text)
#     results = index.query(
#         vector=query_embedding,
#         top_k=top_k,
#         include_metadata=True
#     )    
#     return results    

# Insert a job
# job = {
#     "id": "job123",
#     "title": "Senior Software Engineer",
#     "company": "TechCorp",
#     "location": "San Francisco, CA",
#     "salary": "$150,000 - $200,000",
#     "industry": "Technology",
#     "role": "Backend Developer",
#     "work_arrangement": "Hybrid",
#     "description": "We're looking for an experienced backend developer..."
# }
# #insert_job(job)

# # Search for similar jobs
# user_preferences = {
#     "title": "Software Engineer",
#     "company": "JeetSoft",
#     "location": "San Francisco Bay Area",
#     "salary": "$120,000 - $180,000",
#     "industry": "Technology",
#     "role": "Full Stack Developer",
#     "work_arrangement": "Remote",
#     "description": "Looking for a challenging role in a fast-paced environment..."
# }

# similar_jobs = search_similar_jobs(user_preferences)

# Print results
# for match in similar_jobs['matches']:
#     print(f"Job ID: {match['id']}")
#     print(f"Similarity Score: {match['score']}")
#     print("Job Details:")
#     for key, value in match['metadata'].items():
#         print(f"  {key}: {value}")
#     print("\n")
